# SPDX-License-Identifier: AGPL-3.0-only
"""Manifest and URL rules of the update check (split from test_update_check.py, whose helpers it reuses)."""
import json
import unittest

import _paths  # noqa: F401
from hst_office import update_fetch as fetch
from hst_office import update_logic as logic
from test_update_check import TEST_PUBLIC, manifest, release, signed


class ManifestRules(unittest.TestCase):
    def test_rejects_malformed(self):
        bad_links = dict(release("1.0.0"), notes="http://office.hasontech.vn/")
        cases = [b"not json", b"[]", json.dumps({"schema": 4, "channels": {}}).encode(),
                 manifest(stable=dict(release("1.0.0"), version="1.0")), manifest(stable=bad_links),
                 manifest(stable=dict(release("1.0.0"), downloads={"windows": "https://evil.example/x"})),
                 manifest(stable=dict(release("1.0.0"), downloads={"amiga": "https://office.hasontech.vn/x"})),
                 manifest(stable=dict(release("1.0.0"), critical="yes")), manifest(stable=dict(release("1.0.0"), date="30/10"))]
        for data in cases:
            with self.subTest(data[:60]), self.assertRaises(logic.ManifestError):
                logic.parse_manifest(data)

    def test_signature_required_and_bound_to_bytes(self):
        data = manifest(beta=release("1.0.0"))
        sig = signed(data)
        self.assertEqual(fetch.verify_manifest(data, sig, TEST_PUBLIC)["beta"]["version"], "1.0.0")
        tampered = data.replace(b"1.0.0", b"9.9.9")
        for bad_data, bad_sig in ((tampered, sig), (data, ""), (data, "not base64!"), (data, signed(data, bytes(32)))):
            with self.assertRaises(fetch.UpdateError):
                fetch.verify_manifest(bad_data, bad_sig, TEST_PUBLIC)
        with self.assertRaises(fetch.UpdateError):  # test-key signature is not accepted by the built-in key
            fetch.verify_manifest(data, sig)


class UrlRules(unittest.TestCase):
    def test_fetch_url_https_and_host_only(self):
        self.assertTrue(logic.is_fetch_url(logic.MANIFEST_URL))
        for bad in ("http://office.hasontech.vn/update/latest.json", "https://evil.example/latest.json",
                    "https://office.hasontech.vn.evil.example/x", "https://user@office.hasontech.vn/x",
                    "https://office.hasontech.vn:8443/x", "ftp://office.hasontech.vn/x", "file:///etc/passwd",
                    "https://office.hasontech.vn/a b", "http://127.0.0.1:8000/latest.json"):
            with self.subTest(bad):
                self.assertFalse(logic.is_fetch_url(bad))
        self.assertTrue(logic.is_fetch_url("http://127.0.0.1:8000/latest.json", allow_test=True))
        self.assertFalse(logic.is_fetch_url("http://localhost:8000/latest.json", allow_test=True))

    def test_links_and_redirects(self):
        self.assertTrue(logic.is_safe_link("https://office.hasontech.vn/tai/windows"))
        for bad in ("http://office.hasontech.vn/", "https://hasontech.vn.evil.example/", "javascript:alert(1)", "https://x.vn/"):
            self.assertFalse(logic.is_safe_link(bad), bad)
        self.assertTrue(logic.same_origin(logic.MANIFEST_URL, "https://office.hasontech.vn/other"))
        self.assertFalse(logic.same_origin(logic.MANIFEST_URL, "https://evil.example/latest.json"))
        self.assertFalse(logic.same_origin(logic.MANIFEST_URL, "http://office.hasontech.vn/update/latest.json"))

    def test_test_override_needs_test_build(self):
        env = {fetch.TEST_URL_ENV: "http://127.0.0.1:9/latest.json"}
        self.assertEqual(fetch.manifest_url({"test_mode": False}, env), logic.MANIFEST_URL)
        self.assertEqual(fetch.manifest_url({"test_mode": True}, env), env[fetch.TEST_URL_ENV])
        self.assertEqual(fetch.manifest_url({"test_mode": True}, {fetch.TEST_URL_ENV: "http://evil.example/x"}), logic.MANIFEST_URL)
        self.assertFalse(fetch.release_info()["test_mode"])  # the repository stamp is a release stamp

    def test_platform_and_user_agent(self):
        self.assertEqual(logic.platform_key("Windows", "AMD64"), "windows")
        self.assertEqual(logic.platform_key("Darwin", "arm64"), "macos-arm")
        self.assertEqual(logic.platform_key("Darwin", "x86_64"), "macos-intel")
        self.assertEqual(logic.platform_key("Linux", "x86_64"), "linux")
        self.assertEqual(logic.user_agent("1.0.0-beta.2", "Windows"), "HSTOffice/1.0.0-beta.2 (Windows)")
        rel = logic._release("beta", dict(release("1.0.0"), downloads={"linux": "https://office.hasontech.vn/tai/linux"}))
        self.assertEqual(logic.download_url(rel, "windows"), rel["notes"])


if __name__ == "__main__":
    unittest.main()
