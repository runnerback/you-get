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
        mock_resp.read.return_value = json.dumps({
            "biz_code": 0, "data": {"message": "pong"}
        }).encode("utf-8")
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
        mock_resp.read.return_value = json.dumps({
            "biz_code": 500, "msg": "err"
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        self.assertIsNone(call_bilibili_sign({"aid": "1", "cid": "2"}, "SESSDATA=xx"))

    @patch("you_get.util.signsrv_client.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        self.assertIsNone(call_bilibili_sign({"aid": "1"}, ""))


if __name__ == "__main__":
    unittest.main()
