# SPDX-License-Identifier: AGPL-3.0-only
"""Regression fixtures use actual NSS SQL databases and native module loading."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import _paths
from hst_office import usb_token_nss as nss, usb_token_detect as detection

ROOTS = Path('/usr/lib/x86_64-linux-gnu/libnssckbi.so')
SOFT = Path('/usr/lib/softhsm/libsofthsm2.so')
FILES = ('pkcs11.txt', 'secmod.db', 'cert9.db', 'key4.db')


@unittest.skipUnless(shutil.which('certutil') and shutil.which('modutil') and ROOTS.exists() and SOFT.exists(),
                     'requires real NSS tools, built-in roots and SoftHSM2')
class RealNssTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.db = self.base / 'db'
        self.db.mkdir()
        self.path = self.db / 'pkcs11.txt'
        self.run_nss('certutil', '-N', '-d', 'sql:' + str(self.db), '--empty-password')
        (self.base / 'tokens').mkdir()
        config = self.base / 'softhsm.conf'
        config.write_text('directories.tokendir = %s\nobjectstore.backend = file\n' % (self.base / 'tokens'))
        env = patch.dict(os.environ, {'SOFTHSM2_CONF': str(config)})
        env.start()
        self.addCleanup(env.stop)

    def run_nss(self, *args):
        return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40).stdout.decode()

    def add_old(self, name='Feitian ePass2003 old', path=ROOTS):
        self.run_nss('modutil', '-add', name, '-libfile', str(path), '-dbdir', 'sql:' + str(self.db), '-force')

    def snapshot(self):
        return {name: (self.db / name).read_bytes() if (self.db / name).exists() else None for name in FILES}

    def register(self, mode, library=SOFT, label='Feitian ePass2003'):
        # Only the root-execution guard is bypassed in these disposable DB fixtures.
        with patch('hst_office.usb_token_db.user_database'), patch.dict(os.environ,
                {'HST_USB_TOKEN_TEST_NO_TOOLS': '1' if mode == 'pkcs11' else '0'}):
            return nss.register(self.db, [dict(label=label, path=str(library))])[0]

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

    def test_sql_lock_refuses_and_changes_nothing(self):
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            with sqlite3.connect(self.db / 'cert9.db', timeout=0) as connection:
                connection.execute('BEGIN EXCLUSIVE')
                row = self.register(mode)
                self.assertEqual(row['status'], 'error', row)
                self.assertIn('khóa độc quyền', row['error'])
            self.assertEqual(self.snapshot(), before)

    def test_unknown_format_refuses_and_changes_nothing(self):
        with self.path.open('a') as handle:
            handle.write('\nunknown-format: preserve this\n')
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            self.assertEqual(self.register(mode)['status'], 'error')
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

    def test_final_boundary_keeps_real_competing_modutil_update(self):
        original = nss.read_text(self.path)
        extra, name = nss.addition(original, 'Our module', str(SOFT))
        argv = ['modutil', '-add', 'Concurrent roots', '-libfile', str(ROOTS), '-dbdir', 'sql:' + str(self.db), '-force']
        if hasattr(nss, 'append_atomic'):  # The reviewed implementation: deterministic lost-update reproduction.
            replace = os.replace
            def competing_replace(*args):
                self.run_nss(*argv)
                return replace(*args)
            with patch.object(nss.os, 'replace', side_effect=competing_replace):
                nss.append_atomic(self.path, original, extra)
        else:
            from hst_office import usb_token_transaction as transaction
            write, processes = os.write, []
            def competing_write(*args):
                child = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(child)
                time.sleep(0.2)
                self.assertIsNone(child.poll(), 'NSS must wait for the kernel/SQL locks')
                return write(*args)
            with patch.object(transaction.os, 'write', side_effect=competing_write):
                transaction.commit_addition(self.db, original, extra)
            self.assertEqual(processes[0].wait(timeout=40), 0)
        listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
        self.assertIn(name, listing)
        self.assertIn('Concurrent roots', listing)

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

    def test_already_initialized_native_writer_waits_for_module_lease(self):
        from hst_office import usb_token_transaction as transaction
        code = '''import ctypes, sys
n = ctypes.CDLL('libnss3.so')
n.NSS_InitReadWrite.argtypes = [ctypes.c_char_p]
n.SECMOD_AddNewModule.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong]
assert n.NSS_InitReadWrite(sys.argv[1].encode()) == 0
print('ready', flush=True)
sys.stdin.read(1)
print(n.SECMOD_AddNewModule(b'Concurrent initialized NSS', sys.argv[2].encode(), 0, 0), flush=True)
n.NSS_Shutdown()
'''
        child = subprocess.Popen([sys.executable, '-c', code, 'sql:' + str(self.db), str(ROOTS)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(child.stdout.close)
        self.addCleanup(child.stdin.close)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        original = nss.read_text(self.path)
        extra, name = nss.addition(original, 'Our module', str(SOFT))
        write = os.write
        def native_writer(*args):
            child.stdin.write('x')
            child.stdin.flush()
            time.sleep(0.2)
            self.assertIsNone(child.poll())
            return write(*args)
        with patch.object(transaction.os, 'write', side_effect=native_writer):
            transaction.commit_addition(self.db, original, extra)
        self.assertEqual(child.communicate(timeout=40)[0].strip(), '0')
        self.assertEqual(child.returncode, 0)
        listing = self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db))
        self.assertIn(name, listing)
        self.assertIn('Concurrent initialized NSS', listing)

    def test_unsupported_exclusive_lock_refuses_existing_file(self):
        from hst_office import usb_token_transaction as transaction
        from hst_office.usb_token_errors import SetupError
        self.add_old()
        before = self.snapshot()
        original = nss.read_text(self.path)
        extra, _ = nss.addition(original, 'New', str(SOFT))
        with patch.object(transaction.sys, 'platform', 'darwin'), self.assertRaises(SetupError):
            transaction.commit_addition(self.db, original, extra)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.db.glob('.hst-token-backup-*')), [])

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

    def test_late_native_rename_is_detected_without_restoring_over_competitor(self):
        from hst_office import usb_token_transaction as transaction
        from hst_office.usb_token_errors import SetupError
        staging = self.base / 'competing-db'
        shutil.copytree(self.db, staging)
        self.run_nss('modutil', '-add', 'Concurrent roots', '-libfile', str(ROOTS), '-dbdir', 'sql:' + str(staging), '-force')
        winner = (staging / 'pkcs11.txt').read_bytes()
        original = nss.read_text(self.path)
        extra, _ = nss.addition(original, 'Our module', str(SOFT))
        write = os.write
        def late_rename(*args):
            os.replace(staging / 'pkcs11.txt', self.path)
            return write(*args)
        with patch.object(transaction.os, 'write', side_effect=late_rename), self.assertRaises(SetupError):
            transaction.commit_addition(self.db, original, extra)
        self.assertEqual(self.path.read_bytes(), winner)
        self.assertIn('Concurrent roots', self.run_nss('modutil', '-list', '-dbdir', 'sql:' + str(self.db)))
