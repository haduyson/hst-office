#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS run of HST ▸ Thiết lập USB Token… in a real HST Office.app, signing with SoftHSM2.

macOS counterpart of check-usb-token-setup.py (no platform override: real Darwin, bundled NSS
and Python). SoftHSM2 plays the VNPT-CA driver through HST_USB_TOKEN_TEST_ROOT
(<root>/usr/local/lib/libvnptca_p11_v8.dylib -> libsofthsm2). Scenarios, each with a fresh HOME:
  fresh    no certificate store yet;
  firefox  an existing Firefox profile (internal, Builtin Roots and another module) that must
           stay byte-identical while a new HST store is created and selected after restart.
Each: setup, repeat (existing), restart, the token certificate through XSecurityEnvironment
with the test PIN, an ODT signed through the UI and validated by HST, a final repeat.

  --tools       soffice PATH contains Homebrew modutil/certutil;
  --no-tools    soffice PATH has neither (the normal Mac case; no test simulation flag).
Run with the app's bundled Python (PYTHONPATH: Contents/Resources, pyuno dir, this directory);
the driver's PATH must provide softhsm2-util, pkcs11-tool, certutil, modutil, openssl 3.
`--verify <results.json>` (any Python with lxml and cryptography) adds the independent
XML-DSig verification of the signed ODT files.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import types
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signature_pki  # noqa: E402

LABEL = "VNPT-CA Token Manager"
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TOOLS = ("modutil", "certutil")


def brew_roots():
    """Homebrew's Builtin Roots module (absolute install names, so a copy still loads)."""
    prefix = subprocess.run(["brew", "--prefix", "nss"], capture_output=True, text=True, check=True).stdout.strip()
    return Path(prefix) / "lib/libnssckbi.dylib"


def firefox_profile(home):
    from usb_token_private_harness import snapshot
    root = home / "Library/Application Support/Firefox"
    source = root / "Profiles/hst.default-release"
    source.mkdir(parents=True)
    (root / "profiles.ini").write_text("[Profile0]\nName=default-release\nIsRelative=1\n"
                                       "Path=Profiles/hst.default-release\nDefault=1\n\n[General]\nStartWithLastProfile=1\n")
    roots = brew_roots()
    vendor = home / "another-vendor.dylib"
    shutil.copyfile(roots, vendor)
    subprocess.run(["certutil", "-N", "-d", "sql:" + str(source), "--empty-password"], check=True, capture_output=True)
    for name, library in (("Builtin Roots", roots), ("Another vendor", vendor)):
        subprocess.run(["modutil", "-add", name, "-libfile", str(library), "-dbdir", "sql:" + str(source), "-force"],
                       check=True, capture_output=True)
    return source, snapshot(source)


def addon_urls(office):
    """Every URL of the HST add-on menus as merged into the configuration."""
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                  (PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Addons/AddonUI"),))
    urls = []

    def walk(node):
        for name in node.getElementNames():
            child = node.getByName(name)
            if name == "URL" and isinstance(child, str):
                urls.append(child)
            elif hasattr(child, "getElementNames"):
                walk(child)
    walk(access)
    return urls


def run_case(args, scenario, signing):
    import hst_gui_macos
    from usb_token_harness import certificate_with_pin, setup_dialog
    from usb_token_private_harness import check_private, preserved_records, snapshot
    mode = "tools" if args.tools else "no-tools"
    base = (args.workdir / ("%s-%s" % (scenario, mode))).resolve()
    base.mkdir(parents=True)
    pki = signature_pki.TokenPki(str(base / "pki")).create(register_module=False)
    root = base / "vendors with spaces"
    library = root / "usr/local/lib/libvnptca_p11_v8.dylib"
    library.parent.mkdir(parents=True)
    library.symlink_to(pki.module)
    # A second catalog path to the same file must not register the module twice.
    (library.parent / "libeTPkcs11.dylib").symlink_to(library)
    soffice_path = (os.path.dirname(shutil.which("modutil")) + ":" + SYSTEM_PATH) if args.tools else SYSTEM_PATH
    env = {"SOFTHSM2_CONF": pki.conf, "HST_USB_TOKEN_TEST_ROOT": str(root), "TZ": "Asia/Ho_Chi_Minh", "PATH": soffice_path}
    office = hst_gui_macos.Office(args.app, base / "office", args.port, env=env, oxt=args.oxt,
                                  config=signing.TABS + [("/org.openoffice.Office.Linguistic/General", "UILocale", "en-US")])
    home = office.home
    home.mkdir(parents=True)
    db = home / "Library/Application Support/HST Office/nssdb"
    result = {"scenario": scenario, "mode": mode, "soffice_path": soffice_path, "checks": {}, "ca_pem": pki.ca_pem}
    checks = result["checks"]
    try:
        found = {tool: shutil.which(tool, path=soffice_path) for tool in TOOLS}
        assert all(found.values()) if args.tools else not any(found.values()), found
        checks["nss_tools_on_soffice_path_" + ("present" if args.tools else "absent")] = True
        source = before = None
        if scenario == "firefox":
            source, before = firefox_profile(home)
        print("%s/%s: starting office" % (scenario, mode), flush=True)
        office.start()
        urls = addon_urls(office)
        assert "org.hst.office.vi:SetupUsbToken" in urls, urls
        checks["hst_menu_has_usb_token_command"] = True
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        signing.export_pdf(doc, str(base / "before-setup.pdf"))  # PDF export initializes NSS
        nss = office.service("com.sun.star.xml.crypto.NSSInitializer")
        result["nss_before"] = {"path": nss.NSSPath, "initialized": bool(nss.IsNSSinitialized)}
        if scenario == "firefox":
            assert Path(nss.NSSPath.removeprefix("sql:")) == source, result["nss_before"]
            assert snapshot(source) == before
            checks["core_uses_firefox_profile_before_setup"] = True
        text = setup_dialog(office, frame, signing)
        print("%s/%s: setup dialog checked" % (scenario, mode), flush=True)
        result["first_dialog"] = text
        assert "Đã tìm thấy và đăng ký: " + LABEL in text, text
        assert str(db) in text and "Khởi động lại HST Office rồi" in text, text
        assert "HST Office hiện dùng kho chứng thư riêng" in text, text
        module_file = db / "pkcs11.txt"
        saved = module_file.read_bytes()
        assert saved.count(str(library).encode()) == 1 and b"libeTPkcs11" not in saved, saved
        assert not (db / "cert9.db").exists() and not (db / "key4.db").exists()
        assert db.stat().st_mode & 0o777 == 0o700 and (db / ".hst-office-nssdb").is_file()
        checks["vietnamese_command_created_hst_store_and_registered_module"] = True
        if scenario == "firefox":
            assert snapshot(source) == before
            preserved_records(saved, before["pkcs11.txt"][1])
            checks["old_store_byte_identical_and_records_carried_over"] = True
        result["repeat_dialog"] = text = setup_dialog(office, frame, signing)
        assert "Đã đăng ký từ trước: " + LABEL in text and "Khởi động lại HST Office rồi" in text, text
        assert saved == module_file.read_bytes()
        checks["repeat_before_restart_reports_existing"] = True
        doc.close(True)
        office.stop()
        office.start(fresh=False)
        print("%s/%s: restarted office" % (scenario, mode), flush=True)
        doc = office.load("private:factory/swriter")
        doc.Text.String = "Văn bản kiểm thử thiết lập USB Token — HST Office trên macOS."
        target = base / "signed.odt"
        doc.storeAsURL(target.as_uri(), signing.props(FilterName="writer8", Overwrite=True))
        signing.export_pdf(doc, str(base / "after-setup.pdf"))
        nss = office.service("com.sun.star.xml.crypto.NSSInitializer")
        result["nss_after"] = {"path": nss.NSSPath, "initialized": bool(nss.IsNSSinitialized),
                               "certdir": office.config_value("/org.openoffice.Office.Common/Security/Scripting", "CertDir")}
        assert Path(nss.NSSPath.removeprefix("sql:")) == db, result["nss_after"]
        assert (db / "cert9.db").is_file() and (db / "key4.db").is_file()
        checks["hst_store_selected_after_restart"] = True
        listing = subprocess.run(["modutil", "-list", "-dbdir", "sql:" + str(db)], check=True,
                                 capture_output=True, text=True, env=pki.env).stdout
        result["modutil_list_after_restart"] = listing
        if scenario == "firefox":
            check_private(db, source, before, pki.env, label="HST " + LABEL)
            checks["inherited_roots_and_vendor_loaded_after_restart"] = True
        else:
            assert "HST " + LABEL in listing and "Not loaded" not in listing, listing
            checks["vendor_module_loaded_after_restart"] = True
        subprocess.run(["certutil", "-A", "-d", "sql:" + str(db), "-n", "HST Test Root CA", "-t", "CT,C,C",
                        "-a", "-i", pki.ca_pem], env=pki.env, check=True, capture_output=True)
        subject, prompts = certificate_with_pin(office, signing, base / "shots")
        print("%s/%s: token certificate listed" % (scenario, mode), flush=True)
        result["certificate_subject"] = subject
        assert signature_pki.USER_CN in subject and prompts == 1, (subject, prompts)
        checks["xsecurityenvironment_lists_token_certificate"] = True
        frame = doc.getCurrentController().getFrame()
        dialogs = signing.Dialogs(office, str(base / "shots"), [signature_pki.USER_PIN])
        signed = dialogs.sign_open_document(frame, "usb-setup")
        result["signing"] = signed
        assert signed["signed"], signed
        checks["odt_signed_through_ui_with_pin"] = True
        doc.close(True)
        doc = signing.load_visible(office, target.as_uri())
        time.sleep(3)
        state = signing.signature_state(office, doc.getCurrentController().getFrame())
        assert state == "OK", state
        checks["office_validates_signature"] = True
        with zipfile.ZipFile(target) as archive:
            assert "META-INF/documentsignatures.xml" in archive.namelist()
        result["signed_odt"] = str(target)
        if scenario == "firefox":
            assert snapshot(source) == before
            checks["old_store_unchanged_after_signing"] = True
        result["final_dialog"] = text = setup_dialog(office, doc.getCurrentController().getFrame(), signing)
        assert "Đã đăng ký từ trước: " + LABEL in text and "Khởi động lại HST Office rồi" not in text, text
        checks["rerun_after_restart_reports_existing_without_restart"] = True
        doc.close(True)
        result["passed"] = True
    except Exception as exc:  # noqa: BLE001 - keep the partial evidence of this scenario
        import traceback
        result["error"] = traceback.format_exc()
        print("%s/%s: %r" % (scenario, mode, exc), flush=True)
        try:
            office.screenshot(str(base / "shots/failure.png"))
        except Exception:  # noqa: BLE001 - evidence only
            pass
    finally:
        office.stop()
        # Observation only: whether setup left an empty Linux-style directory behind on macOS.
        result["home_pki_nssdb_exists"] = (home / ".pki/nssdb").exists()
    return result


def verify(results_path):
    import signature_verify
    results = json.loads(Path(results_path).read_text())
    failed = 0
    for row in results:
        if not row.get("signed_odt"):
            continue
        verified = signature_verify.verify_package(row["signed_odt"], row["ca_pem"])
        row["independent_verification"] = verified
        ok = len(verified) == 1 and verified[0]["valid"] and not verified[0]["unchecked"]
        row["checks"]["independent_signature_verification"] = ok
        failed += not ok
        print("%s/%s independent verification: %s" % (row["scenario"], row["mode"], "PASS" if ok else verified))
    Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 1 if failed or not all(r.get("signed_odt") for r in results) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path)
    ap.add_argument("--oxt", type=Path)
    ap.add_argument("--workdir", type=Path)
    ap.add_argument("--port", type=int, default=2093)
    ap.add_argument("--scenario", choices=("both", "fresh", "firefox"), default="both")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--tools", dest="tools", action="store_true")
    group.add_argument("--no-tools", dest="tools", action="store_false")
    ap.add_argument("--verify", type=Path, help="independent verification of an earlier results.json")
    args = ap.parse_args()
    if args.verify:
        return verify(args.verify)
    if not (args.app and args.oxt and args.workdir):
        ap.error("--app, --oxt and --workdir are required")
    if sys.platform != "darwin" or os.geteuid() == 0:
        ap.error("Run on macOS as a normal user.")
    missing = signature_pki.missing_tools()
    if missing:
        print("FAIL: missing test tools: " + ", ".join(missing))
        return 2
    try:
        import signature_verify  # noqa: F401
    except ImportError:  # lxml/cryptography are not in the bundled Python; see --verify
        sys.modules["signature_verify"] = types.ModuleType("signature_verify")
    from usb_token_harness import signing_helpers
    signing = signing_helpers()
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    results, status = [], 0
    for scenario in (("fresh", "firefox") if args.scenario == "both" else (args.scenario,)):
        results.append(run_case(args, scenario, signing))
        passed = results[-1].get("passed", False)
        status |= not passed
        print("%s: %s (%d checks)" % (scenario, "PASS" if passed else "FAIL", len(results[-1]["checks"])), flush=True)
        (args.workdir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print("%s: %d scenarios, %d checks" % ("PASS" if not status else "FAIL", len(results),
                                          sum(len(r["checks"]) for r in results)))
    return status


if __name__ == "__main__":
    sys.exit(main())
