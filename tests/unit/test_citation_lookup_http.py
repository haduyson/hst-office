# SPDX-License-Identifier: AGPL-3.0-only
"""The HTTPS helper of the online lookup: only the allowed hosts over HTTPS, no header injection, and a
User-Agent without any address."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_lookup_http as http


class Helper(unittest.TestCase):
    def test_url_rules(self):
        self.assertTrue(http.allowed("https://doi.org/10.1/x"))
        for url in ("http://doi.org/10.1/x", "https://evil.example/x", "https://doi.org.evil.example/",
                    "https://user@doi.org/x", "https://doi.org:8443/x", "file:///etc/passwd"):
            self.assertFalse(http.allowed(url), url)
        with self.assertRaises(ValueError):
            http.get("https://evil.example/", "application/json", "1.0.2")
        with self.assertRaises(ValueError):
            http.get("https://doi.org/10.1/x", "application/json", "1.0.2\r\nX-Injected: 1")

    def test_user_agent_has_no_address(self):
        seen = []

        class Opener:
            def open(self, request, timeout):
                seen.append(dict(request.header_items()))
                raise OSError("offline test")
        original = http.urllib.request.build_opener
        http.urllib.request.build_opener = lambda *handlers: Opener()
        try:
            with self.assertRaises(OSError):
                http.get("https://doi.org/10.1/x", "application/json", "1.0.2")
        finally:
            http.urllib.request.build_opener = original
        self.assertEqual(seen[0]["User-agent"], "HSTOffice/1.0.2")


if __name__ == "__main__":
    unittest.main()
