# SPDX-License-Identifier: AGPL-3.0-only
"""Automatic private-store migration with real NSS and read-only source profiles."""
import os
import shutil
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, ROOTS, SOFT, nss
from hst_office import usb_token_store as store, usb_token_transaction as transaction


class PrivateStoreTest(NativeNssFixture):
    def migrate(self, modules=None, platform='macos', configured='', mode='pkcs11'):
        modules = modules or [dict(label='VNPT-CA', path=str(SOFT))]
        with patch('hst_office.usb_token_db.user_database'), patch.dict(os.environ,
                HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0'):
            return store.register(self.db, modules, self.base, platform, configured)

    def profile(self):
        self.add_old('Builtin Roots', ROOTS)
        vendor = self.base / 'another vendor.so'
        shutil.copyfile(ROOTS, vendor)
        self.add_old('Another vendor', vendor)
        return vendor

    def tree(self, db):
        return {str(p.relative_to(db)): (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
                for p in db.rglob('*')}

    def test_firefox_records_preserved_old_tree_unchanged_both_methods(self):
        vendor = self.profile()
        self.path.chmod(0o400)
        self.db.chmod(0o500)
        self.addCleanup(self.db.chmod, 0o700)
        before, original = self.tree(self.db), self.path.read_bytes()
        for mode in ('modutil', 'pkcs11'):
            with self.subTest(mode=mode), patch.object(transaction, 'module_lease', side_effect=AssertionError('no locks')):
                target, rows, moved = self.migrate(mode=mode)
            self.assertTrue(moved, rows)
            self.assertEqual(rows[0]['status'], 'added')
            self.assertEqual(self.tree(self.db), before)
            self.assertTrue(store.owned(target))
            self.assertTrue((target / 'pkcs11.txt').read_bytes().startswith(original))
            self.assertEqual({r['library'] for r in nss.parse(nss.read_text(target / 'pkcs11.txt'))},
                             {'', str(ROOTS), str(vendor), str(SOFT)})
            for name in ('cert9.db', 'key4.db'):
                self.assertFalse((target / name).exists())
            backup = next(target.glob('.hst-token-backup-*'))
            self.assertEqual((backup / 'pkcs11.txt').read_bytes(), original)
            self.assertEqual((backup / 'pkcs11.txt').stat().st_mode & 0o777, 0o600)
            self.run_nss('certutil', '-N', '-d', 'sql:' + str(target), '--empty-password')
            listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(target))
            for name in ('NSS Internal PKCS #11 Module', 'Builtin Roots', 'Another vendor', 'HST VNPT-CA'):
                self.assertIn(name, listing)
            self.assertNotIn('Not loaded', listing)
            self.assertEqual(self.tree(self.db), before)

    def test_second_driver_then_idempotent_rerun_both_methods(self):
        for mode in ('modutil', 'pkcs11'):
            with self.subTest(mode=mode):
                first, rows, _ = self.migrate(mode=mode)
                self.run_nss('certutil', '-N', '-d', 'sql:' + str(first), '--empty-password')
                self.db = first
                original = self.tree(first)
                modules = [dict(label='VNPT-CA', path=str(SOFT)), dict(label='Second', path=str(ROOTS))]
                second, rows, moved = self.migrate(modules, configured=str(first), mode=mode)
                self.assertTrue(moved, rows)
                self.assertNotEqual(first, second)
                self.assertEqual([r['status'] for r in rows], ['existing', 'added'])
                self.assertEqual(self.tree(first), original)
                self.run_nss('certutil', '-N', '-d', 'sql:' + str(second), '--empty-password')
                listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(second))
                self.assertIn('HST Second', listing)
                self.assertNotIn('Not loaded', listing)
                self.db = second
                before = self.tree(second)
                again, rows, moved = self.migrate(modules, configured=str(second), mode=mode)
                self.assertEqual(again, second)
                self.assertFalse(moved)
                self.assertEqual([r['status'] for r in rows], ['existing', 'existing'])
                self.assertEqual(self.tree(second), before)
                # Use a fresh source for the other method.
                self.setUp()

    def test_all_validated_additions_published_in_one_link(self):
        modules = [dict(label='A', path=str(SOFT)), dict(label='B', path=str(ROOTS))]
        with patch.object(transaction.os, 'link', wraps=os.link) as link:
            target, rows, moved = self.migrate(modules)
        self.assertTrue(moved, rows)
        self.assertEqual([r['status'] for r in rows], ['added', 'added'])
        self.assertEqual(link.call_count, 1)
        self.assertEqual(link.call_args.args[1], target / 'pkcs11.txt')
        self.assertEqual(len(nss.parse(nss.read_text(target / 'pkcs11.txt'))), 3)

    def test_linux_unavailable_lease_uses_private_store_read_only(self):
        before = self.tree(self.db)
        # A real competing reader prevents the disposable worker's write lease.
        with self.path.open('rb'):
            target, rows, moved = self.migrate(platform='linux')
        self.assertTrue(moved, rows)
        self.assertEqual(target, self.base / '.local/share/hst-office/nssdb')
        self.assertEqual(self.tree(self.db), before)

    def test_normal_linux_keeps_existing_lease_transaction(self):
        original = self.path.read_bytes()
        target, rows, moved = self.migrate(platform='linux')
        self.assertFalse(moved)
        self.assertEqual(target, self.db)
        self.assertEqual(rows[0]['status'], 'added')
        self.assertTrue(self.path.read_bytes().startswith(original))
        backup = next(self.db.glob('.hst-token-backup-*'))
        self.assertEqual((backup / 'pkcs11.txt').read_bytes(), original)
        self.assertFalse((self.base / '.local').exists())

    def test_fresh_macos_store_accepts_multiple_drivers_together(self):
        self.db = self.base / 'empty-db'
        self.db.mkdir()
        modules = [dict(label='First', path=str(SOFT)), dict(label='Second', path=str(ROOTS))]
        target, rows, moved = self.migrate(modules)
        self.assertTrue(moved, rows)
        self.assertEqual([r['status'] for r in rows], ['added', 'added'])
        self.assertTrue(store.owned(target))
        self.assertEqual(list(self.db.iterdir()), [])

    def test_invalid_library_does_not_create_or_select_store(self):
        bad = self.base / 'broken.so'
        bad.write_bytes(b'not a driver')
        before = self.tree(self.db)
        target, rows, moved = self.migrate([dict(label='Bad', path=str(bad))])
        self.assertEqual(rows[0]['status'], 'error')
        self.assertFalse(moved)
        self.assertEqual(target, self.db)
        self.assertFalse((self.base / 'Library').exists())
        self.assertEqual(self.tree(self.db), before)

    def test_mixed_valid_invalid_modules_only_publishes_validated_driver(self):
        bad = self.base / 'broken.so'
        bad.touch()
        target, rows, moved = self.migrate([dict(label='Good', path=str(SOFT)), dict(label='Bad', path=str(bad))])
        self.assertTrue(moved)
        self.assertEqual([r['status'] for r in rows], ['added', 'error'])
        self.assertNotIn(str(bad), nss.read_text(target / 'pkcs11.txt'))

    def test_no_clobber_race_keeps_competing_file_and_original(self):
        before = self.tree(self.db)
        link = os.link
        def competing_create(source, target):
            target.write_bytes(b'competing registration')
            return link(source, target)
        with patch.object(transaction.os, 'link', side_effect=competing_create):
            target, rows, moved = self.migrate()
        self.assertFalse(moved)
        self.assertEqual(rows[0]['status'], 'error')
        self.assertEqual(self.tree(self.db), before)
        private = self.base / 'Library/Application Support/HST Office/nssdb'
        self.assertEqual((private / 'pkcs11.txt').read_bytes(), b'competing registration')
        self.assertEqual(list(private.glob('.hst-token-backup-*')), [])

    def test_fsync_failure_rolls_back_without_touching_original(self):
        target = store.directory(self.base, 'macos')
        before = self.tree(self.db)
        with patch.object(store.os, 'fsync', side_effect=OSError('disk full')), self.assertRaises(OSError):
            store.publish(self.db, target, nss.read_text(self.path), 'new')
        self.assertFalse((target / 'pkcs11.txt').exists())
        self.assertEqual(list(target.glob('.hst-token-backup-*')), [])
        self.assertEqual(self.tree(self.db), before)

    def test_source_change_before_publication_refuses(self):
        original = nss.read_text(self.path)
        target = store.directory(self.base, 'macos')
        self.path.write_text(original + '# concurrent change\n')
        with self.assertRaisesRegex(ValueError, 'vừa thay đổi'):
            store.publish(self.db, target, original, original)
        self.assertFalse((target / 'pkcs11.txt').exists())
        self.assertEqual(nss.read_text(self.path), original + '# concurrent change\n')
