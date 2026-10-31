# SPDX-License-Identifier: AGPL-3.0-only
"""Seed Firefox records and assert the Darwin fallback leaves its source intact."""
from pathlib import Path
import shutil
import subprocess

ROOTS = Path('/usr/lib/x86_64-linux-gnu/libnssckbi.so')


def snapshot(path):
    return {str(p.relative_to(path)): (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
            for p in path.rglob('*')}


def preserved_records(saved, original):
    # Internal parameters must be rebound. Retain every other original byte.
    strip = lambda data: b'\n'.join(line for line in data.split(b'\n') if not line.startswith(b'parameters='))
    assert strip(saved).startswith(strip(original))


def browser_profile(office):
    home = Path(office.workdir) / 'home'
    source = home / '.mozilla/firefox/default'
    source.mkdir(parents=True)
    (source.parent / 'profiles.ini').write_text('[Profile0]\nName=default\nIsRelative=1\nPath=default\nDefault=1\n')
    vendor = home / 'another-vendor.so'
    shutil.copyfile(ROOTS, vendor)
    subprocess.run(['certutil', '-N', '-d', 'sql:' + str(source), '--empty-password'], check=True, capture_output=True)
    for name, library in [('Builtin Roots', ROOTS), ('Another vendor', vendor)]:
        subprocess.run(['modutil', '-add', name, '-libfile', str(library), '-dbdir', 'sql:' + str(source), '-force'],
                       check=True, capture_output=True)
    return source, snapshot(source)


def check_private(db, source, before, env, label='HST Feitian ePass2003'):
    assert snapshot(source) == before, 'The original Firefox store changed'
    preserved_records((db / 'pkcs11.txt').read_bytes(), before['pkcs11.txt'][1])
    assert db.stat().st_mode & 0o777 == 0o700
    assert (db / '.hst-office-nssdb').is_file()
    listing = subprocess.run(['modutil', '-list', '-dbdir', 'sql:' + str(db)], check=True,
                             capture_output=True, text=True, env=env).stdout
    for name in ('NSS Internal PKCS #11 Module', 'Builtin Roots', 'Another vendor', label):
        assert name in listing, listing
    assert 'Not loaded' not in listing, listing
