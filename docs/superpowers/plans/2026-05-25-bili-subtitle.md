# Bilibili CC 字幕下载（含 AI 字幕）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `you-get` 的 `bilibili.py` extractor 里增加 CC 字幕（含 AI 自动生成）下载能力，复用 `extractor.py:244-255` 通用字幕落盘机制，依赖 `MediaCrawlerPro-SignSrv` 提供 wbi 签名。

**Architecture:**
- 新增 `util/signsrv_client.py` 封装 SignSrv HTTP 调用（健康检查 + 调签名）
- 新增 `extractors/bilibili_subtitle.py` 实现"拉字幕列表 → 拉字幕 JSON → 转 SRT → 填充 `caption_tracks`"完整链路
- 在 `bilibili.py` 三处 `# get danmaku` 旁加一行调用
- 全程"warn 后跳过"，字幕失败不阻塞视频下载

**Tech Stack:**
- Python 3.12 + stdlib (urllib, json, unittest)
- 复用 you-get 现有 `get_content()` 工具
- 依赖外部服务：MediaCrawlerPro-SignSrv（默认 `http://127.0.0.1:8989`）

**Spec:** `docs/superpowers/specs/2026-05-25-bili-subtitle-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `src/you_get/util/signsrv_client.py` | **新建** | SignSrv HTTP 客户端（`is_signsrv_available`, `call_bilibili_sign`） |
| `src/you_get/extractors/bilibili_subtitle.py` | **新建** | 字幕抓取主流程（`fetch_subtitles`）+ 纯函数（`_json_to_srt`, `_serialize_cookies`, `_is_ai_subtitle`） |
| `src/you_get/extractors/bilibili.py` | **修改 3 处** | 第 338、417、599 行（`# get danmaku` 之后）各加一行调用 |
| `tests/test_signsrv_client.py` | **新建** | SignSrv 客户端单元测试（mock HTTP） |
| `tests/test_bilibili_subtitle.py` | **新建** | 字幕模块单元测试（纯函数） |
| `tests/manual_test_bili_subtitle.py` | **新建** | 端到端手动验证脚本（需启动 SignSrv + cookies） |
| `docs/bilibili_subtitle_usage.md` | **新建** | 使用文档（v1.0，2026-05-25） |

---

## Task 1: SignSrv HTTP 客户端 — `signsrv_client.py`

**Files:**
- Create: `src/you_get/util/signsrv_client.py`
- Test: `tests/test_signsrv_client.py`

- [ ] **Step 1.1: 写失败测试 — `is_signsrv_available` 成功路径**

文件：`tests/test_signsrv_client.py`（新建）

```python
#!/usr/bin/env python

import json
import unittest
from unittest.mock import patch, MagicMock

from you_get.util.signsrv_client import (
    is_signsrv_available,
    call_bilibili_sign,
    DEFAULT_SIGN_SRV_URL,
)


class TestIsSignsrvAvailable(unittest.TestCase):

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_true_when_pong_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"biz_code": 0, "data": {"message": "pong"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertTrue(is_signsrv_available())

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_false_on_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("connection refused")
        self.assertFalse(is_signsrv_available())

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_false_on_bad_biz_code(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"biz_code": 1, "msg": "err"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        self.assertFalse(is_signsrv_available())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: 运行测试，确认失败**

```bash
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
venv/bin/python -m unittest tests.test_signsrv_client -v
```

Expected: `ModuleNotFoundError: No module named 'you_get.util.signsrv_client'`

- [ ] **Step 1.3: 写最小实现 — `signsrv_client.py`**

文件：`src/you_get/util/signsrv_client.py`（新建）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""SignSrv HTTP 客户端。

依赖外部服务 MediaCrawlerPro-SignSrv，地址通过环境变量 SIGN_SRV_URL 配置，
默认 http://127.0.0.1:8989。所有失败返回 None/False，不抛异常。
"""

import json
import logging
import os
from typing import Dict, Optional
from urllib import request

logger = logging.getLogger(__name__)

DEFAULT_SIGN_SRV_URL = "http://127.0.0.1:8989"


def _get_sign_srv_url() -> str:
    return os.environ.get("SIGN_SRV_URL", DEFAULT_SIGN_SRV_URL).rstrip("/")


def is_signsrv_available(timeout: float = 1.0) -> bool:
    """GET /signsrv/pong，200 且 biz_code=0 视为可用。"""
    url = f"{_get_sign_srv_url()}/signsrv/pong"
    try:
        with request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("biz_code") == 0
    except Exception as e:
        logger.debug(f"[SignSrv] healthcheck failed: {e}")
        return False


def call_bilibili_sign(req_data: Dict, cookies: str, timeout: float = 5.0) -> Optional[Dict]:
    """POST /signsrv/v1/bilibili/sign。

    成功返回 {"wts": str, "w_rid": str}；任何失败返回 None。
    """
    url = f"{_get_sign_srv_url()}/signsrv/v1/bilibili/sign"
    payload = json.dumps({"req_data": req_data, "cookies": cookies}).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                logger.error(f"[SignSrv] http {resp.status}")
                return None
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("biz_code") != 0:
                logger.error(f"[SignSrv] biz_code={data.get('biz_code')} msg={data.get('msg')}")
                return None
            return data.get("data")
    except Exception as e:
        logger.error(f"[SignSrv] sign request failed: {e}")
        return None
```

- [ ] **Step 1.4: 运行测试，确认 healthcheck 测试通过**

```bash
venv/bin/python -m unittest tests.test_signsrv_client.TestIsSignsrvAvailable -v
```

Expected: 3 tests PASS

- [ ] **Step 1.5: 追加 `call_bilibili_sign` 测试**

追加到 `tests/test_signsrv_client.py`：

```python
class TestCallBilibiliSign(unittest.TestCase):

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_wts_and_wrid_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "biz_code": 0,
            "msg": "success",
            "data": {"wts": "1779701373", "w_rid": "abc123"},
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = call_bilibili_sign({"aid": "1", "cid": "2"}, "SESSDATA=xx")
        self.assertEqual(result, {"wts": "1779701373", "w_rid": "abc123"})

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_none_on_biz_code_error(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"biz_code": 500, "msg": "err"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertIsNone(call_bilibili_sign({"aid": "1", "cid": "2"}, "SESSDATA=xx"))

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        self.assertIsNone(call_bilibili_sign({"aid": "1"}, ""))
```

- [ ] **Step 1.6: 运行全部测试，确认通过**

```bash
venv/bin/python -m unittest tests.test_signsrv_client -v
```

Expected: 6 tests PASS

- [ ] **Step 1.7: 提交（由用户操作）**

```bash
# 等待用户确认后提交
git status
git diff src/you_get/util/signsrv_client.py tests/test_signsrv_client.py
```

提示用户检查 diff 后提交：
```bash
git add src/you_get/util/signsrv_client.py tests/test_signsrv_client.py
git commit -m "feat(util): add SignSrv HTTP client for bilibili sign"
```

---

## Task 2: SRT 转换纯函数 — `_json_to_srt`

**Files:**
- Create: `src/you_get/extractors/bilibili_subtitle.py`（先放纯函数，后续 task 追加 fetch_subtitles）
- Test: `tests/test_bilibili_subtitle.py`

- [ ] **Step 2.1: 写失败测试 — JSON→SRT 转换**

文件：`tests/test_bilibili_subtitle.py`（新建）

```python
#!/usr/bin/env python

import unittest

from you_get.extractors.bilibili_subtitle import (
    _json_to_srt,
    _is_ai_subtitle,
    _serialize_cookies,
)


class TestJsonToSrt(unittest.TestCase):

    def test_converts_simple_two_segments(self):
        bili_json = {
            "body": [
                {"from": 0.0, "to": 2.5, "content": "Hello"},
                {"from": 2.5, "to": 5.0, "content": "World"},
            ]
        }
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:02,500\n"
            "Hello\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:05,000\n"
            "World\n"
            "\n"
        )
        self.assertEqual(_json_to_srt(bili_json), expected)

    def test_handles_subsecond_precision(self):
        bili_json = {"body": [{"from": 12.345, "to": 67.891, "content": "x"}]}
        srt = _json_to_srt(bili_json)
        self.assertIn("00:00:12,345 --> 00:01:07,891", srt)

    def test_handles_hours(self):
        bili_json = {"body": [{"from": 3661.0, "to": 3662.0, "content": "long"}]}
        srt = _json_to_srt(bili_json)
        self.assertIn("01:01:01,000 --> 01:01:02,000", srt)

    def test_empty_body_returns_empty_string(self):
        self.assertEqual(_json_to_srt({"body": []}), "")

    def test_missing_body_returns_empty_string(self):
        self.assertEqual(_json_to_srt({}), "")

    def test_skips_segment_with_no_content(self):
        bili_json = {
            "body": [
                {"from": 0.0, "to": 1.0, "content": "ok"},
                {"from": 1.0, "to": 2.0},  # 缺 content
                {"from": 2.0, "to": 3.0, "content": ""},  # 空 content
            ]
        }
        srt = _json_to_srt(bili_json)
        self.assertIn("1\n", srt)
        self.assertNotIn("2\n", srt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2.2: 运行测试，确认失败**

```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle.TestJsonToSrt -v
```

Expected: `ModuleNotFoundError: No module named 'you_get.extractors.bilibili_subtitle'`

- [ ] **Step 2.3: 创建模块和最小实现**

文件：`src/you_get/extractors/bilibili_subtitle.py`（新建）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Bilibili CC 字幕（含 AI）抓取与转换。

依赖 MediaCrawlerPro-SignSrv 提供 wbi 签名。任何失败 log.w 后跳过，
不抛异常，不影响视频本体下载。
"""

import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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


def _seconds_to_srt_timestamp(t: float) -> str:
    """秒（float）转 SRT 时间戳 HH:MM:SS,mmm。"""
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:06.3f}".format(int(h), int(m), s).replace(".", ",")
```

- [ ] **Step 2.4: 运行测试，确认通过**

```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle.TestJsonToSrt -v
```

Expected: 6 tests PASS

---

## Task 3: AI 判定 + cookies 序列化纯函数

**Files:**
- Modify: `src/you_get/extractors/bilibili_subtitle.py`
- Test: `tests/test_bilibili_subtitle.py`

- [ ] **Step 3.1: 写失败测试 — `_is_ai_subtitle` 和 `_serialize_cookies`**

追加到 `tests/test_bilibili_subtitle.py`：

```python
class TestIsAiSubtitle(unittest.TestCase):

    def test_type_1_is_ai(self):
        self.assertTrue(_is_ai_subtitle({"type": 1, "lan": "zh-CN"}))

    def test_type_0_is_not_ai(self):
        self.assertFalse(_is_ai_subtitle({"type": 0, "lan": "zh-CN"}))

    def test_ai_type_positive_is_ai(self):
        self.assertTrue(_is_ai_subtitle({"type": 0, "ai_type": 1, "lan": "zh-CN"}))

    def test_lan_prefix_ai_dash_is_ai(self):
        self.assertTrue(_is_ai_subtitle({"lan": "ai-zh"}))

    def test_all_zero_no_prefix_is_not_ai(self):
        self.assertFalse(_is_ai_subtitle({"type": 0, "ai_type": 0, "lan": "en-US"}))


class TestSerializeCookies(unittest.TestCase):

    def test_dict_to_cookie_string(self):
        result = _serialize_cookies({"SESSDATA": "abc", "bili_jct": "xyz"})
        # 顺序不固定，分别检查
        self.assertIn("SESSDATA=abc", result)
        self.assertIn("bili_jct=xyz", result)
        self.assertIn("; ", result)

    def test_empty_dict_returns_empty_string(self):
        self.assertEqual(_serialize_cookies({}), "")

    def test_none_returns_empty_string(self):
        self.assertEqual(_serialize_cookies(None), "")

    def test_string_returned_as_is(self):
        self.assertEqual(_serialize_cookies("SESSDATA=abc; bili_jct=xyz"), "SESSDATA=abc; bili_jct=xyz")
```

- [ ] **Step 3.2: 运行测试，确认失败**

```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle.TestIsAiSubtitle tests.test_bilibili_subtitle.TestSerializeCookies -v
```

Expected: `ImportError: cannot import name '_is_ai_subtitle' ...`

- [ ] **Step 3.3: 在 `bilibili_subtitle.py` 追加实现**

在 `bilibili_subtitle.py` 末尾追加：

```python
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
    """把 cookies（dict / str / None）序列化成 'k=v; k=v' 字符串。"""
    if cookies is None:
        return ""
    if isinstance(cookies, str):
        return cookies
    if isinstance(cookies, dict):
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    # 兜底：返回空字符串，让调用方走 cookies 缺失分支
    return ""
```

- [ ] **Step 3.4: 运行测试，确认通过**

```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle -v
```

Expected: 15 tests PASS（6 srt + 5 ai + 4 cookies）

- [ ] **Step 3.5: 提交（用户操作）**

```bash
git status
git diff src/you_get/extractors/bilibili_subtitle.py tests/test_bilibili_subtitle.py
# 由用户确认后：
git add src/you_get/extractors/bilibili_subtitle.py tests/test_bilibili_subtitle.py
git commit -m "feat(bilibili): add pure helpers for subtitle (srt convert, ai detect, cookies serialize)"
```

---

## Task 4: `fetch_subtitles` 主流程

**Files:**
- Modify: `src/you_get/extractors/bilibili_subtitle.py`

- [ ] **Step 4.1: 在 `bilibili_subtitle.py` 顶部补 import**

修改 `src/you_get/extractors/bilibili_subtitle.py` 的 import 区，加：

```python
from you_get.util.signsrv_client import (
    is_signsrv_available,
    call_bilibili_sign,
    DEFAULT_SIGN_SRV_URL,
)
from ..common import get_content
```

- [ ] **Step 4.2: 追加 `fetch_subtitles` 实现**

在 `bilibili_subtitle.py` 末尾追加：

```python
BILIBILI_SUBTITLE_API = "https://api.bilibili.com/x/player/wbi/v2"


def fetch_subtitles(extractor, avid, cid, cookies) -> None:
    """抓取并填充 extractor.caption_tracks。

    任何失败（前置检查、签名、列表接口、单条字幕下载）都 log.w 后跳过对应步骤，
    不抛异常、不影响 caller。

    Args:
        extractor: 持有 caption_tracks dict 的 VideoExtractor 实例
        avid: 视频 aid（int 或 str 都接受）
        cid: 分 P 的 cid
        cookies: dict / str / None
    """
    cookie_str = _serialize_cookies(cookies)
    if not cookie_str:
        logger.warning("[Subtitle] 未提供 cookies，跳过字幕下载")
        return

    if not is_signsrv_available():
        import os
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
        logger.error(f"[Subtitle] 字幕列表接口返回错误 code={resp.get('code')} message={resp.get('message')}")
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
```

- [ ] **Step 4.3: 跑已有测试，确认未破坏纯函数**

```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle -v
```

Expected: 15 tests PASS（fetch_subtitles 没有单元测试，因为有 SignSrv + 网络外部依赖，留给 Task 6 e2e 验证）

- [ ] **Step 4.4: 提交（用户操作）**

```bash
git status
git diff src/you_get/extractors/bilibili_subtitle.py
# 由用户确认后：
git add src/you_get/extractors/bilibili_subtitle.py
git commit -m "feat(bilibili): implement fetch_subtitles main flow"
```

---

## Task 5: 集成到 `bilibili.py` 三处

**Files:**
- Modify: `src/you_get/extractors/bilibili.py`

- [ ] **Step 5.1: 先看 3 处 cid 的上下文**

```bash
grep -n "# get danmaku" src/you_get/extractors/bilibili.py
```

Expected 输出 3 行：
```
337:            # get danmaku
416:            # get danmaku
598:        # get danmaku
```

- [ ] **Step 5.2: 在文件顶部 import**

修改 `src/you_get/extractors/bilibili.py`，在 `from ..extractor import VideoExtractor` 之后加：

```python
from .bilibili_subtitle import fetch_subtitles
from ..common import cookies
```

（确认 `you_get.common.cookies` 是全局加载的 cookiejar；如果是 CookieJar 类型，下一步要转 dict 或 str）

- [ ] **Step 5.3: 确认 `cookies` 全局变量类型**

```bash
grep -n "^cookies = \|^cookies=" src/you_get/common.py | head -5
grep -n "def load_cookies" src/you_get/common.py
```

预期：`cookies` 通过 `load_cookies()` 设置。读 `load_cookies` 函数（约 `common.py:200-260` 区间）确认它是 `CookieJar` 还是 `dict`。

如果是 `CookieJar`，在 `bilibili_subtitle.py` 的 `_serialize_cookies` 里加一个 isinstance 分支：

```python
def _serialize_cookies(cookies) -> str:
    if cookies is None:
        return ""
    if isinstance(cookies, str):
        return cookies
    if isinstance(cookies, dict):
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    # CookieJar 兼容
    try:
        from http.cookiejar import CookieJar
        if isinstance(cookies, CookieJar):
            return "; ".join(f"{c.name}={c.value}" for c in cookies)
    except Exception:
        pass
    return ""
```

如果加了 CookieJar 分支，**同时**在 `tests/test_bilibili_subtitle.py` 的 `TestSerializeCookies` 追加：

```python
def test_cookiejar_to_string(self):
    from http.cookiejar import CookieJar, Cookie
    jar = CookieJar()
    jar.set_cookie(Cookie(
        version=0, name="SESSDATA", value="abc",
        port=None, port_specified=False,
        domain=".bilibili.com", domain_specified=True, domain_initial_dot=True,
        path="/", path_specified=True, secure=False, expires=None,
        discard=False, comment=None, comment_url=None, rest={},
    ))
    result = _serialize_cookies(jar)
    self.assertEqual(result, "SESSDATA=abc")
```

跑测试：
```bash
venv/bin/python -m unittest tests.test_bilibili_subtitle -v
```

Expected: 16 tests PASS（新增一个 cookiejar 测试）

- [ ] **Step 5.4: 修改普通视频分支（约 338 行）**

定位 `# get danmaku`（出现 3 次中的第 1 次，在普通视频分支）：

```bash
sed -n '335,342p' src/you_get/extractors/bilibili.py
```

预期：
```python
                cid = initial_state['videoData']['pages'][p - 1]['cid']  # ...
            # get danmaku
            self.danmaku = get_content('https://comment.bilibili.com/%s.xml' % cid, headers=self.bilibili_headers(referer=self.url))
```

用 Edit 工具替换为：
```python
            # get danmaku
            self.danmaku = get_content('https://comment.bilibili.com/%s.xml' % cid, headers=self.bilibili_headers(referer=self.url))
            # get subtitles (via SignSrv)
            fetch_subtitles(self, avid, cid, cookies)
```

- [ ] **Step 5.5: 修改番剧分支（约 417 行）**

同理，第 2 次 `# get danmaku`：

```bash
sed -n '414,420p' src/you_get/extractors/bilibili.py
```

用 Edit 替换为同样的模式：在 `self.danmaku = ...` 行之后追加：
```python
            # get subtitles (via SignSrv)
            fetch_subtitles(self, avid, cid, cookies)
```

- [ ] **Step 5.6: 修改 festival 分支（约 599 行）**

第 3 次 `# get danmaku`：

```bash
sed -n '596,602p' src/you_get/extractors/bilibili.py
```

注意此处缩进可能与前两处不同（spec §6.3 列出 598，是更浅缩进）。读出来核对缩进，再 Edit 加入：
```python
        # get subtitles (via SignSrv)
        fetch_subtitles(self, avid, cid, cookies)
```

- [ ] **Step 5.7: 跑全部单测确认未破坏**

```bash
venv/bin/python -m unittest discover tests -v
```

Expected: 全部已有测试 + 新增测试都 PASS。

- [ ] **Step 5.8: 静态语法检查（确保 import 不报错）**

```bash
venv/bin/python -c "from you_get.extractors.bilibili import Bilibili; print('ok')"
```

Expected: `ok`

- [ ] **Step 5.9: 提交（用户操作）**

```bash
git status
git diff src/you_get/extractors/bilibili.py
# 由用户确认后：
git add src/you_get/extractors/bilibili.py src/you_get/extractors/bilibili_subtitle.py tests/test_bilibili_subtitle.py
git commit -m "feat(bilibili): integrate subtitle fetching into bilibili extractor"
```

---

## Task 6: 端到端实测脚本 + AI 判定字段校准

**Files:**
- Create: `tests/manual_test_bili_subtitle.py`

- [ ] **Step 6.1: 写 manual 脚本**

文件：`tests/manual_test_bili_subtitle.py`（新建）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""手动 e2e 验证脚本。

用法：
    1. 启动 SignSrv：
       cd ../MediaCrawlerPro-SignSrv && venv/bin/python app.py &
    2. 准备 cookies.txt（Netscape 格式，含 SESSDATA）
    3. 运行：
       python tests/manual_test_bili_subtitle.py \\
           --cookies ~/bili_cookies.txt \\
           --bv BV1xx411c7us

验证点：
    [v1] SignSrv 在线 + 视频有字幕：caption_tracks 被填充，打印每条 lan/key/前 3 行 SRT
    [v2] SignSrv 离线：log.w + caption_tracks 为空
    [v3] cookies 为空：log.w + caption_tracks 为空
    [v4] 无字幕视频：log "无可用字幕" + caption_tracks 为空

打印 subtitles[] 原始字段供 spec §4.3 AI 判定规则校准。
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# 让脚本能从 you-get 根目录跑
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from you_get.common import load_cookies, cookies as global_cookies
from you_get.extractors.bilibili_subtitle import fetch_subtitles, _serialize_cookies


class FakeExtractor:
    def __init__(self):
        self.caption_tracks = {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies", required=False, help="Netscape cookies.txt 路径")
    parser.add_argument("--bv", required=True, help="BV 号或视频 URL")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="[%(levelname)s] %(message)s")

    if args.cookies:
        load_cookies(args.cookies)
    cookies = global_cookies  # CookieJar 或 None

    # 解析 BV → aid/cid
    aid, cid = resolve_bv_to_aid_cid(args.bv, _serialize_cookies(cookies))
    print(f"aid={aid} cid={cid}")

    ext = FakeExtractor()
    fetch_subtitles(ext, aid, cid, cookies)

    print(f"\n=== 抓取到 {len(ext.caption_tracks)} 条字幕 ===")
    for key, srt in ext.caption_tracks.items():
        print(f"\n--- {key} ---")
        print("\n".join(srt.splitlines()[:6]))


def resolve_bv_to_aid_cid(bv_or_url: str, cookie_str: str):
    """从 BV 号或 URL 拿 aid/cid（用 initial_state）。"""
    from urllib import request
    import gzip, re

    if bv_or_url.startswith("http"):
        url = bv_or_url
    else:
        url = f"https://www.bilibili.com/video/{bv_or_url}/"

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
        raise RuntimeError("找不到 __INITIAL_STATE__")
    data = json.loads(m.group(1))
    aid = data.get("aid")
    vd = data.get("videoData") or {}
    cid = vd.get("cid") or (vd.get("pages") or [{}])[0].get("cid")
    return aid, cid


if __name__ == "__main__":
    main()
```

- [ ] **Step 6.2: 启动 SignSrv（独立终端或后台）**

```bash
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/MediaCrawlerPro-SignSrv
venv/bin/python app.py > /tmp/signsrv.log 2>&1 &
echo $! > /tmp/signsrv.pid
sleep 4
curl -s http://127.0.0.1:8989/signsrv/pong
```

Expected: `{"biz_code":0,"msg":"OK!","isok":true,"data":{"message":"pong"}}`

- [ ] **Step 6.3: 跑 v1（有 cookies + 有字幕的 BV）**

⚠️ 这一步需要用户**提供一个有 AI 字幕的 BV 号**（如知识区/纪录片视频，外国 MV 通常没字幕）和 cookies.txt 路径。

```bash
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
venv/bin/python tests/manual_test_bili_subtitle.py \
    --cookies ~/bili_cookies.txt \
    --bv <用户提供的 BV>
```

Expected：
- 打印 aid、cid
- 打印若干 `[INFO] [Subtitle] 已抓取 xxx`
- 打印每条字幕的前 6 行 SRT 内容

**关键校准**：如果字幕被识别成 AI 但应该是 UP 上传，或反之，需打开 `bilibili_subtitle.py` 修改 `_is_ai_subtitle`，再回到 tests 补充对应 case。

- [ ] **Step 6.4: 跑 v2（关掉 SignSrv 验证 warn skip）**

```bash
kill $(cat /tmp/signsrv.pid)
rm /tmp/signsrv.pid
venv/bin/python tests/manual_test_bili_subtitle.py --cookies ~/bili_cookies.txt --bv <BV>
```

Expected: `[WARNING] [Subtitle] SignSrv 不可达 ...，跳过字幕下载` + `抓取到 0 条字幕`

- [ ] **Step 6.5: 跑 v3（不传 cookies 验证 warn skip）**

```bash
venv/bin/python tests/manual_test_bili_subtitle.py --bv <BV>
```

Expected: `[WARNING] [Subtitle] 未提供 cookies，跳过字幕下载`

- [ ] **Step 6.6: 跑 v4（无字幕的 BV）**

```bash
# 重启 SignSrv
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/MediaCrawlerPro-SignSrv
venv/bin/python app.py > /tmp/signsrv.log 2>&1 &
echo $! > /tmp/signsrv.pid
sleep 4
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
venv/bin/python tests/manual_test_bili_subtitle.py --cookies ~/bili_cookies.txt --bv BV1GJ411x7h7
```

Expected: `[INFO] [Subtitle] 该视频无可用字幕` + `抓取到 0 条字幕`

- [ ] **Step 6.7: 关掉 SignSrv，清理**

```bash
kill $(cat /tmp/signsrv.pid) 2>/dev/null
rm -f /tmp/signsrv.pid /tmp/signsrv.log
```

- [ ] **Step 6.8: 跑 you-get 命令真实下载验证（端到端）**

```bash
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/MediaCrawlerPro-SignSrv
venv/bin/python app.py > /tmp/signsrv.log 2>&1 &
echo $! > /tmp/signsrv.pid
sleep 4
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
mkdir -p /tmp/youget-subtitle-test
venv/bin/python -m you_get \
    --disable-kuaidaili-proxy \
    --cookies ~/bili_cookies.txt \
    -n -o /tmp/youget-subtitle-test \
    --format=dash-flv360-HEVC \
    https://www.bilibili.com/video/<带字幕的BV>/
ls -la /tmp/youget-subtitle-test/
kill $(cat /tmp/signsrv.pid) 2>/dev/null
rm -f /tmp/signsrv.pid /tmp/signsrv.log
```

Expected: 目录下有 `{title}.zh-CN.srt` 或 `{title}.ai-zh-CN.srt` 等文件。

- [ ] **Step 6.9: 提交（用户操作）**

```bash
git status
git diff tests/manual_test_bili_subtitle.py
# 用户确认后：
git add tests/manual_test_bili_subtitle.py
git commit -m "test(bilibili): add manual e2e test script for subtitle"
```

如 Step 6.3 触发了 `_is_ai_subtitle` 修正，一并 commit。

---

## Task 7: 写使用文档

**Files:**
- Create: `docs/bilibili_subtitle_usage.md`

- [ ] **Step 7.1: 写文档**

文件：`docs/bilibili_subtitle_usage.md`（新建）

```markdown
# you-get 下载 Bilibili 字幕（含 AI 字幕）使用说明

- **版本**: v1.0
- **更新时间**: 2026-05-25
- **依赖**: MediaCrawlerPro-SignSrv（提供 wbi 签名）

## 前置条件

| 项 | 说明 |
|---|---|
| MediaCrawlerPro-SignSrv 运行中 | 默认地址 `http://127.0.0.1:8989`，可用 env `SIGN_SRV_URL` 覆盖 |
| 登录 cookies（Netscape 格式） | `--cookies cookies.txt` |
| 网络可直连 B 站 | `--disable-kuaidaili-proxy` 关掉失效的默认快代理 |

## 启动 SignSrv

\`\`\`bash
cd /path/to/MediaCrawlerPro-SignSrv
venv/bin/python app.py  # 监听 8989
\`\`\`

## 下载命令

\`\`\`bash
cd /path/to/you-get
source venv/bin/activate
./you-get --disable-kuaidaili-proxy --cookies ~/bili_cookies.txt \\
    https://www.bilibili.com/video/BVxxxxxx/
\`\`\`

## 产出文件

| 文件 | 说明 |
|---|---|
| `{title}.zh-CN.srt` | UP 上传中文字幕 |
| `{title}.en-US.srt` | UP 上传英文字幕 |
| `{title}.ai-zh-CN.srt` | AI 自动生成中文字幕 |
| `{title}.ai-en-US.srt` | AI 自动生成英文字幕 |

## 失败行为

字幕是增量功能，任何字幕相关失败都**不会**中断视频下载，只 warn 后跳过：

| 场景 | 表现 |
|---|---|
| SignSrv 未启动 | `[WARNING] [Subtitle] SignSrv 不可达 (...)，跳过字幕下载` |
| cookies 未传 | `[WARNING] [Subtitle] 未提供 cookies，跳过字幕下载` |
| 视频本身无字幕 | `[INFO] [Subtitle] 该视频无可用字幕` |
| 单条字幕下载失败 | `[WARNING] [Subtitle] 下载 xx 字幕 JSON 失败: ...`，其他字幕继续 |

## 关闭字幕下载

复用现有 `--no-caption`：
\`\`\`bash
./you-get --no-caption ...
\`\`\`
此选项同时关闭弹幕和字幕。

## 关联文档
- 设计 spec: `docs/superpowers/specs/2026-05-25-bili-subtitle-design.md`
- 实现 plan: `docs/superpowers/plans/2026-05-25-bili-subtitle.md`
- 不合并音视频用法: `docs/bilibili_no_merge_usage.md`
```

- [ ] **Step 7.2: 提交（用户操作）**

```bash
git status
git add docs/bilibili_subtitle_usage.md
git commit -m "docs(bilibili): add subtitle usage guide"
```

---

## 完成 checklist

实现完成后核对：

- [ ] 单元测试：`venv/bin/python -m unittest discover tests -v` 全 PASS（含原有用例）
- [ ] 端到端：Task 6 v1-v4 + Step 6.8 全部按 Expected 输出
- [ ] 文件清单：
  - `src/you_get/util/signsrv_client.py` 存在
  - `src/you_get/extractors/bilibili_subtitle.py` 存在
  - `src/you_get/extractors/bilibili.py` 三处 cid 旁有 `fetch_subtitles(self, avid, cid, cookies)`
  - `tests/test_signsrv_client.py`、`tests/test_bilibili_subtitle.py`、`tests/manual_test_bili_subtitle.py` 存在
  - `docs/bilibili_subtitle_usage.md` 存在
- [ ] AI 判定逻辑（spec §4.3 校准点）已在 Task 6 实测中校准
- [ ] 关闭 SignSrv 时 you-get 不抛错、视频仍能下载（Task 6 Step 6.4 / 6.8 验证）

## 已知后续改进点（不在本 plan 范围）

- `kuaidaili_proxy.py` 硬编码兜底（违反 "不要写保底代码" 规则）— 已在 `docs/bilibili_no_merge_usage.md` §6 记录，下次单独处理
- `--no-subtitle` 独立 CLI 开关 — 当前复用 `--no-caption`，若实际使用觉得不够细可再加
