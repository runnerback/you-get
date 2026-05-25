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
                {"from": 1.0, "to": 2.0},
                {"from": 2.0, "to": 3.0, "content": ""},
            ]
        }
        srt = _json_to_srt(bili_json)
        self.assertIn("1\n", srt)
        self.assertNotIn("2\n", srt)


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
        self.assertIn("SESSDATA=abc", result)
        self.assertIn("bili_jct=xyz", result)
        self.assertIn("; ", result)

    def test_empty_dict_returns_empty_string(self):
        self.assertEqual(_serialize_cookies({}), "")

    def test_none_returns_empty_string(self):
        self.assertEqual(_serialize_cookies(None), "")

    def test_string_returned_as_is(self):
        self.assertEqual(
            _serialize_cookies("SESSDATA=abc; bili_jct=xyz"),
            "SESSDATA=abc; bili_jct=xyz",
        )

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


if __name__ == "__main__":
    unittest.main()
