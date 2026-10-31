# SPDX-License-Identifier: AGPL-3.0-only
"""Real NSS isolation for every parameter delimiter, prefix and policy form."""
import os
import shutil
import subprocess
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, ROOTS, SOFT, nss
from hst_office import usb_token_store as store


def quoted(value, left='"', right='"'):
    value = value.replace('\\', '\\\\')
    if left:
        value = value.replace(right, '\\' + right)
    else:
        value = value.replace(' ', '\\ ')
    return left + value + right


class BindingTest(NativeNssFixture):
    def migrate(self, mode):
        with patch('hst_office.usb_token_db.user_database'), patch.dict(os.environ,
                HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0'):
            return store.register(self.db, [dict(label='Token', path=str(SOFT))], self.base, 'macos')

    def tree(self):
        return {str(p.relative_to(self.db)): (p.stat().st_mode, p.stat().st_uid, p.read_bytes())
                for p in self.db.iterdir() if p.is_file()}

    def certificate(self):
        cert = self.base / 'sentinel.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=New store only', '-keyout', str(self.base / 'key.pem'), '-out', str(cert)],
                       check=True, capture_output=True, timeout=30)
        return cert

    def test_all_parameter_quotes_rebind_and_import_only_into_new_store_both_methods(self):
        self.add_old('Builtin Roots')
        original = self.path.read_text()
        # Include an external parameters field and old-directory text: never globally replace.
        vendor = self.base / 'vendor.so'
        shutil.copyfile(ROOTS, vendor)
        external = '\nlibrary=%s\nname=Other vendor\nparameters=old=%s\n\n' % (vendor, self.db)
        cert = self.certificate()
        for mode in ('modutil', 'pkcs11'):
            for outer in (False, True):
                for left, right in [('', ''), ('"', '"'), ("'", "'"), ('<', '>'), ('{', '}'), ('[', ']'), ('(', ')')]:
                    with self.subTest(mode=mode, outer=outer, delimiter=left):
                        for name in ('cert9.db', 'key4.db'):
                            shutil.copyfile(self.db / name, self.db / ('old-' + name))
                        values = [('configDir', 'sql:' + str(self.db)), ('certPrefix', 'old-'),
                                  ('keyPrefix', 'old-'), ('flags', 'optimizeSpace')]
                        params = ' '.join(k + '=' + quoted(v, left, right) for k, v in values)
                        lines = [line if not line.startswith('parameters=') else
                                 'parameters=' + (quoted(params) if outer else params) for line in original.splitlines()]
                        self.path.write_text('\n'.join(lines) + '\n' + external)
                        listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
                        self.assertNotIn('Not loaded', listing)
                        before = self.tree()
                        target, rows, moved = self.migrate(mode)
                        self.assertTrue(moved, rows)
                        copied = (target / 'pkcs11.txt').read_text()
                        self.assertIn(external, copied)
                        self.assertIn(next(line for line in original.splitlines() if line.startswith('NSS=')), copied)
                        self.assertIn('flags=' + quoted('optimizeSpace', left, right),
                                      nss._value(
                                          next(line.split('=', 1)[1] for line in copied.splitlines()
                                               if line.startswith('parameters='))))
                        self.run_nss('certutil', '-N', '-d', 'sql:' + str(target), '--empty-password')
                        self.run_nss('certutil', '-A', '-d', 'sql:' + str(target), '-n', 'sentinel',
                                     '-t', 'CT,C,C', '-a', '-i', str(cert))
                        self.assertIn('sentinel', self.run_nss('certutil', '-L', '-d', 'sql:' + str(target)))
                        for name in ('cert9.db', 'key4.db'):
                            self.assertTrue((target / name).is_file())
                            self.assertFalse((target / ('old-' + name)).exists())
                        self.assertEqual(self.tree(), before)

    def test_escaped_paths_and_values_do_not_retain_old_binding(self):
        target = self.base / 'old space " quote \\ path'
        self.db.rename(target)
        self.db, self.path = target, target / 'pkcs11.txt'
        for left, right in [('', ''), ('"', '"'), ("'", "'"), ('<', '>'), ('{', '}'), ('[', ']'), ('(', ')')]:
            with self.subTest(delimiter=left):
                params = 'configdir=' + quoted('sql:' + str(self.db), left, right) + ' certPrefix= keyPrefix= flags='
                self.path.write_text('library=\nname=NSS Internal PKCS #11 Module\nparameters=' + quoted(params)
                                     + '\nNSS=Flags=internal,critical\n\n')
                self.run_nss('certutil', '-L', '-d', 'sql:' + str(self.db))
                before = self.tree()
                new, rows, moved = self.migrate('pkcs11')
                self.assertTrue(moved, rows)
                self.run_nss('certutil', '-N', '-d', 'sql:' + str(new), '--empty-password')
                self.assertTrue((new / 'cert9.db').is_file())
                self.assertEqual(self.tree(), before)

    def test_unsupported_pinned_policy_refuses_before_allocation_both_methods(self):
        original = self.path.read_text()
        for mode in ('modutil', 'pkcs11'):
            for key, value in [('flags', 'readOnly'), ('flags', 'noCertDB'), ('flags', 'noModDB'),
                               ('tokens', '0x2=[configdir=' + str(self.db) + ']'), ('updateDir', str(self.db))]:
                for left, right in [('', ''), ('"', '"'), ("'", "'"), ('<', '>'), ('{', '}'), ('[', ']'), ('(', ')')]:
                    with self.subTest(mode=mode, key=key, value=value, delimiter=left):
                        params = 'configdir=' + quoted('sql:' + str(self.db)) + ' ' + key + '=' + quoted(value, left, right)
                        self.path.write_text('\n'.join('parameters=' + quoted(params) if line.startswith('parameters=')
                                                       else line for line in original.splitlines()) + '\n')
                        before = self.tree()
                        new, rows, moved = self.migrate(mode)
                        self.assertFalse(moved)
                        self.assertEqual(new, self.db)
                        self.assertEqual(rows[0]['status'], 'error')
                        self.assertIn('Bảo mật → Chứng chỉ', rows[0]['error'])
                        self.assertFalse((self.base / 'Library').exists())
                        self.assertEqual(self.tree(), before)
