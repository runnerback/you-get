#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 站字幕端到端手动验证脚本。

前置：
    1. 启动 SignSrv：
       cd ../MediaCrawlerPro-SignSrv && venv/bin/python app.py &
    2. 准备 cookies.txt（Netscape 格式，含 SESSDATA）

用法：
    python tests/manual_test_bili_subtitle.py --cookies ~/bili_cookies.txt --bv BVxxxxxx

验证场景：
    v1 SignSrv 在线 + 有 cookies + 有字幕的视频 → 字幕被抓取
    v2 SignSrv 离线                            → warn skip，caption_tracks 为空
    v3 不传 cookies                            → warn skip
    v4 无字幕视频（如外国 MV）                 → info "无可用字幕"

同时打印 subtitles[] 原始字段以校准 AI 判定（spec §4.3）。
"""

import argparse
import gzip
import json
import logging
import re
import sys
from pathlib import Path
from urllib import request

# 让脚本能从 you-get 根目录跑
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from you_get.common import load_cookies, cookies as _  # noqa: F401  确保模块初始化
from you_get import common
from you_get.extractors.bilibili_subtitle import fetch_subtitles, _serialize_cookies


class FakeExtractor:
    def __init__(self):
        self.caption_tracks = {}


def resolve_bv_to_aid_cid(bv_or_url: str, cookie_str: str):
    """从 BV 号或 URL 拿 aid/cid（用 initial_state）。"""
    url = bv_or_url if bv_or_url.startswith("http") else f"https://www.bilibili.com/video/{bv_or_url}/"
    req = request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Encoding": "gzip",
        "Cookie": cookie_str,
    })
    with request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        html = raw.decode("utf-8", errors="ignore")

    m = re.search(r"__INITIAL_STATE__=(.*?);\(function", html)
    if not m:
        raise RuntimeError("找不到 __INITIAL_STATE__（可能视频不存在或被风控）")
    data = json.loads(m.group(1))
    aid = data.get("aid")
    vd = data.get("videoData") or {}
    cid = vd.get("cid") or (vd.get("pages") or [{}])[0].get("cid")
    return aid, cid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies", help="Netscape cookies.txt 路径（不传则模拟 v3）")
    parser.add_argument("--bv", required=True, help="BV 号或视频 URL")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    if args.cookies:
        load_cookies(args.cookies)

    cookie_str = _serialize_cookies(common.cookies)
    aid, cid = resolve_bv_to_aid_cid(args.bv, cookie_str)
    print(f"\n>>> aid={aid}  cid={cid}")

    ext = FakeExtractor()
    fetch_subtitles(ext, aid, cid)

    print(f"\n>>> 抓取到 {len(ext.caption_tracks)} 条字幕")
    for key, srt in ext.caption_tracks.items():
        print(f"\n--- {key} ---")
        head = "\n".join(srt.splitlines()[:6])
        print(head)


if __name__ == "__main__":
    main()
