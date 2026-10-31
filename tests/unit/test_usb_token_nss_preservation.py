# SPDX-License-Identifier: AGPL-3.0-only
"""Existing module bytes, backups and recovery with real NSS databases."""
import os
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, ROOTS, SOFT, nss


class NativePreservationTest(NativeNssFixture):
    def test_crlf_refused_without_mutation_both_methods(self):
        self.add_old()
        self.path.write_bytes(self.path.read_bytes().replace(b'\n', b'\r\n'))
        self.assertIn('Feitian ePass2003 old', self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db)))
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            with self.subTest(mode=mode):
                self.assertEqual(self.register(mode)['status'], 'error')
                self.assertEqual(self.snapshot(), before)

    def test_prefix_and_exact_names_preserved_both_methods(self):
        for mode in ('modutil', 'pkcs11'):
            for old in ('Feitian ePass2003 old', 'Feitian ePass2003', '"Feitian ePass2003"'):
                with self.subTest(mode=mode, old=old):
                    self.setUp()
                    self.add_old(old)
                    self.path.chmod(0o640)
                    before = self.snapshot()
                    row = self.register(mode)
                    self.assertEqual(row['status'], 'added', row)
                    self.assertTrue(self.path.read_bytes().startswith(before['pkcs11.txt']))
                    self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
                    listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
                    self.assertIn(old.strip('"'), listing)
                    self.assertIn('HST Feitian ePass2003', listing)
                    self.assertNotIn('Not loaded', listing)
                    for name in ('cert9.db', 'key4.db', 'secmod.db'):
                        self.assertEqual(self.snapshot()[name], before[name])
                    backups = list(self.db.glob('.hst-token-backup-*'))
                    self.assertEqual(len(backups), 1)
                    for name, content in before.items():
                        if content is not None:
                            self.assertEqual((backups[0] / name).read_bytes(), content)
                    saved = self.snapshot()
                    self.assertEqual(self.register(mode)['status'], 'existing')
                    self.assertEqual(self.snapshot(), saved)

    def test_library_prefix_preserves_unrelated_registration(self):
        old, new = self.base / 'module-old', self.base / 'module'
        old.symlink_to(ROOTS)
        new.symlink_to(SOFT)
        self.add_old(path=old)
        before = self.path.read_bytes()
        self.assertEqual(self.register('modutil', new)['status'], 'added')
        self.assertTrue(self.path.read_bytes().startswith(before))
        self.assertIn('Feitian ePass2003 old', self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db)))

    def test_unknown_format_refuses_and_changes_nothing(self):
        with self.path.open('a') as handle:
            handle.write('\nunknown-format: preserve this\n')
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            self.assertEqual(self.register(mode)['status'], 'error')
            self.assertEqual(self.snapshot(), before)

    def test_write_failure_restores_all_four_files(self):
        from hst_office import usb_token_transaction as transaction
        self.add_old()
        before = self.snapshot()
        original = nss.read_text(self.path)
        extra, _ = nss.addition(original, 'New', str(SOFT))
        write = os.write
        def partial_then_error(fd, payload):
            write(fd, payload[:5])
            raise OSError('No space left on device')
        with patch.object(transaction.os, 'write', side_effect=partial_then_error), self.assertRaises(OSError):
            transaction.commit_addition(self.db, original, extra)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.db.glob('.hst-token-backup-*')), [])

    def test_unsupported_exclusive_lock_refuses_existing_file(self):
        from hst_office import usb_token_transaction as transaction
        from hst_office.usb_token_errors import SetupError
        self.add_old()
        before = self.snapshot()
        original = nss.read_text(self.path)
        extra, _ = nss.addition(original, 'New', str(SOFT))
        for _ in range(2):  # Retrying does not make the macOS restriction transient.
            with patch.object(transaction.sys, 'platform', 'darwin'), self.assertRaisesRegex(SetupError, 'chưa hỗ trợ khóa an toàn'):
                transaction.commit_addition(self.db, original, extra)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(list(self.db.glob('.hst-token-backup-*')), [])

    def test_macos_new_file_creation_then_second_driver_refusal(self):
        from hst_office import usb_token_transaction as transaction
        from hst_office.usb_token_errors import SetupError
        db = self.base / 'separate-empty-db'
        db.mkdir()
        extra, name = nss.addition('', 'First token', str(SOFT))
        with patch.object(transaction.sys, 'platform', 'darwin'):
            transaction.commit_addition(db, '', extra)
            original = (db / 'pkcs11.txt').read_bytes()
            second, _ = nss.addition(original.decode(), 'Second token', str(ROOTS))
            with self.assertRaises(SetupError):
                transaction.commit_addition(db, original.decode(), second)
        self.assertEqual((db / 'pkcs11.txt').read_bytes(), original)
        self.assertEqual((db / 'pkcs11.txt').stat().st_mode & 0o777, 0o600)
        self.run_nss('certutil', '-N', '-d', 'sql:' + str(db), '--empty-password')
        listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(db))
        self.assertIn(name, listing)
        self.assertNotIn('Not loaded', listing)
