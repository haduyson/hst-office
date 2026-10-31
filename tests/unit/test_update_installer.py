# SPDX-License-Identifier: AGPL-3.0-only
"""Installer metadata, file/cache safety, dual manifest generation and authenticated fallback."""
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

import _paths
from hst_office import update_fetch as fetch
from hst_office import update_installer as installer
from hst_office import update_logic as logic
from test_update_check import TEST_PUBLIC, manifest, release, signed

GITHUB = "https://github.com/haduyson/hst-office/releases/download/v1.0.0-beta.4/"
NAMES = {"windows": "HSTOffice_1.0.0_Win_x86-64_en-US_vi.msi", "macos-arm": "HSTOffice_1.0.0_macOS_arm64.dmg",
         "macos-intel": "HSTOffice_1.0.0_macOS_x86_64.dmg", "linux": "HSTOffice_1.0.0_Linux_x86-64.deb"}
SPEC = importlib.util.spec_from_file_location("generate_update_manifest",
                                            Path(_paths.ROOT) / "scripts/release/generate-update-manifest.py")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def metadata(platform="windows", content=b"installer"):
    return {"url": GITHUB + NAMES[platform], "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}


def schema2(installers=None):
    entry = release("1.0.0-beta.4")
    if installers is not None:
        entry["installers"] = installers
    return json.dumps({"schema": 2, "channels": {"stable": None, "beta": entry}}).encode()


class InstallerMetadata(unittest.TestCase):
    def test_schema1_and_optional_schema2_installers(self):
        self.assertEqual(logic.parse_manifest(manifest(beta=release("1.0.0")))["beta"]["installers"], {})
        self.assertEqual(logic.parse_manifest(schema2())["beta"]["installers"], {})
        old = release("1.0.0")
        old["installers"] = "ignored unknown schema 1 field"
        self.assertEqual(logic.parse_manifest(manifest(beta=old))["beta"]["installers"], {})
        self.assertEqual(logic.SCHEMAS, (1, 2))
        self.assertEqual(logic.SCHEMA, 1)
        self.assertTrue(logic.is_fetch_url(logic.MANIFEST_URL))
        self.assertTrue(logic.is_fetch_url(logic.LEGACY_MANIFEST_URL))

    def test_parsed_installers_and_platform_selection(self):
        raw = {platform: metadata(platform) for platform in logic.PLATFORMS}
        parsed = logic.parse_manifest(schema2(raw))["beta"]
        for platform in logic.PLATFORMS:
            expected = dict(raw[platform], name=NAMES[platform])
            self.assertEqual(parsed["installers"][platform], expected)
            self.assertEqual(installer.choose_installer(parsed, platform), expected)
        self.assertIsNone(installer.choose_installer(parsed, "amiga"))
        self.assertIsNone(installer.choose_installer({}, "linux"))
        self.assertIsNone(installer.choose_installer(None, "linux"))
        self.assertEqual(parsed["downloads"], release("1.0.0")["downloads"])
        self.assertNotIn("name", raw["windows"])

    def test_invalid_metadata_is_manifest_error(self):
        changes = [("sha256", value) for value in (None, 123, "a" * 63, "A" * 64, "g" * 64, "0" * 64 + "\n")]
        changes += [("size", value) for value in (None, True, False, 0, -1, 4294967297, 1.0, "1")]
        changes += [("url", value) for value in (None, 123, "http://hasontech.vn/a.msi", "https://evil.test/a.msi",
                    GITHUB + "setup.dmg", GITHUB + "../", GITHUB + "with%20space.msi", GITHUB + "a.exe")]
        for field, value in changes:
            raw = {"windows": dict(metadata(), **{field: value})}
            with self.subTest(field=field, value=value), self.assertRaises(logic.ManifestError):
                logic.parse_manifest(schema2(raw))
        for value in (None, [], "invalid", {"amiga": metadata()}, {"windows": None}, {"windows": {}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                installer.parse_installers(value, logic.PLATFORMS)
        invalid = json.loads(schema2())
        invalid["channels"]["beta"]["installers"] = None
        with self.assertRaises(logic.ManifestError):
            logic.parse_manifest(json.dumps(invalid).encode())

    def test_sizes_at_limits_and_extensions_for_each_platform(self):
        for size in (1, 4294967296):
            self.assertEqual(installer.parse_installers({"windows": dict(metadata(), size=size)},
                                                       logic.PLATFORMS)["windows"]["size"], size)
        for platform in logic.PLATFORMS:
            wrong = "setup.msi" if platform != "windows" else "setup.deb"
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                installer.parse_installers({platform: dict(metadata(platform), url=GITHUB + wrong)}, logic.PLATFORMS)

    def test_url_rules(self):
        for url in (GITHUB + "setup.msi", "https://hasontech.vn/a.deb", "https://cdn.hasontech.vn/a.dmg"):
            self.assertTrue(installer.is_installer_url(url), url)
        bad = ("https://github.com/other/hst-office/releases/download/v1/a.msi",
               "https://github.com/haduyson/hst-office/releases/download-other/v1/a.msi",
               "https://github.com/haduyson/hst-office/archive/a.msi", "https://github.com/a.msi",
               "https://sub.github.com/haduyson/hst-office/releases/download/v1/a.msi",
               "https://hasontech.vn.evil.test/a.msi", "https://evilhasontech.vn/a.msi",
               "https://user:pass@hasontech.vn/a.msi", "https://hasontech.vn:443/a.msi",
               "https://hasontech.vn:/a.msi", "https://hasontech.vn:bad/a.msi", "https://[invalid/a.msi",
               "https://hasontech.vn/with space.msi", "https://hasontech.vn/a.msi\n", "https://hasontech.vn/\x00a.msi",
               "https://hasontech.vn/a.MSI", "https://hasontech.vn/a.msi/", "https://hasontech.vn/a%2fsetup.msi",
               "https://hasontech.vn/a\\setup.msi", "file:///a.msi", "ftp://hasontech.vn/a.msi")
        for url in bad:
            with self.subTest(url=url):
                self.assertFalse(installer.is_installer_url(url))

    def test_test_urls_and_allow_test_threading(self):
        for url in ("http://127.0.0.1/setup.msi", "http://127.0.0.1:8000/setup.msi"):
            self.assertFalse(installer.is_installer_url(url))
            self.assertTrue(installer.is_installer_url(url, allow_test=True))
            data = schema2({"windows": dict(metadata(), url=url)})
            with self.assertRaises(logic.ManifestError):
                logic.parse_manifest(data)
            self.assertEqual(logic.parse_manifest(data, allow_test=True)["beta"]["installers"]["windows"]["url"], url)
            with self.assertRaises(fetch.UpdateError):
                fetch.verify_manifest(data, signed(data), TEST_PUBLIC)
            self.assertIn("windows", fetch.verify_manifest(data, signed(data), TEST_PUBLIC, True)["beta"]["installers"])
        for url in ("http://localhost/a.msi", "https://127.0.0.1/a.msi", "http://127.0.0.2/a.msi",
                    "http://user@127.0.0.1/a.msi", "http://127.0.0.1:99999/a.msi"):
            self.assertFalse(installer.is_installer_url(url, allow_test=True), url)

    def test_redirect_allowlist(self):
        for host in ("hasontech.vn", "cdn.hasontech.vn", "github.com", "objects.githubusercontent.com",
                     "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"):
            self.assertTrue(installer.is_redirect_allowed("https://" + host + "/delivery?token=test"))
        for url in ("http://hasontech.vn/a", "https://evil.test/a", "https://raw.githubusercontent.com/a",
                    "https://github.com.evil.test/a", "https://sub.objects.githubusercontent.com/a",
                    "https://user@github.com/a", "https://github.com:443/a", "https://github.com/a b", "https://["):
            self.assertFalse(installer.is_redirect_allowed(url), url)
        self.assertFalse(installer.is_redirect_allowed("http://127.0.0.1:9000/a"))
        self.assertTrue(installer.is_redirect_allowed("http://127.0.0.1:9000/a", True))
        self.assertFalse(installer.is_redirect_allowed("http://localhost:9000/a", True))


class InstallerFiles(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_verify_content_size_hash_and_missing_file(self):
        content = b"x" * (1024 * 1024) + b"tail"
        path = self.root / "setup.msi"
        path.write_bytes(content)
        entry = metadata(content=content)
        installer.verify_file(path, entry)
        with self.assertRaisesRegex(installer.InstallerError, "size"):
            installer.verify_file(path, dict(entry, size=len(content) + 1, sha256="0" * 64))
        path.write_bytes(content[:-1] + b"X")
        with self.assertRaisesRegex(installer.InstallerError, "sha256"):
            installer.verify_file(path, entry)
        with self.assertRaisesRegex(installer.InstallerError, "cannot read installer"):
            installer.verify_file(self.root / "missing", entry)

    def test_cache_paths(self):
        home = os.path.join("users", "tester")
        cases = (("Windows", {}, (home, "AppData", "Local", "HSTOffice", "update")),
                 ("Windows", {"LOCALAPPDATA": "local"}, ("local", "HSTOffice", "update")),
                 ("Darwin", {}, (home, "Library", "Caches", "HSTOffice", "update")),
                 ("Linux", {}, (home, ".cache", "hst-office", "update")),
                 ("Linux", {"XDG_CACHE_HOME": "cache"}, ("cache", "hst-office", "update")))
        for system, environ, parts in cases:
            with self.subTest(system=system, environ=environ):
                cache = installer.cache_dir(system, environ, home)
                self.assertEqual(cache, os.path.join(*parts))
                self.assertEqual(installer.installer_path(cache, {"name": "setup.msi"}), os.path.join(cache, "setup.msi"))

    def test_cleanup_preserves_log_kept_file_directories_and_symlinks(self):
        cache = self.root / "cache"
        cache.mkdir()
        for name in ("update.log", "keep.msi", "old.msi", "partial.tmp"):
            (cache / name).write_bytes(b"content")
        nested = cache / "nested"
        nested.mkdir()
        (nested / "untouched").touch()
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "valuable"
        target.write_bytes(b"preserve")
        (cache / "linked-file").symlink_to(target)
        (cache / "linked-dir").symlink_to(outside, target_is_directory=True)
        (cache / "broken").symlink_to(self.root / "absent")
        installer.cleanup(cache, "keep.msi")
        self.assertEqual({p.name for p in cache.iterdir()},
                         {"update.log", "keep.msi", "nested", "linked-file", "linked-dir", "broken"})
        self.assertEqual(target.read_bytes(), b"preserve")
        self.assertTrue((nested / "untouched").exists())
        installer.cleanup(cache)
        self.assertFalse((cache / "keep.msi").exists())
        self.assertTrue((cache / "update.log").exists())
        linked_cache = self.root / "linked-cache"
        linked_cache.symlink_to(outside, target_is_directory=True)
        installer.cleanup(linked_cache)
        installer.cleanup(self.root / "absent-cache")
        installer.cleanup(target)
        with mock.patch.object(installer.os, "unlink", side_effect=PermissionError("denied")):
            installer.cleanup(outside)
        self.assertEqual(target.read_bytes(), b"preserve")


class ManifestGenerator(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.site = self.root / "site"
        self.site.mkdir()
        self.sums = self.root / "SHA256SUMS"
        self.contents = {name: ("content for " + name).encode() for name in NAMES.values()}
        self.contents["HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz"] = b"legacy archive"
        for name, data in self.contents.items():
            (self.assets / name).write_bytes(data)
        self.write_sums()

    def write_sums(self, contents=None):
        data = self.contents if contents is None else contents
        self.sums.write_text("".join(hashlib.sha256(content).hexdigest() + "  " + name + "\n"
                                    for name, content in data.items()), encoding="utf-8")

    def run_generator(self, extra=(), gh=False):
        args = ["--tag", "v1.0.0-beta.4", "--sums", str(self.sums), "--site-dir", str(self.site), "--date", "2026-10-31"]
        args += ["--gh-tag", "v1.0.0-beta.4"] if gh else ["--assets-dir", str(self.assets)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            result = generator.main(args + list(extra))
        self.assertEqual(result, 0)
        return output.getvalue()

    def read_output(self, name):
        data = (self.site / name).read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        logic.parse_manifest(data)
        return json.loads(data)

    def test_end_to_end_both_schemas_other_channel_and_determinism(self):
        stable = dict(release("1.0.0"), installers={"linux": metadata("linux")})
        previous = {"schema": 2, "channels": {"stable": stable, "beta": release("1.0.0-beta.3")}}
        (self.site / "latest-2.json").write_text(json.dumps(previous), encoding="utf-8")
        (self.site / "latest.json").write_bytes(manifest(stable=release("0.9.0")))
        output = self.run_generator(("--critical",))
        modern, legacy = self.read_output("latest-2.json"), self.read_output("latest.json")
        self.assertEqual(modern["schema"], 2)
        self.assertEqual(legacy["schema"], 1)  # installed legacy clients require exactly schema 1
        self.assertEqual(modern["channels"]["stable"], stable)
        for key, entry in modern["channels"].items():
            self.assertEqual(legacy["channels"][key], {k: v for k, v in entry.items() if k != "installers"})
        beta = modern["channels"]["beta"]
        self.assertEqual((beta["version"], beta["date"], beta["notes"], beta["critical"]),
                         ("1.0.0-beta.4", "2026-10-31", "https://office.hasontech.vn/#tai-ve", True))
        self.assertEqual(beta["downloads"], release("1.0.0")["downloads"])
        self.assertEqual(set(beta["installers"]), set(logic.PLATFORMS))
        for platform, name in NAMES.items():
            self.assertEqual(beta["installers"][platform], metadata(platform, self.contents[name]))
        self.assertIn("sign-update-manifest.py", output)
        self.assertIn("latest-2.json", output)
        self.assertIn("latest.json", output)
        before = {p.name: p.read_bytes() for p in self.site.iterdir()}
        self.run_generator(("--critical",))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.site.iterdir()})
        self.assertEqual(set(before), {"latest.json", "latest-2.json"})

    def test_legacy_input_and_stable_default_channel(self):
        beta = release("1.0.0-beta.3")
        (self.site / "latest.json").write_bytes(manifest(beta=beta))
        self.run_generator(("--tag", "v1.0.0"))
        modern = self.read_output("latest-2.json")
        self.assertEqual(modern["channels"]["beta"], beta)
        self.assertEqual(modern["channels"]["stable"]["version"], "1.0.0")

    def test_explicit_channel_notes_and_empty_site(self):
        self.run_generator(("--channel", "stable", "--notes", "https://office.hasontech.vn/diem-moi/"))
        modern = self.read_output("latest-2.json")
        self.assertIsNone(modern["channels"]["beta"])
        self.assertEqual(modern["channels"]["stable"]["notes"], "https://office.hasontech.vn/diem-moi/")

    def test_bad_hash_does_not_write_either_manifest(self):
        for name in ("latest.json", "latest-2.json"):
            (self.site / name).write_bytes(manifest(beta=release("1.0.0-beta.3")))
        before = {p.name: p.read_bytes() for p in self.site.iterdir()}
        (self.assets / NAMES["windows"]).write_bytes(b"X" * len(self.contents[NAMES["windows"]]))
        with self.assertRaises(SystemExit) as raised:
            self.run_generator()
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.site.iterdir()})

    def test_missing_hash_missing_asset_zero_size_and_no_installer(self):
        original = self.sums.read_bytes()
        self.write_sums({name: data for name, data in self.contents.items() if name != NAMES["linux"]})
        with self.assertRaises(SystemExit):
            self.run_generator()
        self.sums.write_bytes(original)
        path = self.assets / NAMES["linux"]
        path.unlink()
        with self.assertRaises(SystemExit):
            self.run_generator()
        path.touch()
        with self.assertRaises(SystemExit):
            self.run_generator()
        for name in NAMES.values():
            (self.assets / name).unlink()
        self.write_sums({name: data for name, data in self.contents.items() if name.endswith(".tar.gz")})
        with self.assertRaises(SystemExit):
            self.run_generator()
        self.assertEqual(list(self.site.iterdir()), [])

    def test_github_metadata_and_digest(self):
        assets = [{"name": name, "size": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
                  for name, data in self.contents.items()]
        response = subprocess.CompletedProcess([], 0, stdout=json.dumps({"assets": assets}))
        with mock.patch.object(generator.subprocess, "run", return_value=response) as run:
            self.run_generator(gh=True)
        self.assertEqual(run.call_args.args[0], ["gh", "release", "view", "v1.0.0-beta.4", "--repo",
                                               "haduyson/hst-office", "--json", "assets"])
        self.assertEqual(set(self.read_output("latest-2.json")["channels"]["beta"]["installers"]), set(logic.PLATFORMS))
        assets[0]["digest"] = "sha256:" + "0" * 64
        response.stdout = json.dumps({"assets": assets})
        with mock.patch.object(generator.subprocess, "run", return_value=response), self.assertRaises(SystemExit):
            self.run_generator(gh=True)


class _FetchHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        self.server.paths.append(self.path)
        status, headers, body = self.server.routes.get(self.path, (404, {}, b""))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchTransport(unittest.TestCase):
    """Exercise transport failures without requiring sockets, alongside the HTTP server tests."""

    def run_fetch(self, responses):
        opener = mock.Mock()
        opener.open.side_effect = responses
        with mock.patch.object(fetch, "_opener", return_value=opener), mock.patch.object(logic, "PUBLIC_KEY", TEST_PUBLIC):
            result = fetch.fetch_channels({"release": "1.0.0-beta.2", "test_mode": False}, proxy={}, environ={})
        return result, [call.args[0].full_url for call in opener.open.call_args_list]

    def response(self, data, url):
        response = io.BytesIO(data)
        response.geturl = lambda: url
        return response

    def test_offline_falls_back_and_verifies_legacy(self):
        data = manifest(beta=release("1.0.0-beta.3"))
        result, urls = self.run_fetch([urllib.error.URLError("offline"),
                                      self.response(data, logic.LEGACY_MANIFEST_URL),
                                      self.response(signed(data).encode(), logic.LEGACY_MANIFEST_URL + ".sig")])
        self.assertEqual(result["beta"]["version"], "1.0.0-beta.3")
        self.assertEqual(urls, [logic.MANIFEST_URL, logic.LEGACY_MANIFEST_URL, logic.LEGACY_MANIFEST_URL + ".sig"])

    def test_bad_signature_never_requests_legacy(self):
        with self.assertRaisesRegex(fetch.UpdateError, "bad manifest signature"):
            self.run_fetch([self.response(schema2(), logic.MANIFEST_URL),
                            self.response(signed(b"different bytes").encode(), logic.MANIFEST_URL + ".sig")])

    def test_rejected_manifest_never_requests_legacy(self):
        data = schema2({"windows": dict(metadata(), size=0)})
        with self.assertRaisesRegex(fetch.UpdateError, "manifest rejected"):
            self.run_fetch([self.response(data, logic.MANIFEST_URL),
                            self.response(signed(data).encode(), logic.MANIFEST_URL + ".sig")])


class FetchFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FetchHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.paths = []
        self.data = manifest(beta=release("1.0.0-beta.3"))
        self.server.routes = {"/latest.json": (200, {}, self.data),
                              "/latest.json.sig": (200, {}, signed(self.data).encode())}
        for key, value in (("MANIFEST_URL", self.base + "/latest-2.json"),
                           ("LEGACY_MANIFEST_URL", self.base + "/latest.json"), ("PUBLIC_KEY", TEST_PUBLIC)):
            patch = mock.patch.object(logic, key, value)
            patch.start()
            self.addCleanup(patch.stop)

    def run_fetch(self, environ=None):
        return fetch.fetch_channels({"release": "1.0.0-beta.2", "test_mode": True}, proxy={},
                                    environ={} if environ is None else environ)

    def test_http_failure_falls_back_with_signature(self):
        for status in (404, 503):
            self.server.paths.clear()
            self.server.routes["/latest-2.json"] = (status, {}, b"")
            with self.subTest(status=status):
                channels = self.run_fetch()
                self.assertEqual(channels["beta"]["version"], "1.0.0-beta.3")
                self.assertEqual(channels["beta"]["installers"], {})
                self.assertEqual(self.server.paths, ["/latest-2.json", "/latest.json", "/latest.json.sig"])

    def test_signature_fetch_failure_falls_back(self):
        self.server.routes["/latest-2.json"] = (200, {}, schema2())
        self.assertEqual(self.run_fetch()["beta"]["version"], "1.0.0-beta.3")
        self.assertEqual(self.server.paths, ["/latest-2.json", "/latest-2.json.sig", "/latest.json", "/latest.json.sig"])

    def test_primary_success_and_test_installer(self):
        data = schema2({"windows": dict(metadata(), url=self.base + "/setup.msi")})
        self.server.routes.update({"/latest-2.json": (200, {}, data),
                                   "/latest-2.json.sig": (200, {}, signed(data).encode())})
        self.assertEqual(self.run_fetch()["beta"]["installers"]["windows"]["name"], "setup.msi")
        self.assertEqual(self.server.paths, ["/latest-2.json", "/latest-2.json.sig"])

    def test_bad_signature_and_rejected_manifest_do_not_fall_back(self):
        invalid = schema2({"windows": dict(metadata(), sha256="bad")})
        for data, signature in ((schema2(), signed(self.data).encode()), (invalid, signed(invalid).encode()),
                                (schema2(), b"not base64"), (schema2(), b"\xff")):
            self.server.paths.clear()
            self.server.routes.update({"/latest-2.json": (200, {}, data), "/latest-2.json.sig": (200, {}, signature)})
            with self.subTest(signature=signature[:8]), self.assertRaises(fetch.UpdateError):
                self.run_fetch()
            self.assertEqual(self.server.paths, ["/latest-2.json", "/latest-2.json.sig"])

    def test_oversized_or_foreign_redirect_do_not_fall_back(self):
        for response in ((200, {}, b" " * (logic.MAX_BYTES + 1)), (302, {"Location": "https://evil.test/x"}, b"")):
            self.server.paths.clear()
            self.server.routes["/latest-2.json"] = response
            with self.assertRaises(fetch.UpdateError):
                self.run_fetch()
            self.assertEqual(self.server.paths, ["/latest-2.json"])

    def test_test_override_does_not_fall_back_even_if_equal_to_primary(self):
        for path in ("/override.json", "/latest-2.json"):
            self.server.paths.clear()
            with self.assertRaises(fetch.UpdateError):
                self.run_fetch({fetch.TEST_URL_ENV: self.base + path})
            self.assertEqual(self.server.paths, [path])

    def test_legacy_signature_is_still_required(self):
        self.server.routes["/latest.json.sig"] = (200, {}, signed(schema2()).encode())
        with self.assertRaisesRegex(fetch.UpdateError, "bad manifest signature"):
            self.run_fetch()
        self.assertEqual(self.server.paths, ["/latest-2.json", "/latest.json", "/latest.json.sig"])


if __name__ == "__main__":
    unittest.main()
