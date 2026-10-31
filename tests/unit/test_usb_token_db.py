# SPDX-License-Identifier: AGPL-3.0-only
"""Database selection matches the core, including profile ordering and explicit options."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _paths
from hst_office.usb_token_db import ROOTS, MAC_ROOTS, select_db, user_database
from hst_office.usb_token_errors import SetupError


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def profile(self, root, ini=None):
        root = self.home / root
        root.mkdir(parents=True, exist_ok=True)
        (root / "profiles.ini").write_text(ini or "[Profile0]\nName=default\nIsRelative=1\nPath=test\nDefault=1\n")
        (root / "test").mkdir(exist_ok=True)
        return root / "test"

    def select(self, **kwargs):
        return select_db(self.home, env=kwargs.pop("env", {}), **kwargs)

    def test_empty_home_falls_back(self):
        self.assertEqual(self.select(), (self.home / ".pki/nssdb", True))

    def test_existing_shared_db(self):
        path = self.home / ".pki/nssdb"
        path.mkdir(parents=True)
        (path / "cert9.db").touch()
        self.assertEqual(self.select(), (path, True))

    def test_every_linux_profile_root(self):
        for _, roots in ROOTS:
            for root in roots:
                with self.subTest(root=root):
                    expected = self.profile(root)
                    self.assertEqual(self.select(), (expected, False))
                    (expected.parent / "profiles.ini").unlink()

    def test_every_mac_profile_root(self):
        for root in MAC_ROOTS:
            expected = self.profile(root)
            self.assertEqual(self.select(platform="macos"), (expected, False))
            (expected.parent / "profiles.ini").unlink()

    def test_thunderbird_precedes_firefox(self):
        self.profile(".mozilla/firefox")
        thunderbird = self.profile("snap/thunderbird/common/.thunderbird")
        self.assertEqual(self.select()[0], thunderbird)

    def test_first_registry_per_product(self):
        expected = self.profile(".mozilla/firefox")
        self.profile("snap/firefox/common/.mozilla/firefox")
        self.assertEqual(self.select()[0], expected)

    def test_default_release_precedes_flag_and_install_sections(self):
        expected = self.profile(".mozilla/firefox", "[InstallHash]\nDefault=ignored\n[Profile0]\nName=z\nPath=wrong\n"
                                "IsRelative=1\nDefault=1\n[Profile1]\nName=default-release\nPath=test\nIsRelative=1\n")
        self.assertEqual(self.select()[0], expected)

    def test_without_default_profile_names_sorted(self):
        expected = self.profile(".mozilla/firefox", "[Profile0]\nName=z\nPath=wrong\nIsRelative=1\n"
                                "[Profile1]\nName=a\nPath=test\nIsRelative=1\n")
        self.assertEqual(self.select()[0], expected)

    def test_absolute_profile_and_profile_root_override(self):
        expected = self.home / "elsewhere"
        self.profile("custom", "[Profile0]\nName=a\nIsRelative=0\nPath=" + str(expected))
        self.assertEqual(self.select(env={"MOZILLA_FIREFOX_PROFILE_ROOT": str(self.home / "custom")})[0], expected)

    def test_cached_core_path_precedes_environment_and_configured(self):
        values = [str(self.home / v) for v in ("env", "configured", "core")]
        self.assertEqual(self.select(env={"MOZILLA_CERTIFICATE_FOLDER": "sql:" + values[0]},
                                     configured=values[1], core_path=values[2])[0], Path(values[2]))
        self.assertEqual(self.select(configured=values[1], core_path=values[2])[0], Path(values[2]))
        self.assertEqual(self.select(env={"MOZILLA_CERTIFICATE_FOLDER": "sql:" + values[0]})[0], Path(values[0]))

    def test_only_existing_absolute_filesystem_configured_path_is_accepted(self):
        browser = self.profile(".thunderbird")
        valid = self.home / "valid"
        valid.mkdir()
        self.assertEqual(self.select(configured=str(valid))[0], valid)
        for value in (str(self.home / "missing"), "sql:" + str(valid), "~/valid", "relative", "dbm:/old"):
            with self.subTest(value=value):
                self.assertEqual(self.select(configured=value)[0], browser)

    def test_cached_legacy_db_rejected(self):
        with self.assertRaises(SetupError):
            self.select(core_path="dbm:/old")

    def test_refuse_root(self):
        with patch("os.geteuid", return_value=0), self.assertRaises(SetupError):
            user_database(self.home)

    def test_refuse_another_users_db(self):
        with patch("os.geteuid", return_value=self.home.stat().st_uid + 1), self.assertRaises(SetupError):
            user_database(self.home)

    def test_refuse_legacy_db(self):
        (self.home / "cert8.db").touch()
        with patch("os.geteuid", return_value=2000), self.assertRaises(ValueError):
            user_database(self.home)
