#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Real UNO/NSS CertDir regressions, with Firefox present; no signing dependencies."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('HST_VCLPLUGIN', 'gen')
import hst_gui
from usb_token_harness import install, setup_dialog

ROOT = Path(__file__).resolve().parents[2]
CONFIG = '/org.openoffice.Office.Common/Security/Scripting'


def sql_db(path):
    path.mkdir(parents=True)
    subprocess.run(['certutil', '-N', '-d', 'sql:' + str(path), '--empty-password'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def export_pdf(doc, path):
    from com.sun.star.beans import PropertyValue
    doc.storeToURL(path.as_uri(), (PropertyValue(Name='FilterName', Value='writer_pdf_Export'),))


def run_case(args, mode, kind):
    base = args.workdir / (mode + '-' + kind)
    root, home = base / 'drivers', base / 'office/home'
    browser = home / '.mozilla/firefox/test'
    configured = home / 'configured'
    sql_db(browser)
    (browser.parent / 'profiles.ini').write_text('[Profile0]\nName=default\nIsRelative=1\nPath=test\nDefault=1\n')
    if kind != 'missing':
        sql_db(configured)
    value = ('sql:' if kind == 'sql' else '') + str(configured)
    if kind == 'tilde':
        value = '~/configured'
    chosen = configured if kind == 'absolute' else browser
    library = root / 'usr/lib/libcastle.so.1.0.0'
    library.parent.mkdir(parents=True)
    library.symlink_to('/usr/lib/softhsm/libsofthsm2.so')
    tokens = base / 'tokens'
    tokens.mkdir()
    conf = base / 'softhsm.conf'
    conf.write_text('directories.tokendir = %s\nobjectstore.backend = file\n' % tokens)
    env = dict(SOFTHSM2_CONF=str(conf), HST_USB_TOKEN_TEST_ROOT=str(root),
               HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0')
    office = hst_gui.Office(args.instdir, str(base / 'office'), args.port, display=args.display,
                            config=[(CONFIG, 'CertDir', value)], env=env)
    checks = {}
    initial = (chosen / 'pkcs11.txt').read_bytes()
    other = (configured / 'pkcs11.txt').read_bytes() if configured.exists() and chosen != configured else None
    try:
        install(office, args.oxt)
        doc = office.load('private:factory/swriter')
        nss = office.service('com.sun.star.xml.crypto.NSSInitializer')
        if kind == 'tilde':
            # This core exposes the literal shell path. Setup must refuse it,
            # rather than silently register into an expanded, different DB.
            assert nss.NSSPath == value, nss.NSSPath
            text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
            assert 'đường dẫn tuyệt đối' in text, text
            assert (browser / 'pkcs11.txt').read_bytes() == initial
            assert (configured / 'pkcs11.txt').read_bytes() == other
            checks['literal_core_path_refused_without_mutation'] = True
            doc.close(True)
            print('%s %s: 1 check passed' % (mode, kind), flush=True)
            return dict(mode=mode, configured=kind, checks=checks)
        assert Path(nss.NSSPath) == chosen, (kind, nss.NSSPath, chosen)
        assert not nss.IsNSSinitialized
        checks['actual_core_selection_before_initialization'] = True
        text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
        assert 'Đã tìm thấy và đăng ký:' in text and str(chosen) in text, text
        assert (chosen / 'pkcs11.txt').read_bytes().startswith(initial)
        if other is not None:
            assert (configured / 'pkcs11.txt').read_bytes() == other
        if kind == 'missing':
            assert not configured.exists()
        checks['setup_adds_only_to_core_selected_database'] = True
        export_pdf(doc, base / 'before-restart.pdf')
        assert Path(nss.NSSPath) == chosen and nss.IsNSSinitialized
        checks['core_selection_after_pdf_export'] = True
        doc.close(True)
        office.stop()
        office.start(fresh=False)
        doc = office.load('private:factory/swriter')
        export_pdf(doc, base / 'after-restart.pdf')
        assert Path(office.service('com.sun.star.xml.crypto.NSSInitializer').NSSPath) == chosen
        text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
        assert 'Đã đăng ký từ trước:' in text, text
        checks['same_database_and_loaded_module_after_restart'] = True
        doc.close(True)
    finally:
        office.stop()
    print('%s %s: %d checks passed' % (mode, kind, len(checks)), flush=True)
    return dict(mode=mode, configured=kind, checks=checks)


def run_fallback(args, mode):
    base = args.workdir / (mode + '-fallback')
    library = base / 'drivers/usr/lib/libcastle.so.1.0.0'
    library.parent.mkdir(parents=True)
    library.symlink_to('/usr/lib/softhsm/libsofthsm2.so')
    tokens = base / 'tokens'
    tokens.mkdir()
    conf = base / 'softhsm.conf'
    conf.write_text('directories.tokendir = %s\nobjectstore.backend = file\n' % tokens)
    env = dict(SOFTHSM2_CONF=str(conf), HST_USB_TOKEN_TEST_ROOT=str(base / 'drivers'),
               HST_USB_TOKEN_TEST_NO_TOOLS='1' if mode == 'pkcs11' else '0')
    office = hst_gui.Office(args.instdir, str(base / 'office'), args.port, display=args.display, env=env)
    db = base / 'office/home/.pki/nssdb'
    checks = {}
    try:
        install(office, args.oxt)
        doc = office.load('private:factory/swriter')
        export_pdf(doc, base / 'before.pdf')
        assert office.service('com.sun.star.xml.crypto.NSSInitializer').IsNSSinitialized
        text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
        assert 'Đã tìm thấy và đăng ký:' in text and 'Khởi động lại HST Office rồi' in text, text
        assert not (db / 'cert9.db').exists()
        saved = (db / 'pkcs11.txt').read_bytes()
        checks['verified_driver_added_without_live_sql_initialization'] = True
        text = setup_dialog(office, doc.getCurrentController().getFrame(), None)
        assert 'Đã đăng ký từ trước:' in text and saved == (db / 'pkcs11.txt').read_bytes(), text
        checks['idempotent_before_restart'] = True
        doc.close(True)
        office.stop()
        office.start(fresh=False)
        doc = office.load('private:factory/swriter')
        export_pdf(doc, base / 'after.pdf')
        assert Path(office.service('com.sun.star.xml.crypto.NSSInitializer').NSSPath) == db
        assert (db / 'cert9.db').exists() and (db / 'key4.db').exists()
        checks['core_initializes_selected_sql_database_after_restart'] = True
        listing = subprocess.run(['modutil', '-list', '-dbdir', 'sql:' + str(db)], env=dict(os.environ, **env),
                                 capture_output=True, text=True, check=True).stdout
        assert 'HST Feitian ePass2003' in listing and 'Not loaded' not in listing
        checks['independent_nss_loads_added_module'] = True
        doc.close(True)
    finally:
        office.stop()
    print('%s fallback: %d checks passed' % (mode, len(checks)), flush=True)
    return dict(mode=mode, configured='fallback', checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instdir', default='/opt/hst')
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--oxt', type=Path, default=ROOT / 'dist/extensions/hst-vietnamese-tools.oxt')
    parser.add_argument('--display', default=':99')
    parser.add_argument('--port', type=int, default=2183)
    parser.add_argument('--mode', choices=('both', 'modutil', 'pkcs11'), default='both')
    parser.add_argument('--case', choices=('all', 'absolute', 'sql', 'missing', 'tilde', 'fallback'), default='all')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Use an unprivileged account and a private HOME.')
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True)
    hst_gui.setup_uno(args.instdir)
    results = []
    try:
        for mode in (('modutil', 'pkcs11') if args.mode == 'both' else (args.mode,)):
            for kind in (('absolute', 'sql', 'missing', 'tilde', 'fallback') if args.case == 'all' else (args.case,)):
                results.append(run_fallback(args, mode) if kind == 'fallback' else run_case(args, mode, kind))
    finally:
        (args.workdir / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: %d cases, %d checks' % (len(results), sum(len(r['checks']) for r in results)))


if __name__ == '__main__':
    main()
