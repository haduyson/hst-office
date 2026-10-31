# SPDX-License-Identifier: AGPL-3.0-only
"""Real competing NSS writers, kernel leases and SQLite exclusion."""
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from unittest.mock import patch

from usb_token_nss_fixtures import NativeNssFixture, ROOTS, SOFT, nss


class NativeConcurrencyTest(NativeNssFixture):
    def test_sql_lock_refuses_and_changes_nothing(self):
        before = self.snapshot()
        for mode in ('modutil', 'pkcs11'):
            with sqlite3.connect(self.db / 'cert9.db', timeout=0) as connection:
                connection.execute('BEGIN EXCLUSIVE')
                row = self.register(mode)
                self.assertEqual(row['status'], 'error', row)
                self.assertIn('khóa độc quyền', row['error'])
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
