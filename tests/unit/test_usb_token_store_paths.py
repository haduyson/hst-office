# SPDX-License-Identifier: AGPL-3.0-only
"""Private-store ownership, permissions, numbering and CertDir reuse."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _paths
from hst_office import usb_token_store as store


class StorePathsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

    def test_platform_paths_are_user_owned_private_and_marked(self):
        for platform, relative in [('macos', 'Library/Application Support/HST Office/nssdb'),
                                   ('linux', '.local/share/hst-office/nssdb')]:
            path = store.directory(self.home, platform)
            self.assertEqual(path, self.home / relative)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_uid, os.geteuid())
            self.assertTrue(store.owned(path))

    def test_foreign_nonempty_or_empty_directory_is_never_reused(self):
        path = self.home / 'Library/Application Support/HST Office/nssdb'
        path.mkdir(parents=True)
        (path / 'user-data').write_bytes(b'keep exactly')
        (path.parent / 'nssdb-2').mkdir()
        target = store.directory(self.home, 'macos', str(path))
        self.assertEqual(target.name, 'nssdb-3')
        self.assertEqual(list(path.iterdir()), [path / 'user-data'])
        self.assertEqual((path / 'user-data').read_bytes(), b'keep exactly')
        self.assertEqual(list((path.parent / 'nssdb-2').iterdir()), [])

    def test_owned_current_empty_store_reused(self):
        path = store.directory(self.home, 'macos')
        self.assertEqual(store.directory(self.home, 'macos', str(path)), path)

    def test_owned_noncurrent_store_never_reused(self):
        path = store.directory(self.home, 'macos')
        self.assertEqual(store.directory(self.home, 'macos'), path.with_name('nssdb-2'))

    def test_current_module_file_means_in_use_even_before_restart(self):
        path = store.directory(self.home, 'macos')
        (path / 'pkcs11.txt').write_bytes(b'keep')
        second = store.directory(self.home, 'macos', str(path))
        self.assertEqual(second, path.with_name('nssdb-2'))
        (second / 'pkcs11.txt').write_bytes(b'also keep')
        self.assertEqual(store.directory(self.home, 'macos', str(second)), path.with_name('nssdb-3'))
        self.assertEqual((path / 'pkcs11.txt').read_bytes(), b'keep')

    def test_symlink_target_is_not_followed(self):
        path = store.directory(self.home, 'macos')
        alias = path.with_name('nssdb-2')
        alias.symlink_to(path)
        self.assertFalse(store.owned(alias))
        self.assertEqual(store.directory(self.home, 'macos', str(alias)), path.with_name('nssdb-3'))

    def test_symlink_parent_is_refused(self):
        (self.home / 'Library').symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'không là liên kết'):
            store.directory(self.home, 'macos')
        self.assertFalse((self.home / 'Application Support').exists())

    def test_foreign_uid_marker_and_insecure_permissions_rejected(self):
        path = store.directory(self.home, 'macos')
        with patch.object(store.os, 'geteuid', return_value=os.geteuid() + 1):
            self.assertFalse(store.owned(path))
        path.chmod(0o755)
        self.assertFalse(store.owned(path))
        path.chmod(0o700)
        (path / store.MARKER).write_bytes(b'not HST')
        self.assertFalse(store.owned(path))
