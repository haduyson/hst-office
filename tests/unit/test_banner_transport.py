# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.request

from _paths import ROOT
from banner_fixtures import KEY, SEED, VERSION, manifest, signed
from hst_office import banner_http as banner_fetch
from hst_office import banner_verify, update_logic
from hst_office.banner_urls import FEED_URL


class BannerTransportTests(unittest.TestCase):
    def response(self, payload=b"hello", url=FEED_URL):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = payload
        response.geturl.return_value = url
        response.status = 200
        response.headers = {}
        return opener, response

    def test_plain_user_agent_timeout_bounded_read(self):
        opener, response = self.response()
        with patch.object(banner_fetch.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(banner_fetch.request(FEED_URL, 20, VERSION), b"hello")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "HSTOffice/" + VERSION)
        self.assertEqual(set(k.lower() for k in request.headers), {"user-agent", "accept"})
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 5)
        response.read.assert_called_once_with(21)

    def test_oversize_response_rejected(self):
        opener, _ = self.response(b"x" * 21)
        with patch.object(banner_fetch.urllib.request, "build_opener", return_value=opener), self.assertRaises(ValueError):
            banner_fetch.request(FEED_URL, 20, VERSION)

    def test_transport_https_only(self):
        with patch.object(banner_fetch.urllib.request, "build_opener") as opener:
            for url in ("http://system.hasontech.vn/a", "file:///tmp/a"):
                with self.assertRaises(ValueError): banner_fetch.request(url, 20, VERSION)
            opener.assert_not_called()

    def test_final_origin_and_compression_checked(self):
        for url, encoding, status in (("https://evil.example/a", "identity", 200),
                                      (FEED_URL, "gzip", 200), (FEED_URL, "identity", 206)):
            opener, response = self.response(url=url)
            response.headers = {"Content-Encoding": encoding}; response.status = status
            with patch.object(banner_fetch.urllib.request, "build_opener", return_value=opener), self.assertRaises(ValueError):
                banner_fetch.request(FEED_URL, 20, VERSION)

    def test_redirect_policy(self):
        redirect = banner_fetch._Redirect()
        req = urllib.request.Request(FEED_URL)
        result = redirect.redirect_request(req, None, 302, "", {}, FEED_URL + ".new")
        self.assertEqual(result.full_url, FEED_URL + ".new")
        for target in ("http://system.hasontech.vn/a", "https://hasontech.vn/a", "https://evil.example/a"):
            with self.assertRaises(ValueError): redirect.redirect_request(req, None, 302, "", {}, target)

    def test_signing_script_roundtrip_throwaway_key(self):
        spec = importlib.util.spec_from_file_location("sign_banner", Path(ROOT) / "scripts/release/sign-banner-manifest.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "throwaway.key"; key.write_text(SEED.hex()); key.chmod(0o600)
            path = Path(tmp) / "banners.json"; path.write_bytes(signed(manifest())[0])
            with patch.object(banner_verify, "PUBLIC_KEY", KEY):
                module.sign(path, key)
                self.assertEqual(banner_verify.verify_manifest(path.read_bytes(), Path(str(path) + ".sig").read_bytes())["schemaVersion"], 1)
            with patch.object(banner_verify, "PUBLIC_KEY", b""), self.assertRaises(ValueError): module.sign(path, key)
            with patch.object(banner_verify, "PUBLIC_KEY", KEY), patch.object(update_logic, "PUBLIC_KEY", KEY), self.assertRaises(ValueError):
                module.sign(path, key)


if __name__ == "__main__": unittest.main()
