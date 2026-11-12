# SPDX-License-Identifier: AGPL-3.0-only
"""The display report's POST through the private helper: headers, no redirects, status as the answer, deadline."""
import json
import unittest
from unittest import mock
import urllib.error

import _paths  # noqa: F401 - makes the extension package importable
from hst_office import banner_fetch, banner_http

URL = "https://system.hasontech.vn/hst-office/impressions"
BODY = b'{"schemaVersion":1,"release":"1.0.2","days":[{"day":"2026-11-12","counts":{"aios":3}}]}'


class HelperPostTest(unittest.TestCase):
    def opener(self, status=204):
        response = mock.MagicMock(status=status)
        response.__enter__.return_value = response
        opener = mock.Mock()
        opener.open.return_value = response
        return opener

    def test_json_post_carries_only_the_plain_user_agent(self):
        opener = self.opener()
        with mock.patch.object(banner_http.urllib.request, "build_opener", return_value=opener) as build:
            self.assertEqual(banner_http.post_status(URL, BODY.decode(), "1.0.2"), 204)
        sent = opener.open.call_args[0][0]
        self.assertEqual(sent.get_method(), "POST")
        self.assertEqual(sent.full_url, URL)
        self.assertEqual(sent.data, BODY)
        self.assertEqual(sent.get_header("User-agent"), "HSTOffice/1.0.2")
        self.assertEqual(sent.get_header("Content-type"), "application/json")
        self.assertIsNone(sent.get_header("Cookie"))
        self.assertIsNone(sent.get_header("Referer"))
        self.assertTrue(any(isinstance(h, banner_http._NoRedirect) for h in build.call_args[0]))

    def test_error_status_is_an_answer(self):
        for code in (400, 413, 429, 503):
            opener = mock.Mock()
            opener.open.side_effect = urllib.error.HTTPError(URL, code, "x", {}, None)
            with mock.patch.object(banner_http.urllib.request, "build_opener", return_value=opener):
                self.assertEqual(banner_http.post_status(URL, BODY.decode(), "1.0.2"), code)

    def test_refuses_plain_http_and_oversized_bodies(self):
        with self.assertRaises(ValueError):
            banner_http.post_status("http://system.hasontech.vn/hst-office/impressions", BODY.decode(), "1.0.2")
        with self.assertRaises(ValueError):
            banner_http.post_status(URL, "x" * 8193, "1.0.2")

    def test_main_dispatches_the_post(self):
        stdin = json.dumps({"post": True, "url": URL, "body": BODY.decode(), "version": "1.0.2", "proxy": None})
        out = mock.MagicMock()
        with mock.patch.object(banner_http, "post_status", return_value=204) as post, \
                mock.patch.object(banner_http.sys, "stdin", mock.Mock(buffer=mock.Mock(read=lambda n: stdin.encode()))), \
                mock.patch.object(banner_http.sys, "stdout", mock.Mock(buffer=out)):
            self.assertEqual(banner_http.main(), 0)
        post.assert_called_once_with(url=URL, body=BODY.decode(), version="1.0.2", proxy=None)
        out.write.assert_called_once_with(b"204")


class SupervisorPostTest(unittest.TestCase):
    def test_request_goes_to_the_helper_with_the_five_second_deadline(self):
        with mock.patch.object(banner_fetch, "_run", return_value=b"204") as run:
            self.assertEqual(banner_fetch.post_status(URL, BODY, "1.0.2", {"https": "proxy:8080"}), 204)
        payload, timeout = run.call_args[0]
        self.assertEqual(timeout, banner_fetch.TIMEOUT)
        self.assertEqual(timeout, 5)
        self.assertEqual(json.loads(payload), {"post": True, "url": URL, "body": BODY.decode(), "version": "1.0.2",
                                               "proxy": {"https": "proxy:8080"}})

    def test_invalid_requests_never_start_the_helper(self):
        with mock.patch.object(banner_fetch, "_run") as run:
            for args in (("http://system.hasontech.vn/x", BODY), (URL, b""), (URL, b"x" * 8193), (URL, "text"),
                         (URL, "é".encode())):
                with self.assertRaises(ValueError):
                    banner_fetch.post_status(args[0], args[1], "1.0.2")
            with self.assertRaises(ValueError):
                banner_fetch.post_status(URL, BODY, "1.0.2\r\nX-Evil: 1")
        run.assert_not_called()

    def test_deadline_error_reaches_the_caller(self):
        with mock.patch.object(banner_fetch, "_run", side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                banner_fetch.post_status(URL, BODY, "1.0.2")


if __name__ == "__main__":
    unittest.main()
