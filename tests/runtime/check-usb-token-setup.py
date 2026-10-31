#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Run the real HST USB Token command and sign ODT with SoftHSM2 in both NSS modes.

Run as a non-root user, on Xvfb, with python3-uno, softhsm2, opensc, libnss3-tools,
openssl, python3-lxml, python3-cryptography and the built .oxt. The install is read-only.
The no-tools run disables BOTH modutil and certutil inside the extension, as on macOS.
Test-only search root: HST_USB_TOKEN_TEST_ROOT; NSS CLI simulation: HST_USB_TOKEN_TEST_NO_TOOLS.
Example: check-usb-token-setup.py --instdir /opt/hst --workdir /tmp/usb-setup --display :99
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

os.environ.setdefault("HST_VCLPLUGIN", "gen")
import hst_gui
import signature_pki
from usb_token_harness import certificate_with_pin, install, setup_dialog, signing_helpers

ROOT = Path(__file__).resolve().parents[2]


def run_mode(args, mode, signing):
    import uno
    base = args.workdir / mode
    base.mkdir(parents=True)
    pki = signature_pki.TokenPki(str(base / "pki")).create(register_module=False)
    root = base / "vendors with spaces"
    library = root / 'usr/lib/libcastle.so.1.0.0'
    library.parent.mkdir(parents=True)
    library.symlink_to(pki.module)
    # Another detected path to the same inode must not register the module twice.
    (library.parent / "libeTPkcs11.so").symlink_to(library)
    extra = {"SOFTHSM2_CONF": pki.conf, "HST_USB_TOKEN_TEST_ROOT": str(root), "TZ": "Asia/Ho_Chi_Minh"}
    if mode == "pkcs11":
        extra["HST_USB_TOKEN_TEST_NO_TOOLS"] = "1"
    office = hst_gui.Office(args.instdir, str(base / "office"), args.port, display=args.display,
                            config=signing.TABS + [("/org.openoffice.Office.Linguistic/General", "UILocale", "en-US")], env=extra)
    db = Path(office.workdir) / "home/.pki/nssdb"
    result = {"backend": mode, "checks": {}}
    checks = result["checks"]
    try:
        print(mode + ": starting office", flush=True)
        install(office, args.oxt)
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        # Exercise both cached NSS (PDF before setup) and first-use initialization.
        if not args.cold:
            signing.export_pdf(doc, str(base / "before-setup.pdf"))
        nss = office.service("com.sun.star.xml.crypto.NSSInitializer")
        assert nss.IsNSSinitialized == (not args.cold)
        checks["nss_initial_state_verified"] = True
        text = setup_dialog(office, frame, signing)
        print(mode + ": setup dialog checked", flush=True)
        result["first_dialog"] = text
        assert "Đã tìm thấy và đăng ký: Feitian ePass2003" in text, text
        assert str(db) in text and "Khởi động lại HST Office rồi" in text, text
        module_file = db / "pkcs11.txt"
        saved = module_file.read_bytes()
        assert str(library).encode() in saved, saved
        checks["vietnamese_command_registered_module"] = True
        text = setup_dialog(office, frame, signing)
        assert "Đã đăng ký từ trước" in text and "Khởi động lại HST Office rồi" in text, text
        assert saved == module_file.read_bytes()
        checks["repeat_command_idempotent"] = True
        if mode == "pkcs11":
            assert not (db / "cert9.db").exists(), "Setup must leave live SQL initialization to core on restart"
            checks["no_nss_tools_needed"] = True
        doc.close(True)
        office.stop()
        office.start(fresh=False)
        print(mode + ": restarted office", flush=True)
        # Core creates the no-tools SQL DB with empty internal password on first use.
        doc = office.load("private:factory/swriter")
        doc.Text.String = "Văn bản kiểm thử thiết lập USB Token — HST Office."
        target = base / "signed.odt"
        doc.storeAsURL(target.as_uri(), signing.props(FilterName="writer8", Overwrite=True))
        signing.export_pdf(doc, str(base / "after-setup.pdf"))
        assert (db / "cert9.db").is_file() and (db / "key4.db").is_file()
        assert Path(office.service("com.sun.star.xml.crypto.NSSInitializer").NSSPath) == db
        checks["core_uses_selected_sql_db_after_restart"] = True
        subprocess.run(["certutil", "-A", "-d", "sql:" + str(db), "-n", "HST Test Root CA", "-t", "CT,C,C",
                        "-a", "-i", pki.ca_pem], env=pki.env, check=True, capture_output=True)
        subject, prompts = certificate_with_pin(office, signing, base / "shots")
        print(mode + ": token certificate listed", flush=True)
        result["certificate_subject"] = subject
        assert signature_pki.USER_CN in subject and prompts == 1
        checks["xsecurityenvironment_lists_token_certificate"] = True
        frame = doc.getCurrentController().getFrame()
        dialogs = signing.Dialogs(office, str(base / "shots"), [signature_pki.USER_PIN])
        signed = dialogs.sign_open_document(frame, "usb-setup")
        assert signed["signed"], signed
        checks["odt_signed_through_ui"] = True
        doc.close(True)
        doc = signing.load_visible(office, target.as_uri())
        state = signing.signature_state(office, doc.getCurrentController().getFrame())
        assert state == "OK", state
        checks["office_validates_signature"] = True
        with zipfile.ZipFile(target) as archive:
            assert "META-INF/documentsignatures.xml" in archive.namelist()
        verified = signing.signature_verify.verify_package(str(target), pki.ca_pem)
        result["independent_verification"] = verified
        assert len(verified) == 1 and verified[0]["valid"] and not verified[0]["unchecked"], verified
        checks["independent_signature_verification"] = True
        text = setup_dialog(office, doc.getCurrentController().getFrame(), signing)
        assert "Đã đăng ký từ trước" in text and "Khởi động lại HST Office rồi" not in text, text
        checks["command_still_works_after_reload"] = True
        doc.close(True)
    finally:
        office.stop()
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instdir", default="/opt/hst")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--oxt", type=Path, default=ROOT / "dist/extensions/hst-vietnamese-tools.oxt")
    ap.add_argument("--display", default=":99")
    ap.add_argument("--port", type=int, default=2083)
    ap.add_argument("--mode", choices=("both", "modutil", "pkcs11"), default="both")
    ap.add_argument("--cold", action="store_true", help="also exercise setup before NSS has initialized")
    args = ap.parse_args()
    if os.geteuid() == 0:
        ap.error("Run this test as a non-root user with its own HOME.")
    missing = signature_pki.missing_tools()
    if missing:
        print("SKIP: " + ", ".join(missing))
        return 77
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    signing = signing_helpers()
    results = []
    try:
        for mode in (("modutil", "pkcs11") if args.mode == "both" else (args.mode,)):
            results.append(run_mode(args, mode, signing))
            print(mode + ": PASS (%d checks)" % len(results[-1]["checks"]), flush=True)
    finally:
        (args.workdir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print("PASS: %d modes, %d checks" % (len(results), sum(len(r["checks"]) for r in results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
