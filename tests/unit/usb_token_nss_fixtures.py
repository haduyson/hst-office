# SPDX-License-Identifier: AGPL-3.0-only
"""Shared disposable SQL databases and independent native NSS assertions."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import _paths
from hst_office import usb_token_nss as nss

ROOTS = Path('/usr/lib/x86_64-linux-gnu/libnssckbi.so')
SOFT = Path('/usr/lib/softhsm/libsofthsm2.so')
FILES = ('pkcs11.txt', 'secmod.db', 'cert9.db', 'key4.db')


@unittest.skipUnless(shutil.which('certutil') and shutil.which('modutil') and ROOTS.exists() and SOFT.exists(),
                     'requires real NSS tools, built-in roots and SoftHSM2')
class NativeNssFixture(unittest.TestCase):
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
