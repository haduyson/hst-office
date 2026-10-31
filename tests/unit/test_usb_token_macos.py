# SPDX-License-Identifier: AGPL-3.0-only
"""Real macOS bundle names in temporary trees; no native Mach-O claim on Linux."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import _paths
from hst_office import usb_token_nss as nss
from hst_office.usb_token_errors import SetupError


class MacBundleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.python = sys.executable

    def bundle(self, name="HST Office.app"):
        contents = self.root / name / "Contents"
        (contents / "MacOS").mkdir(parents=True)
        (contents / "MacOS/soffice").touch()
        framework = contents / "Frameworks/LibreOfficePython.framework"
        version = framework / "Versions/3.12"
        (version / "bin").mkdir(parents=True)
        (version / "bin/python3").symlink_to(self.python)
        (framework / "Versions/Current").symlink_to("3.12", target_is_directory=True)
        (framework / "bin").symlink_to("Versions/Current/bin", target_is_directory=True)
        (contents / "Frameworks/libnss3.dylib").touch()
        return contents, framework, version

    @contextmanager
    def runtime(self, executable, prefix):
        with patch.object(nss.sys, "platform", "darwin"), patch.object(nss.sys, "executable", str(executable)), \
                patch.object(nss.sys, "base_prefix", str(prefix)), patch.object(nss.shutil, "which", return_value=None):
            yield

    def test_standard_app_from_office_and_framework_prefixes(self):
        for name in ("HST.app", "HST Office.app"):
            contents, framework, version = self.bundle(name)
            for prefix in (framework, version, framework / "Versions/Current"):
                with self.subTest(app=name, prefix=prefix), self.runtime(contents / "MacOS/soffice", prefix):
                    self.assertEqual(nss.nss_library(), str(contents / "Frameworks/libnss3.dylib"))
                    helper = nss.helper_python()
                    self.assertEqual(Path(helper).resolve(), Path(self.python).resolve())
                    # Execute the fixture's helper symlink, not the office binary.
                    result = subprocess.run([helper, "-c", "print('helper ready')"], check=True,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.stdout.strip(), "helper ready")

    def test_prefix_locates_bundle_when_executable_is_external_python(self):
        contents, framework, version = self.bundle()
        for prefix in (framework, version):
            with self.subTest(prefix=prefix), self.runtime(self.python, prefix):
                self.assertEqual(nss.nss_library(), str(contents / "Frameworks/libnss3.dylib"))

    def test_executable_locates_bundle_without_framework_prefix(self):
        contents, _, _ = self.bundle()
        launcher = self.root / "soffice"
        launcher.symlink_to(contents / "MacOS/soffice")
        with self.runtime(launcher, self.root / "unrelated-python"):
            self.assertEqual(nss.nss_library(), str(contents / "Frameworks/libnss3.dylib"))
            self.assertEqual(nss.helper_python(), str(contents / "Frameworks/LibreOfficePython.framework/bin/python3"))

    def test_versioned_helper_without_framework_bin_alias(self):
        contents, framework, version = self.bundle()
        (framework / "bin").unlink()
        with self.runtime(contents / "MacOS/soffice", framework):
            self.assertEqual(nss.helper_python(), str(framework / "Versions/Current/bin/python3"))
            (framework / "Versions/Current").unlink()
            self.assertEqual(nss.helper_python(), str(version / "bin/python3"))

    def test_frameworks_preferred_and_macos_dylib_fallback(self):
        contents, framework, _ = self.bundle()
        (contents / "MacOS/libnss3.dylib").touch()
        with self.runtime(contents / "MacOS/soffice", framework):
            self.assertEqual(nss.nss_library(), str(contents / "Frameworks/libnss3.dylib"))
            (contents / "Frameworks/libnss3.dylib").unlink()
            self.assertEqual(nss.nss_library(), str(contents / "MacOS/libnss3.dylib"))

    def test_missing_dylib_refuses_linux_library_and_other_bundles(self):
        contents, framework, _ = self.bundle()
        self.bundle("Other Office.app")
        (contents / "Frameworks/libnss3.dylib").unlink()
        (contents / "Frameworks/libnss3.so").touch()
        with self.runtime(contents / "MacOS/soffice", framework), self.assertRaisesRegex(SetupError, "Không tìm thấy thư viện NSS"):
            nss.nss_library()

    def test_register_passes_bundled_paths_to_worker(self):
        contents, framework, _ = self.bundle()
        db = self.root / "fresh-db"
        db.mkdir()
        requests = []

        def worker(argv):
            request = json.loads(Path(argv[2]).read_text())
            requests.append((argv, request))
            Path(request["response"]).write_text(json.dumps({"status": "added"}))
            return 0

        with self.runtime(contents / "MacOS/soffice", framework), patch.object(nss, "run_tool", side_effect=worker), \
                patch("hst_office.usb_token_db.user_database"):
            row = nss.register(db, [dict(label="VNPT-CA", path="/usr/local/lib/libvnptca_p11_v8.dylib")])[0]
        self.assertEqual(row["status"], "added")
        argv, request = requests[0]
        self.assertEqual(argv[0], str(framework / "bin/python3"))
        self.assertEqual(Path(argv[1]).name, "usb_token_worker.py")
        self.assertEqual(request["nss"], str(contents / "Frameworks/libnss3.dylib"))
        self.assertEqual(list(db.iterdir()), [])  # Transport fixture does not run native NSS.
