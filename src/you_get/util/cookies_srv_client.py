#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MediaCrawlerPro-Python 资源服务 cookies 客户端。

通过环境变量 RESOURCE_SRV_URL 配置地址，默认 http://127.0.0.1:8990。
任何失败返回 None，不抛异常。
"""

import json
import logging
import os
from typing import Optional
from urllib import request

logger = logging.getLogger(__name__)

DEFAULT_RESOURCE_SRV_URL = "http://127.0.0.1:8990"


def _get_resource_srv_url() -> str:
    return os.environ.get("RESOURCE_SRV_URL", DEFAULT_RESOURCE_SRV_URL).rstrip("/")


def fetch_cookies(platform: str, timeout: float = 3.0) -> Optional[str]:
    """从资源服务拉一条可用 cookies 字符串。

    成功返回 cookies 字符串；任何失败（HTTP 错、404、网络错）返回 None。
    """
    url = f"{_get_resource_srv_url()}/api/v1/{platform}/cookies"
    try:
        with request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning(f"[CookiesSrv] http {resp.status} for {platform}")
                return None
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("cookies")
    except Exception as e:
        logger.warning(f"[CookiesSrv] fetch {platform} cookies failed: {e}")
        return None


# 平台 → 默认 cookie domain（用于把字符串 cookies 注入 CookieJar）
_PLATFORM_DOMAIN = {
    "bili": ".bilibili.com",
    "xhs": ".xiaohongshu.com",
    "dy": ".douyin.com",
    "ks": ".kuaishou.com",
    "wb": ".weibo.com",
    "tieba": ".baidu.com",
    "zhihu": ".zhihu.com",
}


def inject_global_cookies(platform: str) -> bool:
    """把资源服务的 cookies 字符串注入 you_get.common.cookies 全局变量。

    流程：
    1. 若全局 cookies 已存在（用户传了 --cookies）→ 跳过，返回 True
    2. 从资源服务拉字符串 → 解析 → 构造 MozillaCookieJar → 赋值
    3. 任一步失败 log.w 后返回 False，不抛异常

    这样 you-get 主流程（清晰度解析、字幕、其他平台请求）都能用上这份 cookies。
    """
    from http.cookiejar import Cookie, MozillaCookieJar

    from you_get import common as _common

    if _common.cookies is not None:
        return True  # 用户已 --cookies，不覆盖

    cookie_str = fetch_cookies(platform)
    if not cookie_str:
        return False

    domain = _PLATFORM_DOMAIN.get(platform, "")
    if not domain:
        logger.warning(f"[CookiesSrv] 未知平台 {platform}，无法注入 cookies")
        return False

    jar = MozillaCookieJar()
    for kv in cookie_str.split(";"):
        kv = kv.strip()
        if not kv or "=" not in kv:
            continue
        name, value = kv.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            continue
        jar.set_cookie(Cookie(
            version=0, name=name, value=value,
            port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=domain.startswith("."),
            path="/", path_specified=True,
            secure=False, expires=None, discard=False,
            comment=None, comment_url=None, rest={},
        ))

    _common.cookies = jar
    logger.info(f"[CookiesSrv] 已注入 {platform} cookies 到全局（{len(jar)} 个键）")
    return True
