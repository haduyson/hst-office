# SPDX-License-Identifier: AGPL-3.0-only
"""Update check: versions, channels, manifest validation, signatures, URL rules, test override, throttle, skip."""
import base64
import http.server
import json
import os
import threading
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import ed25519
from hst_office import update_fetch as fetch
from hst_office import update_logic as logic

SEED = bytes(range(32))  # test-only key; the real private key never enters the repository
TEST_PUBLIC = ed25519.secret_to_public(SEED)
SITE = os.path.join(_paths.ROOT, "website", "office.hasontech.vn", "update")


def read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


def release(version, channel="beta", critical=False):
    return {"version": version, "date": "2026-10-30", "notes": "https://office.hasontech.vn/#tai-ve", "critical": critical,
            "downloads": {p: "https://office.hasontech.vn/tai/" + p for p in logic.PLATFORMS}}


def manifest(stable=None, beta=None):
    return json.dumps({"schema": 1, "channels": {"stable": stable, "beta": beta}}).encode("utf-8")


def signed(data, seed=SEED):
    return base64.b64encode(ed25519.sign(seed, data)).decode("ascii") + "\n"


class Versions(unittest.TestCase):
    def test_semver_order_with_prerelease(self):
        order = ["0.9.9", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.10", "1.0.0-rc.1",
                 "1.0.0", "1.0.1", "1.1.0", "2.0.0"]
        self.assertEqual(sorted(reversed(order), key=logic.version_key), order)
        self.assertEqual(logic.version_key("1.0.0+build.5"), logic.version_key("1.0.0"))

    def test_invalid_versions(self):
        for bad in ("1.0", "01.0.0", "1.0.0-", "1.0.0-beta..1", "v1.0.0", "", None, "1.0.0-01"):
            with self.subTest(bad):
                self.assertFalse(logic.is_valid_version(bad))

    def test_channel_of_release(self):
        self.assertEqual(logic.channel_of("1.0.0-beta.2"), "beta")
        self.assertEqual(logic.channel_of("1.0.0"), "stable")
        self.assertEqual(logic.channel_of("1.0.0+meta-data"), "stable")

    def test_release_stamp_matches_version_file(self):
        info = json.loads(read(os.path.join(_paths.ROOT, "data", "hst", "release.json")))
        core = read(os.path.join(_paths.ROOT, "VERSION")).strip()
        self.assertTrue(logic.is_valid_version(info["release"]))
        self.assertEqual(info["release"].split("-")[0], core)


class Channels(unittest.TestCase):
    def channels(self, stable=None, beta=None):
        return logic.parse_manifest(manifest(stable, beta))

    def test_beta_user_sees_newer_beta_or_stable(self):
        ch = self.channels(beta=release("1.0.0-beta.10"))
        self.assertEqual(logic.select_update(ch, "1.0.0-beta.2", "beta")["version"], "1.0.0-beta.10")
        ch = self.channels(stable=release("1.0.0"), beta=release("1.0.0-beta.3"))
        self.assertEqual(logic.select_update(ch, "1.0.0-beta.2", "beta")["version"], "1.0.0")
        self.assertEqual(logic.select_update(ch, "1.0.0-beta.2", "beta")["channel"], "stable")

    def test_stable_user_sees_only_stable(self):
        ch = self.channels(beta=release("1.1.0-beta.1"))
        self.assertIsNone(logic.select_update(ch, "1.0.0", "stable"))
        ch = self.channels(stable=release("1.0.1"), beta=release("1.1.0-beta.1"))
        self.assertEqual(logic.select_update(ch, "1.0.0", "stable")["version"], "1.0.1")

    def test_up_to_date_and_older(self):
        ch = self.channels(beta=release("1.0.0-beta.2"))
        self.assertIsNone(logic.select_update(ch, "1.0.0-beta.2", "beta"))
        self.assertIsNone(logic.select_update(ch, "1.0.0", "stable"))

    def test_published_manifest_is_valid_and_signed(self):
        data = read(os.path.join(SITE, "latest.json"), "rb")
        ch = fetch.verify_manifest(data, read(os.path.join(SITE, "latest.json.sig")))
        self.assertEqual(ch["beta"]["version"], "1.0.0-beta.2")
        for url in list(ch["beta"]["downloads"].values()) + [ch["beta"]["notes"]]:
            self.assertTrue(url.startswith("https://office.hasontech.vn/"), url)
        self.assertNotRegex(data.decode("utf-8").lower(), "github|libreoffice")


class ManifestRules(unittest.TestCase):
    def test_rejects_malformed(self):
        bad_links = dict(release("1.0.0"), notes="http://office.hasontech.vn/")
        cases = [b"not json", b"[]", json.dumps({"schema": 2, "channels": {}}).encode(),
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


class SkipAndThrottle(unittest.TestCase):
    def test_skip_version_memory(self):
        rel = logic._release("beta", release("1.0.0"))
        self.assertTrue(logic.should_notify(rel, ""))
        self.assertFalse(logic.should_notify(rel, "1.0.0"))
        self.assertTrue(logic.should_notify(rel, "1.0.0-beta.9"))
        self.assertTrue(logic.should_notify(logic._release("beta", release("1.0.0", critical=True)), "1.0.0"))
        self.assertFalse(logic.should_notify(None, ""))

    def test_24h_throttle(self):
        day = logic.CHECK_INTERVAL
        self.assertTrue(logic.check_due(1_000_000, 0))
        self.assertFalse(logic.check_due(1_000_000, 1_000_000 - day + 1))
        self.assertTrue(logic.check_due(1_000_000, 1_000_000 - day))
        self.assertTrue(logic.check_due(1_000_000, 1_000_000 + 3600))  # clock set back


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}
    agents = []

    def do_GET(self):  # noqa: N802 - http.server API
        self.agents.append(self.headers.get("User-Agent"))
        status, headers, body = self.routes.get(self.path, (404, {}, b""))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class LocalServer(unittest.TestCase):
    """End-to-end fetch against a local plain-HTTP server (test-build override), with the test key."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_fetch(self, routes):
        _Handler.routes = routes
        info = {"release": "1.0.0-beta.2", "channel": "beta", "test_mode": True}
        with mock.patch.object(logic, "PUBLIC_KEY", TEST_PUBLIC):
            return fetch.fetch_channels(info, proxy={}, environ={fetch.TEST_URL_ENV: self.base + "/latest.json"})

    def test_signed_manifest_and_user_agent(self):
        data = manifest(beta=release("1.0.0"))
        _Handler.agents.clear()
        ch = self.run_fetch({"/latest.json": (200, {}, data), "/latest.json.sig": (200, {}, signed(data).encode())})
        self.assertEqual(ch["beta"]["version"], "1.0.0")
        self.assertTrue(all(a.startswith("HSTOffice/1.0.0-beta.2 (") for a in _Handler.agents), _Handler.agents)

    def test_unsigned_tampered_offline_oversized_and_redirect(self):
        data = manifest(beta=release("1.0.0"))
        cases = {
            "unsigned": {"/latest.json": (200, {}, data)},
            "tampered": {"/latest.json": (200, {}, data + b" "), "/latest.json.sig": (200, {}, signed(data).encode())},
            "oversized": {"/latest.json": (200, {}, b" " * (logic.MAX_BYTES + 1))},
            "foreign redirect": {"/latest.json": (302, {"Location": "https://evil.example/latest.json"}, b"")},
            "server error": {"/latest.json": (500, {}, b"")},
        }
        for label, routes in cases.items():
            with self.subTest(label), self.assertRaises(fetch.UpdateError):
                self.run_fetch(routes)

    def test_same_origin_redirect_is_followed(self):
        data = manifest(beta=release("1.0.0"))
        ch = self.run_fetch({"/latest.json": (302, {"Location": "/v2.json"}, b""), "/v2.json": (200, {}, data),
                             "/latest.json.sig": (200, {}, signed(data).encode())})
        self.assertEqual(ch["beta"]["version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
