#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Round-4 real HST/NSS binding and inherited environment regressions, both backends."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('HST_VCLPLUGIN', 'gen')
import hst_gui
from usb_token_harness import install, setup_dialog
from usb_token_private_harness import browser_profile, snapshot, preserved_records

ROOT = Path(__file__).resolve().parents[2]
CONFIG = '/org.openoffice.Office.Common/Security/Scripting'
CASES = ('quoted', 'unquoted', 'pinned-darwin', 'pinned-linux-reader', 'pinned-linux-safe')


def run(*args, env=None):
    return subprocess.run(args, env=env, check=True, capture_output=True, text=True, timeout=40).stdout


def certdir(office):
    from com.sun.star.beans import PropertyValue
    provider = office.service('com.sun.star.configuration.ConfigurationProvider')
    node = provider.createInstanceWithArguments('com.sun.star.configuration.ConfigurationAccess',
                                              (PropertyValue(Name='nodepath', Value=CONFIG),))
    return node.getPropertyValue('CertDir')


def export(doc, path):
    from com.sun.star.beans import PropertyValue
    doc.storeToURL(path.as_uri(), (PropertyValue(Name='FilterName', Value='writer_pdf_Export'),))


def sql_paths(office, db):
    opened = {os.readlink(fd) for fd in Path('/proc/%d/fd' % office.pid).iterdir()}
    actual = {path for path in opened if Path(path).name in ('cert9.db', 'key4.db')}
    assert actual == {str(db / name) for name in ('cert9.db', 'key4.db')}, actual


def run_case(args, mode, kind):
    base = args.workdir / (mode + '-' + kind)
    library = base / 'drivers/usr/lib/libcastle.so.1.0.0'
    library.parent.mkdir(parents=True)
    library.symlink_to('/usr/lib/softhsm/libsofthsm2.so')
    tokens = base / 'tokens'
    tokens.mkdir()
    conf = base / 'softhsm.conf'
    conf.write_text('directories.tokendir = %s\nobjectstore.backend = file\n' % tokens)
    env = dict(SOFTHSM2_CONF=str(conf), HST_USB_TOKEN_TEST_ROOT=str(base / 'drivers'),
               HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0')
    darwin = kind in ('quoted', 'unquoted', 'pinned-darwin')
    if darwin:
        env['HST_USB_TOKEN_TEST_PLATFORM'] = 'darwin'
    office = hst_gui.Office(args.instdir, str(base / 'office'), args.port, display=args.display, env=env)
    source, _ = browser_profile(office)
    pinned = kind.startswith('pinned')
    if pinned:
        office.extra_env['MOZILLA_CERTIFICATE_FOLDER'] = str(source)
    if kind == 'quoted':
        path = source / 'pkcs11.txt'
        path.write_text('\n'.join('parameters="' + line.split('=', 1)[1].replace('\\', '\\\\').replace('"', '\\"') + '"'
                                  if line.startswith('parameters=') else line for line in path.read_text().splitlines()) + '\n')
    before = snapshot(source)
    private = Path(office.workdir) / 'home' / ('Library/Application Support/HST Office' if darwin else '.local/share/hst-office')
    checks = {}
    try:
        install(office, args.oxt)
        doc = office.load('private:factory/swriter')
        export(doc, base / 'before.pdf')
        sql_paths(office, source)
        assert snapshot(source) == before
        checks['source_parameters_load_in_real_core'] = True
        selected = certdir(office)
        refusal = pinned and kind != 'pinned-linux-safe'
        with (source / 'pkcs11.txt').open('rb') if kind == 'pinned-linux-reader' else nullcontext():
            for _ in range(2):
                text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
                if refusal:
                    assert all(word in text for word in ('MOZILLA_CERTIFICATE_FOLDER', 'chưa thay đổi', 'Linux',
                                                         'bỏ thiết lập', 'khởi động lại HST Office')), text
                    assert 'Đã tìm thấy và đăng ký' not in text and 'Đã đăng ký từ trước' not in text, text
                    assert certdir(office) == selected and not private.exists()
                    assert snapshot(source) == before
                else:
                    assert 'Đã tìm thấy và đăng ký' in text or 'Đã đăng ký từ trước' in text, text
        checks['repeat_refuses_without_mutation' if refusal else 'registration_and_repeat_succeed'] = True
        db = source if pinned else private / 'nssdb'
        if not pinned:
            assert certdir(office) == str(db)
            assert snapshot(source) == before
            preserved_records((db / 'pkcs11.txt').read_bytes(), before['pkcs11.txt'][1])
        doc.close(True)
        office.stop()
        office.start(fresh=False)
        doc = office.load('private:factory/swriter')
        export(doc, base / 'after.pdf')
        assert Path(office.service('com.sun.star.xml.crypto.NSSInitializer').NSSPath) == db
        sql_paths(office, db)
        checks['restart_opens_exact_selected_sql_files'] = True
        if refusal:
            with (source / 'pkcs11.txt').open('rb') if kind == 'pinned-linux-reader' else nullcontext():
                text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
            assert 'MOZILLA_CERTIFICATE_FOLDER' in text and 'chưa thay đổi' in text, text
            assert certdir(office) == selected and not private.exists()
            assert snapshot(source) == before
            checks['inherited_pin_still_refused_after_restart'] = True
        else:
            text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
            assert 'Đã đăng ký từ trước' in text and 'Khởi động lại HST Office rồi' not in text, text
            checks['effective_registration_after_restart'] = True
        doc.close(True)
        office.stop()
        if not pinned:
            cert = base / 'sentinel.pem'
            run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=New store only',
                '-keyout', str(base / 'key.pem'), '-out', str(cert))
            native_env = dict(os.environ, **env)
            run('certutil', '-A', '-d', 'sql:' + str(db), '-n', 'sentinel', '-t', 'CT,C,C', '-a', '-i', str(cert), env=native_env)
            assert 'sentinel' in run('certutil', '-L', '-d', 'sql:' + str(db), env=native_env)
            assert 'sentinel' not in run('certutil', '-L', '-d', 'sql:' + str(source), env=native_env)
            assert snapshot(source) == before
            checks['import_into_new_store_cannot_change_old_store'] = True
    finally:
        office.stop()
    print('%s %s: PASS (%d checks)' % (mode, kind, len(checks)), flush=True)
    return dict(mode=mode, case=kind, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instdir', default='/opt/hst')
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--oxt', type=Path, default=ROOT / 'dist/extensions/hst-vietnamese-tools.oxt')
    parser.add_argument('--display', default=':99')
    parser.add_argument('--port', type=int, default=2283)
    parser.add_argument('--mode', choices=('both', 'modutil', 'pkcs11'), default='both')
    parser.add_argument('--case', choices=('all', *CASES), default='all')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Use an unprivileged account and private HOME.')
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    if args.mode != 'both' and args.case != 'all':
        hst_gui.setup_uno(args.instdir)
        result = run_case(args, args.mode, args.case)
        (args.workdir / (args.mode + '-' + args.case) / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        return
    results = []
    try:
        for mode in (('modutil', 'pkcs11') if args.mode == 'both' else (args.mode,)):
            for kind in (CASES if args.case == 'all' else (args.case,)):
                # A fresh PyUNO bridge per case avoids stale proxies across many office lifetimes.
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--instdir', args.instdir,
                                '--workdir', str(args.workdir), '--oxt', str(args.oxt), '--display', args.display,
                                '--port', str(args.port), '--mode', mode, '--case', kind], check=True)
                results.append(json.loads((args.workdir / (mode + '-' + kind) / 'result.json').read_text()))
    finally:
        (args.workdir / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: %d cases, %d checks' % (len(results), sum(len(r['checks']) for r in results)))


if __name__ == '__main__':
    main()
