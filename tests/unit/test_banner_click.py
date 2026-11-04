# SPDX-License-Identifier: AGPL-3.0-only
"""Banner click destination with a stubbed probe, and the real helper's HEAD against a stub opener."""
import unittest
from unittest import mock
import urllib.error

import _paths  # noqa: F401 - makes the extension package importable
from hst_office import banner_click, banner_fetch, banner_http

UTM = {"source": "hst-office", "campaign": "hst-office-1-0"}
QUERY = "?utm_source=hst-office&utm_medium=banner&utm_campaign=hst-office-1-0"
COUNTED = "https://system.hasontech.vn/hst-office/go/aios" + QUERY
HOME = "https://hasontech.vn" + QUERY


class DestinationTest(unittest.TestCase):
    def destination(self, url=COUNTED, **probe):
        stub = mock.Mock(**probe)
        with mock.patch.object(banner_click, "PROBE", stub):
            return banner_click.destination(url, UTM, "1.0.0", {"https": "proxy:8080"}), stub

    def test_reachable_opens_click_url(self):
        self.assertEqual(self.destination(return_value=200)[0], COUNTED)

    def test_status_below_500_counts_as_reachable(self):
        self.assertEqual(self.destination(return_value=404)[0], COUNTED)

    def test_connection_failure_goes_home(self):
        self.assertEqual(self.destination(side_effect=OSError("refused"))[0], HOME)

    def test_503_goes_home(self):
        self.assertEqual(self.destination(return_value=503)[0], HOME)

    def test_timeout_goes_home(self):
        self.assertEqual(self.destination(side_effect=TimeoutError())[0], HOME)

    def test_other_host_opens_directly_without_probe(self):
        url = "https://aios.hasontech.vn" + QUERY
        result, stub = self.destination(url=url, return_value=503)
        self.assertEqual(result, url)
        stub.assert_not_called()

    def test_probe_is_the_manifest_never_the_counted_link(self):
        _, stub = self.destination(return_value=200)
        stub.assert_called_once_with("https://system.hasontech.vn/hst-office/banners.json", "1.0.0",
                                     {"https": "proxy:8080"})


class ProbeTest(unittest.TestCase):
    def test_deadline_is_short(self):
        self.assertLessEqual(banner_fetch.PROBE_TIMEOUT, 1.5)

    def test_head_request_carries_only_the_plain_user_agent(self):
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(banner_http.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(banner_http.head_status("https://system.hasontech.vn/hst-office/banners.json", "1.0.0"), 200)
        sent = opener.open.call_args[0][0]
        self.assertEqual(sent.get_method(), "HEAD")
        self.assertEqual(sent.get_header("User-agent"), "HSTOffice/1.0.0")
        self.assertIsNone(sent.get_header("Cookie"))
        self.assertEqual(sent.full_url, "https://system.hasontech.vn/hst-office/banners.json")

    def test_error_status_is_an_answer(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://x", 503, "down", {}, None)
        with mock.patch.object(banner_http.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(banner_http.head_status("https://system.hasontech.vn/x", "1.0.0"), 503)

    def test_deadline_error_reaches_the_caller(self):
        with mock.patch.object(banner_fetch, "_run", side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                banner_fetch.head_status("https://system.hasontech.vn/x", "1.0.0")


if __name__ == "__main__":
    unittest.main()
