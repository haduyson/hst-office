# SPDX-License-Identifier: AGPL-3.0-only
"""Pinned NSS stores: real Linux leases, native registration and no unused copy."""
from contextlib import nullcontext
import os
from pathlib import Path
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, SOFT
from hst_office import usb_token as action, usb_token_db as database, usb_token_store as store


class PinnedStoreTest(NativeNssFixture):
    def setup_action(self, mode, platform, configured=''):
        modules = [dict(label='Token', path=str(SOFT))]
        with patch.object(database, 'office_state', return_value=(configured, str(self.db), False, None)), \
                patch.object(database, 'user_database'), patch.object(action, 'detect', return_value=modules), \
                patch.object(action, 'platform_name', return_value='linux'), patch.object(Path, 'home', return_value=self.base), \
                patch.dict(os.environ, MOZILLA_CERTIFICATE_FOLDER=str(self.db), HST_USB_TOKEN_TEST_PLATFORM=platform,
                           HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0'):
            return action.setup(None)

    def tree(self):
        return {str(p.relative_to(self.base)): (p.stat().st_mode, p.stat().st_uid,
                                               p.read_bytes() if p.is_file() else None) for p in self.base.rglob('*')}

    def test_pinned_darwin_and_linux_open_reader_refuse_without_changes_both_modes(self):
        self.add_old('Builtin Roots')
        for mode in ('modutil', 'pkcs11'):
            for platform in ('darwin', 'linux'):
                with self.subTest(mode=mode, platform=platform):
                    before = self.tree()
                    with self.path.open('rb') if platform == 'linux' else nullcontext():
                        with patch.object(database, 'set_fallback') as select, self.assertRaisesRegex(
                                ValueError, 'MOZILLA_CERTIFICATE_FOLDER.*chưa thay đổi.*Linux.*bỏ thiết lập'):
                            self.setup_action(mode, platform)
                    select.assert_not_called()
                    self.assertEqual(self.tree(), before)
                    self.assertNotIn('Not loaded', self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db)))

    def test_safe_linux_registers_in_pinned_store_ignoring_unused_marked_certdir(self):
        self.addCleanup(action._pending_restart.clear)
        for mode in ('modutil', 'pkcs11'):
            with self.subTest(mode=mode):
                unused = store.directory(self.base, 'linux')
                action._pending_restart.add(str(unused))
                unused_before = list(unused.iterdir())
                with patch.object(database, 'set_fallback') as select:
                    chosen, rows, _ = self.setup_action(mode, 'linux', str(unused))
                select.assert_not_called()
                self.assertEqual(chosen, self.db)
                self.assertEqual(rows[0]['status'], 'added')
                self.assertEqual(list(unused.iterdir()), unused_before)
                listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
                self.assertIn('HST Token', listing)
                self.assertNotIn('Not loaded', listing)
                self.setUp()

    def test_pinned_missing_directory_is_not_created_on_darwin(self):
        self.db = self.base / 'missing'
        before = self.tree()
        with self.assertRaisesRegex(ValueError, 'MOZILLA_CERTIFICATE_FOLDER'):
            self.setup_action('pkcs11', 'darwin')
        self.assertEqual(self.tree(), before)

    def test_preflight_ownership_check_does_not_create_missing_store(self):
        missing = self.base / 'missing'
        # Root fixture: bypass just the root guard, keep the actual owner checks.
        ids = [2000, 0] if os.geteuid() == 0 else [os.geteuid(), os.geteuid()]
        with patch.object(database.os, 'geteuid', side_effect=ids):
            database.user_database(missing, create=False)
        self.assertFalse(missing.exists())
