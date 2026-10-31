# SPDX-License-Identifier: AGPL-3.0-only
"""Fresh stores: validate ownership without creating unused source directories."""
from itertools import chain, repeat
import os
from pathlib import Path
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, SOFT, nss
from hst_office import usb_token as action, usb_token_db as database, usb_token_store as store
from hst_office.data_files import load_locale
from hst_office.usb_token_db import user_database


class FreshStoreTest(NativeNssFixture):
    def validate(self, *args, **kwargs):
        # Bypass only the root guard in root-run fixtures, keeping ownership and
        # directory creation real. All subsequent uid checks use the actual uid.
        uid = os.geteuid()
        with patch.object(database.os, 'geteuid', side_effect=chain([uid or 2000], repeat(uid))):
            return user_database(*args, **kwargs)

    def setup_action(self, home, platform, mode, override=''):
        modules = [dict(label='Token', path=str(SOFT))]
        with patch.object(database, 'office_state', return_value=('', '', False, None)), \
                patch.object(database, 'user_database', side_effect=self.validate), \
                patch.object(database, 'set_fallback') as select, \
                patch.object(action, 'detect', return_value=modules), \
                patch.object(action, 'platform_name', return_value=platform), \
                patch.object(Path, 'home', return_value=home), \
                patch.dict(os.environ, MOZILLA_CERTIFICATE_FOLDER='', HST_USB_TOKEN_TEST_PLATFORM=override,
                           HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0'):
            result = action.setup(None)
        select.assert_called_once_with(None, result[0])
        return result

    def test_fresh_setup_creates_only_selected_store_both_modes(self):
        self.addCleanup(action._pending_restart.clear)
        for platform, override in (('macos', ''), ('linux', ''), ('linux', 'darwin')):
            for mode in ('modutil', 'pkcs11'):
                with self.subTest(platform=platform, override=override, mode=mode):
                    home = self.base / (platform + override + mode)
                    home.mkdir()
                    target, rows, restart = self.setup_action(home, platform, mode, override)
                    private = platform == 'macos' or override == 'darwin'
                    expected = 'Library/Application Support/HST Office/nssdb' if private else '.pki/nssdb'
                    self.assertEqual(target, home / expected)
                    self.assertTrue((target / 'pkcs11.txt').is_file())
                    self.assertEqual(rows[0]['status'], 'added')
                    self.assertTrue(restart)
                    text = action.result_text(load_locale('vi')['usbToken'], target, rows, restart)
                    self.assertNotIn('Kho cũ được giữ nguyên', text)
                    if private:
                        self.assertFalse((home / '.pki').exists())
                        self.assertIn('HST Office hiện dùng kho chứng thư riêng', text)

    def test_probe_does_not_create_missing_store(self):
        missing = self.base / 'missing/nssdb'
        with patch.object(database, 'user_database', side_effect=self.validate):
            rows = nss.register(missing, [dict(label='Token', path=str(SOFT))], probe=True)
        self.assertEqual(rows[0]['status'], 'added')
        self.assertFalse(missing.parent.exists())

    def test_empty_source_is_not_reported_as_preserved_store(self):
        empty = self.base / 'empty'
        empty.mkdir()
        with patch.object(database, 'user_database', side_effect=self.validate):
            target, rows, moved = store.register(empty, [dict(label='Token', path=str(SOFT))], self.base, 'macos')
        self.assertTrue(moved)
        self.assertNotEqual(target, empty)
        self.assertEqual(list(empty.iterdir()), [])
        text = action.result_text(load_locale('vi')['usbToken'], target, rows, True)
        self.assertIn('HST Office hiện dùng kho chứng thư riêng', text)
        self.assertNotIn('Kho cũ được giữ nguyên', text)

    def test_existing_sql_store_without_module_file_is_reported_as_preserved(self):
        self.path.unlink()
        before = self.snapshot()
        with patch.object(database, 'user_database', side_effect=self.validate):
            target, rows, moved = store.register(self.db, [dict(label='Token', path=str(SOFT))], self.base, 'macos')
        self.assertTrue(moved)
        self.assertEqual(self.snapshot(), before)
        text = action.result_text(load_locale('vi')['usbToken'], target, rows, True)
        self.assertIn('Kho cũ được giữ nguyên, không thay đổi', text)

    def test_reused_owned_store_is_not_reported_as_untouched(self):
        target = store.directory(self.base, 'macos')
        with patch.object(database, 'user_database', side_effect=self.validate):
            chosen, rows, moved = store.register(target, [dict(label='Token', path=str(SOFT))], self.base,
                                                 'macos', str(target))
        self.assertTrue(moved)
        self.assertEqual(chosen, target)
        self.assertTrue((target / 'pkcs11.txt').is_file())
        text = action.result_text(load_locale('vi')['usbToken'], chosen, rows, True)
        self.assertNotIn('Kho cũ được giữ nguyên', text)
