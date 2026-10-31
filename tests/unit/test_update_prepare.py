# SPDX-License-Identifier: AGPL-3.0-only
"""Worker half of "Cập nhật ngay" against a local HTTP server: signed manifest, download, verification, reuse, abort paths."""
import base64
import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import _paths  # noqa: F401
from hst_office import ed25519
from hst_office import update_logic as logic
from hst_office import update_prepare as prep
from hst_office.update_download import DownloadCancelled

SEED = bytes(range(32))  # test-only key
DEB = b"dummy hst office package " * 4000
NAME = "HSTOffice_9.9.9_Linux_x86-64.deb"
INFO = {"release": "1.0.0-beta.3", "channel": "beta", "test_mode": True}


class Server:
    def __init__(self):
        self.files, self.hits = {}, []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                owner.hits.append(self.path)
                body = owner.files.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.end_headers()
                self.wfile.write(body or b"")

            def log_message(self, *args):
                pass
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def publish(self, installers, version="9.9.9", sign_with=SEED):
        release = {"version": version, "date": "2026-10-31", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
                   "downloads": {"linux": "https://office.hasontech.vn/tai/linux"}, "installers": installers}
        data = json.dumps({"schema": 2, "channels": {"stable": release, "beta": None}}).encode()
        self.files["/latest.json"] = data
        self.files["/latest.json.sig"] = base64.b64encode(ed25519.sign(sign_with, data))

    def entry(self, body=DEB, sha=None, size=None):
        return {"linux": {"url": self.base + "/files/" + NAME, "sha256": sha or hashlib.sha256(body).hexdigest(),
                          "size": len(body) if size is None else size}}

    def deb_hits(self):
        return len([h for h in self.hits if h.startswith("/files/")])


class Prepare(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.server.files["/files/" + NAME] = DEB
        self.addCleanup(self.server.httpd.server_close)
        self.addCleanup(self.server.httpd.shutdown)
        self.cache = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache.cleanup)
        self.env = {"HST_UPDATE_TEST_URL": self.server.base + "/latest.json", "XDG_CACHE_HOME": self.cache.name}
        patch = mock.patch.object(logic, "PUBLIC_KEY", ed25519.secret_to_public(SEED))
        patch.start()
        self.addCleanup(patch.stop)
        self.path = os.path.join(self.cache.name, "hst-office", "update", NAME)

    def run_prepare(self, **kwargs):
        return prep.prepare(INFO, environ=self.env, system="Linux", machine="x86_64", **kwargs)

    def test_downloads_verifies_and_reports_progress(self):
        self.server.publish(self.server.entry())
        seen = []
        result = self.run_prepare(progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(result["path"], self.path)
        self.assertEqual(result["release"]["version"], "9.9.9")
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), DEB)
        self.assertEqual(seen[-1], (len(DEB), len(DEB)))
        self.assertFalse(os.path.exists(self.path + ".part"))

    def test_later_click_reuses_verified_file_without_downloading(self):
        self.server.publish(self.server.entry())
        self.run_prepare()
        self.run_prepare()
        self.assertEqual(self.server.deb_hits(), 1)

    def test_damaged_cached_file_is_downloaded_again(self):
        self.server.publish(self.server.entry())
        self.run_prepare()
        with open(self.path, "r+b") as handle:
            handle.write(b"X")
        self.run_prepare()
        self.assertEqual(self.server.deb_hits(), 2)
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), DEB)

    def test_hash_mismatch_aborts_and_keeps_nothing(self):
        self.server.publish(self.server.entry(sha="0" * 64))
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_verify")
        self.assertEqual(os.listdir(os.path.dirname(self.path)), [])

    def test_size_mismatch_aborts(self):
        self.server.publish(self.server.entry(size=len(DEB) - 1))
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_verify")
        self.assertEqual(os.listdir(os.path.dirname(self.path)), [])

    def test_smaller_download_than_announced_aborts(self):
        self.server.publish(self.server.entry(size=len(DEB) + 5))
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_verify")

    def test_bad_manifest_signature_aborts_before_any_download(self):
        self.server.publish(self.server.entry(), sign_with=bytes(reversed(range(32))))
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_verify")
        self.assertEqual(self.server.deb_hits(), 0)

    def test_missing_file_is_a_network_error(self):
        self.server.publish(self.server.entry())
        del self.server.files["/files/" + NAME]
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_network")

    def test_cancel_removes_the_partial_file(self):
        self.server.publish(self.server.entry())
        with self.assertRaises(DownloadCancelled):
            self.run_prepare(cancelled=lambda: True)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), [])

    def test_no_installer_for_this_platform(self):
        self.server.publish({})
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "err_none")

    def test_up_to_date(self):
        self.server.publish(self.server.entry(), version="1.0.0-beta.3")
        with self.assertRaises(prep.PrepareError) as ctx:
            self.run_prepare()
        self.assertEqual(ctx.exception.code, "uptodate")

    def test_other_files_in_the_cache_are_cleaned_but_the_log_stays(self):
        self.server.publish(self.server.entry())
        folder = os.path.dirname(self.path)
        os.makedirs(folder)
        for name in ("old.deb", "update.log"):
            with open(os.path.join(folder, name), "w") as handle:
                handle.write("x")
        self.run_prepare()
        self.assertEqual(sorted(os.listdir(folder)), sorted([NAME, "update.log"]))


class AdministratorPolicy(unittest.TestCase):
    def build(self, *flags):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "policy.oxt")
            subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "release", "build-update-policy-oxt.py"),
                            "--output", out, *flags], check=True, stdout=subprocess.DEVNULL)
            return zipfile.ZipFile(out).read("policy.xcu").decode()

    def test_default_only_locks_autocheck(self):
        text = self.build()
        self.assertIn('"AutoCheck" oor:finalized="true"', text.replace("oor:name=", ""))
        self.assertNotIn("AllowInstall", text)

    def test_no_install_locks_allow_install_false(self):
        text = self.build("--no-install", "--keep-autocheck")
        self.assertIn('oor:name="AllowInstall" oor:finalized="true" oor:op="fuse"><value>false', text)
        self.assertNotIn("AutoCheck", text)

    def test_nothing_to_lock_is_refused(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.build("--keep-autocheck")


if __name__ == "__main__":
    unittest.main()
