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
    """GET /signsrv/pong，HTTP 200 且 biz_code=0 视为可用。"""
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
