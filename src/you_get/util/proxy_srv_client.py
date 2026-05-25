#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MediaCrawlerPro-Python 资源服务代理客户端。

通过环境变量 RESOURCE_SRV_URL 配置资源服务地址，默认 http://127.0.0.1:8990。
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


def fetch_proxy_url(timeout: float = 3.0) -> Optional[str]:
    """从资源服务拉一个可用代理 URL。

    成功返回 'http://user:pwd@ip:port' 字符串；任何失败返回 None。
    """
    url = f"{_get_resource_srv_url()}/api/v1/proxy/kuaidaili"
    try:
        with request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning(f"[ProxySrv] http {resp.status}")
                return None
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("proxy_url")
    except Exception as e:
        logger.warning(f"[ProxySrv] fetch proxy failed: {e}")
        return None
