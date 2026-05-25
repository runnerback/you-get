#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Bilibili CC 字幕（含 AI）抓取与转换。

依赖 MediaCrawlerPro-SignSrv 提供 wbi 签名。任何失败 log.w 后跳过，
不抛异常，不影响视频本体下载。
"""

import json
import logging
import os
from typing import Dict

from ..util.signsrv_client import (
    is_signsrv_available,
    call_bilibili_sign,
    DEFAULT_SIGN_SRV_URL,
)
from ..common import get_content

logger = logging.getLogger(__name__)

BILIBILI_SUBTITLE_API = "https://api.bilibili.com/x/player/wbi/v2"


# ---------- 纯函数 ----------

def _seconds_to_srt_timestamp(t: float) -> str:
    """秒（float）转 SRT 时间戳 HH:MM:SS,mmm。"""
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:06.3f}".format(int(h), int(m), s).replace(".", ",")


def _json_to_srt(bili_subtitle_json: Dict) -> str:
    """将 B 站字幕 JSON（body 数组）转 SRT 字符串。

    B 站格式：{"body": [{"from": float秒, "to": float秒, "content": str}, ...]}
    SRT 格式：每段 N\\nHH:MM:SS,mmm --> HH:MM:SS,mmm\\n内容\\n\\n
    """
    body = bili_subtitle_json.get("body") or []
    lines = []
    seq = 0
    for seg in body:
        content = seg.get("content")
        if not content:
            continue
        start = _seconds_to_srt_timestamp(seg.get("from", 0))
        end = _seconds_to_srt_timestamp(seg.get("to", 0))
        seq += 1
        lines.append(f"{seq}\n{start} --> {end}\n{content}\n\n")
    return "".join(lines)


def _is_ai_subtitle(subtitle: Dict) -> bool:
    """判定一条字幕是否为 AI 生成。

    判定规则（任一为真）：
    - type == 1
    - ai_type > 0
    - lan 以 "ai-" 开头
    """
    if subtitle.get("type") == 1:
        return True
    if (subtitle.get("ai_type") or 0) > 0:
        return True
    lan = subtitle.get("lan") or ""
    if lan.startswith("ai-"):
        return True
    return False


def _serialize_cookies(cookies) -> str:
    """把 cookies（dict / str / CookieJar / None）序列化成 'k=v; k=v' 字符串。"""
    if cookies is None:
        return ""
    if isinstance(cookies, str):
        return cookies
    if isinstance(cookies, dict):
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    try:
        from http.cookiejar import CookieJar
        if isinstance(cookies, CookieJar):
            return "; ".join(f"{c.name}={c.value}" for c in cookies)
    except Exception:
        pass
    return ""


# ---------- 主流程 ----------

def fetch_subtitles(extractor, avid, cid) -> None:
    """抓取并填充 extractor.caption_tracks。

    任何失败（前置检查、签名、列表接口、单条字幕下载）都 log.w 后跳过对应步骤，
    不抛异常、不影响 caller。

    cookies 从 you_get.common.cookies 全局读取（避免 import * 的快照问题）。

    Args:
        extractor: 持有 caption_tracks dict 的 VideoExtractor 实例
        avid: 视频 aid（int 或 str 都接受）
        cid: 分 P 的 cid
    """
    from .. import common
    cookie_str = _serialize_cookies(common.cookies)
    if not cookie_str:
        logger.warning("[Subtitle] 未提供 cookies（--cookies 未传 且 资源服务注入未成功），跳过字幕下载")
        return

    if not is_signsrv_available():
        url = os.environ.get("SIGN_SRV_URL", DEFAULT_SIGN_SRV_URL)
        logger.warning(f"[Subtitle] SignSrv 不可达 ({url})，跳过字幕下载")
        return

    sign = call_bilibili_sign({"aid": str(avid), "cid": str(cid)}, cookie_str)
    if not sign:
        logger.error("[Subtitle] 获取 wbi 签名失败，跳过字幕下载")
        return

    list_url = (
        f"{BILIBILI_SUBTITLE_API}"
        f"?aid={avid}&cid={cid}"
        f"&wts={sign['wts']}&w_rid={sign['w_rid']}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bilibili.com/",
        "Cookie": cookie_str,
    }
    try:
        resp_text = get_content(list_url, headers=headers)
        resp = json.loads(resp_text)
    except Exception as e:
        logger.error(f"[Subtitle] 字幕列表接口请求失败: {e}")
        return

    if resp.get("code") != 0:
        logger.error(
            f"[Subtitle] 字幕列表接口返回错误 "
            f"code={resp.get('code')} message={resp.get('message')}"
        )
        return

    subtitles = (resp.get("data") or {}).get("subtitle", {}).get("subtitles") or []
    if not subtitles:
        logger.info("[Subtitle] 该视频无可用字幕")
        return

    for sub in subtitles:
        _try_fetch_one(extractor, sub, headers)


def _try_fetch_one(extractor, sub: Dict, headers: Dict) -> None:
    """下载一条字幕并填入 caption_tracks。单条失败 log.w 后跳过。"""
    lan = sub.get("lan") or "unknown"
    sub_url = sub.get("subtitle_url") or ""
    if not sub_url:
        logger.warning(f"[Subtitle] {lan} 无 subtitle_url，跳过")
        return
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url

    try:
        sub_json = json.loads(get_content(sub_url, headers=headers))
    except Exception as e:
        logger.warning(f"[Subtitle] 下载 {lan} 字幕 JSON 失败: {e}")
        return

    srt = _json_to_srt(sub_json)
    if not srt:
        logger.warning(f"[Subtitle] {lan} 字幕 body 为空，跳过")
        return

    is_ai = _is_ai_subtitle(sub)
    if is_ai and not lan.startswith("ai-"):
        key = f"ai-{lan}"
    else:
        key = lan

    if key in extractor.caption_tracks:
        logger.warning(f"[Subtitle] caption key '{key}' 已存在，保留先到达，跳过本条")
        return

    extractor.caption_tracks[key] = srt
    logger.info(f"[Subtitle] 已抓取 {key}（{len(sub_json.get('body') or [])} 段）")
