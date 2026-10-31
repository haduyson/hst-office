# SPDX-License-Identifier: AGPL-3.0-only
"""Native NSS validation, detection policy and Vietnamese error regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, ROOTS, SOFT, nss
from hst_office import usb_token_detect as detection


class NativeValidationTest(NativeNssFixture):
    def test_corrupt_library_fails_every_time_both_methods(self):
        bad = self.base / 'vendor.so'
        bad.write_text('not a shared library')
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            for _ in range(2):
                row = self.register(mode, bad)
                self.assertEqual(row['status'], 'error', row)
                self.assertIn('không nạp được', row['error'])
                self.assertEqual(self.snapshot(), before)

    def test_existing_unloadable_record_is_not_reported_registered(self):
        bad = self.base / 'vendor.so'
        bad.write_text('not a shared library')
        with self.path.open('a') as handle:
            handle.write('\nlibrary=%s\nname=Broken\n\n' % bad)
        self.assertIn('Not loaded', self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db)))
        before = self.snapshot()
        self.assertEqual(self.register('pkcs11', bad)['status'], 'error')
        self.assertEqual(self.snapshot(), before)

    def test_catalog_exclusion_prevents_registration_in_real_db(self):
        root = self.base / 'root'
        library = root / 'usr/lib/libcastle.so.1.0.0'
        library.parent.mkdir(parents=True)
        library.symlink_to(SOFT)
        config = root / 'home/.config/pkcs11/modules/vendor.module'
        config.parent.mkdir(parents=True)
        config.write_text('module: /usr/lib/libcastle.so.1.0.0\ndisable-in: soffice.bin\n')
        before = self.snapshot()
        found = detection.detect('linux', root, root / 'home')
        self.assertEqual(found, [])
        with patch('hst_office.usb_token_db.user_database'):
            self.assertEqual(nss.register(self.db, found), [])
        self.assertEqual(self.snapshot(), before)

    def test_enabled_alias_override_registers_real_driver_both_methods(self):
        for mode in ('modutil', 'pkcs11'):
            with self.subTest(mode=mode):
                self.setUp()
                self.add_old()
                before = self.snapshot()
                root = self.base / 'root'
                library = root / 'usr/lib/libcastle.so.1.0.0'
                library.parent.mkdir(parents=True)
                library.symlink_to(SOFT)
                (root / 'active.so').symlink_to(library)
                for directory, value in (('usr/share/p11-kit/modules', '/usr/lib/libcastle.so.1.0.0'),
                                         ('home/.config/pkcs11/modules', '/active.so')):
                    config = root / directory / 'token.module'
                    config.parent.mkdir(parents=True)
                    config.write_text('module: ' + value + '\n')
                found = detection.detect('linux', root, root / 'home', entries=[])
                self.assertEqual(len(found), 1)
                row = self.register(mode, found[0]['path'], found[0]['label'])
                self.assertEqual(row['status'], 'added', row)
                listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
                self.assertIn('HST p11-kit: token', listing)
                self.assertIn('Feitian ePass2003 old', listing)
                self.assertNotIn('Not loaded', listing)
                self.assertTrue(self.path.read_bytes().startswith(before['pkcs11.txt']))
                for name in ('cert9.db', 'key4.db', 'secmod.db'):
                    self.assertEqual(self.snapshot()[name], before[name])

    def test_real_permission_failure_is_vietnamese_and_preserves_db(self):
        self.base.chmod(0o755)
        uid = 65534 if os.geteuid() == 0 else os.geteuid()
        if os.geteuid() == 0:
            for path in [self.db, *self.db.iterdir()]:
                os.chown(path, uid, uid)
        self.db.chmod(0o500)
        self.addCleanup(self.db.chmod, 0o700)
        before = self.snapshot()
        code = ('import json,sys; from pathlib import Path; from hst_office.usb_token_nss import register; '
                'print(json.dumps(register(Path(sys.argv[1]), [dict(label="Roots",path=sys.argv[2])]),ensure_ascii=False))')
        env = dict(os.environ, PYTHONPATH=str(Path(nss.__file__).resolve().parents[1]))
        options = dict(user=uid, group=uid) if os.geteuid() == 0 else {}
        output = subprocess.run([sys.executable, '-c', code, str(self.db), str(ROOTS)], env=env,
                                capture_output=True, text=True, check=True, timeout=40, **options)
        row = json.loads(output.stdout)[0]
        self.assertEqual(row['status'], 'error')
        self.assertIn('quyền', row['error'])
        self.assertNotIn('Permission denied', row['error'])
        self.assertNotIn('Errno', row['error'])
        self.assertEqual(self.snapshot(), before)

    def test_wrong_architecture_is_failed_without_registration(self):
        library = self.base / 'wrong-architecture.so'
        content = bytearray(SOFT.read_bytes())
        self.assertEqual(content[:4], b'\x7fELF')
        content[18:20] = (183).to_bytes(2, 'little')  # AArch64 instead of the x86_64 fixture.
        library.write_bytes(content)
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            row = self.register(mode, library)
            self.assertEqual(row['status'], 'error', row)
            self.assertIn('kiến trúc', row['error'])
            self.assertEqual(self.snapshot(), before)

    def test_missing_dependency_is_failed_without_registration(self):
        library = self.base / 'missing-dependency.so'
        content = SOFT.read_bytes()
        self.assertIn(b'libcrypto.so.3\0', content)
        library.write_bytes(content.replace(b'libcrypto.so.3\0', b'libabsent.so.9\0'))
        before = self.snapshot()
        row = self.register('pkcs11', library)
        self.assertEqual(row['status'], 'error', row)
        self.assertIn('phụ thuộc', row['error'])
        self.assertEqual(self.snapshot(), before)
