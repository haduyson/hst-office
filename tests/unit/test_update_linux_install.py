# SPDX-License-Identifier: AGPL-3.0-only
"""Linux install kind (dpkg / rpm / AppImage) -> manifest platform key, schema 3 manifests, and the AppImage download
beside the running file (update_linux_install, update_logic, update_prepare)."""
import base64
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import ed25519
from hst_office import update_linux_install as li
from hst_office import update_logic as logic
from hst_office import update_prepare as prep
from test_update_prepare import SEED, Server

URL = "https://office.hasontech.vn/tai/1.0.2/HSTOffice_1.0.2_Linux_x86-64."


def entry(ext, body=b"x"):
    return {"url": URL + ext, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}


def release(schema, downloads, installers):
    rel = {"version": "1.0.2", "date": "2026-11-13", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
           "downloads": downloads, "installers": installers}
    return json.dumps({"schema": schema, "channels": {"stable": rel, "beta": None}}).encode()


class Schema3(unittest.TestCase):
    def test_new_linux_keys_only_in_schema_3_and_unknown_keys_skipped(self):
        downloads = {p: "https://office.hasontech.vn/tai/" + p for p in logic.ALL_PLATFORMS + ("linux-snap",)}
        installers = {"linux": entry("deb"), "linux-rpm": entry("rpm"), "linux-appimage": entry("AppImage"),
                      "linux-snap": {"anything": True}}
        stable = logic.parse_manifest(release(3, downloads, installers))["stable"]
        self.assertEqual(set(stable["installers"]), {"linux", "linux-rpm", "linux-appimage"})
        self.assertNotIn("linux-snap", stable["downloads"])
        self.assertEqual(stable["installers"]["linux-appimage"]["name"], "HSTOffice_1.0.2_Linux_x86-64.AppImage")
        for bad in ({"linux-rpm": entry("rpm")}, {"linux": entry("deb"), "linux-appimage": entry("AppImage")}):
            with self.subTest(bad=list(bad)), self.assertRaises(logic.ManifestError):
                logic.parse_manifest(release(2, {"linux": downloads["linux"]}, bad))  # what 1.0.x clients read
        with self.assertRaises(logic.ManifestError):  # known keys are still validated in schema 3
            logic.parse_manifest(release(3, downloads, {"linux-rpm": entry("deb")}))
        self.assertEqual(logic.MANIFEST_URL, "https://office.hasontech.vn/update/latest-3.json")
        self.assertEqual(logic.LEGACY_MANIFEST_URL, "https://office.hasontech.vn/update/latest-2.json")


class Detect(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.appdir = os.path.join(self.root, ".mount_x")
        self.program = os.path.join(self.appdir, "opt", "hst-office1.0", "program")
        os.makedirs(self.program)
        self.appimage = os.path.join(self.root, "HST.AppImage")
        open(self.appimage, "w").close()

    def run_with(self, owner):
        def run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0 if argv[0] == owner else 1)
        return run

    def test_kinds(self):
        which = lambda tool: "/usr/bin/" + tool  # noqa: E731
        env = {"APPIMAGE": self.appimage, "APPDIR": self.appdir}
        self.assertEqual(li.detect(self.program, env, which, self.run_with(None)), "appimage")
        self.assertEqual(li.detect("/opt/hst-office1.0/program", env, which, self.run_with("dpkg-query")), "deb")
        self.assertEqual(li.detect("/opt/hst-office1.0/program", {}, which, self.run_with("rpm")), "rpm")
        self.assertIsNone(li.detect("/opt/hst-office1.0/program", {}, which, self.run_with(None)))
        self.assertIsNone(li.detect("/x", {}, lambda tool: None, self.run_with("rpm")))
        self.assertIsNone(li.detect(self.program, dict(env, APPIMAGE="relative.AppImage"), which, self.run_with(None)))

    def test_platform_keys(self):
        for kind, key in ((None, "linux"), ("deb", "linux"), ("rpm", "linux-rpm"), ("appimage", "linux-appimage")):
            with self.subTest(kind=kind), mock.patch.object(li, "kind", return_value=kind):
                self.assertEqual(li.install_platform("Linux", "x86_64"), key)
        self.assertEqual(li.install_platform("Windows", "AMD64"), "windows")
        self.assertEqual(li.install_platform("Darwin", "arm64"), "macos-arm")

    def test_appimage_update_dir(self):
        self.assertEqual(li.appimage_update_dir({"APPIMAGE": self.appimage}), os.path.join(self.root, ".hst-office-update"))
        with self.assertRaises(ValueError):
            li.appimage_update_dir({})
        os.chmod(self.root, 0o500)
        self.addCleanup(os.chmod, self.root, 0o700)
        if not os.access(self.root, os.W_OK):  # root ignores the mode
            with self.assertRaises(ValueError):
                li.appimage_update_dir({"APPIMAGE": self.appimage})


class PrepareAppImage(unittest.TestCase):
    def test_download_lands_beside_the_appimage(self):
        server = Server()
        self.addCleanup(server.httpd.server_close)
        self.addCleanup(server.httpd.shutdown)
        body = b"new appimage " * 1000
        name = "HSTOffice_9.9.9_Linux_x86-64.AppImage"
        server.files["/files/" + name] = body
        rel = {"version": "9.9.9", "date": "2026-11-13", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
               "downloads": {"linux-appimage": "https://office.hasontech.vn/tai/linux-appimage"},
               "installers": {"linux-appimage": {"url": server.base + "/files/" + name,
                                                 "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}}}
        data = json.dumps({"schema": 3, "channels": {"stable": rel, "beta": None}}).encode()
        server.files.update({"/latest-3.json": data, "/latest-3.json.sig": base64.b64encode(ed25519.sign(SEED, data))})
        with tempfile.TemporaryDirectory() as apps, tempfile.TemporaryDirectory() as cache:
            appimage = os.path.join(apps, "HST.AppImage")
            open(appimage, "w").close()
            env = {"HST_UPDATE_TEST_URL": server.base + "/latest-3.json", "XDG_CACHE_HOME": cache, "APPIMAGE": appimage}
            with mock.patch.object(logic, "PUBLIC_KEY", ed25519.secret_to_public(SEED)), \
                    mock.patch.object(li, "kind", return_value="appimage"):
                result = prep.prepare({"release": "1.0.2", "channel": "stable", "test_mode": True}, environ=env,
                                      system="Linux", machine="x86_64")
            self.assertEqual(result["path"], os.path.join(apps, ".hst-office-update", name))
            with open(result["path"], "rb") as handle:
                self.assertEqual(handle.read(), body)
            self.assertEqual(sorted(os.listdir(apps)), [".hst-office-update", "HST.AppImage"])  # nothing else touched


if __name__ == "__main__":
    unittest.main()
