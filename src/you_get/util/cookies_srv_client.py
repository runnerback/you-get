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
