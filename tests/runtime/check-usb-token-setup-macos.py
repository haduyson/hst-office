#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS USB Token setup/signing probe; see --help for scenarios and requirements."""
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signature_pki
from usb_token_macos_cli import main
from usb_token_macos_harness import addon_urls, changed, firefox_profile, setup_dialog

LABEL = "VNPT-CA Token Manager"
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TOOLS = ("modutil", "certutil")


def bounded_setup(office, frame, signing):
    with office.step("setup-command", 150):
        return setup_dialog(office, frame, signing)


def run_case(args, scenario, signing, tag=None):
    import hst_gui_macos
    from usb_token_harness import certificate_with_pin
    from usb_token_private_harness import preserved_records, snapshot
    mode = "tools" if args.tools else "no-tools"
    signing.Dialogs.log = []
    base = (args.workdir / ("%s-%s" % (tag or scenario, mode))).resolve()
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
    result = {"scenario": tag or scenario, "mode": mode, "soffice_path": soffice_path, "checks": {}, "ca_pem": pki.ca_pem}
    checks = result["checks"]
    source = before = None
    try:
        found = {tool: shutil.which(tool, path=soffice_path) for tool in TOOLS}
        assert all(found.values()) if args.tools else not any(found.values()), found
        checks["nss_tools_on_soffice_path_" + ("present" if args.tools else "absent")] = True
        if scenario.startswith("firefox"):
            source, before = firefox_profile(home, args.app)
        print("%s/%s: starting office" % (scenario, mode), flush=True)
        with office.step("start", 300):
            office.start()
        urls = addon_urls(office)
        assert "org.hst.office.vi:SetupUsbToken" in urls, urls
        checks["hst_menu_has_usb_token_command"] = True
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        if scenario != "firefox":  # PDF export initializes NSS; "firefox" runs setup with NSS still cold
            signing.export_pdf(doc, str(base / "before-setup.pdf"))
        nss = office.service("com.sun.star.xml.crypto.NSSInitializer")
        result["nss_before"] = {"path": nss.NSSPath, "initialized": bool(nss.IsNSSinitialized)}
        if source:
            assert Path(nss.NSSPath.removeprefix("sql:")) == source, result["nss_before"]
            checks["core_uses_firefox_profile_before_setup"] = True
            assert scenario != "firefox" or snapshot(source) == before
            # Core's own NSS session on the browser store (before any setup) may touch it; record that,
            # then require that setup, restart and signing leave the store exactly as core left it.
            result["firefox_files_changed_by_core_before_setup"] = changed(source, before)
            before = snapshot(source)
        text = bounded_setup(office, frame, signing)
        print("%s/%s: setup dialog checked" % (scenario, mode), flush=True)
        result["first_dialog"] = text
        assert "Đã tìm thấy và đăng ký: " + LABEL in text, text
        assert str(db) in text and "Khởi động lại HST Office rồi" in text, text
        assert "HST Office hiện dùng kho chứng thư riêng" in text, text
        assert ("Kho cũ được giữ nguyên" in text) == bool(source), text
        checks["old_store_message_matches_existing_store"] = True
        module_file = db / "pkcs11.txt"
        saved = module_file.read_bytes()
        assert saved.count(str(library).encode()) == 1 and b"libeTPkcs11" not in saved, saved
        assert not (db / "cert9.db").exists() and not (db / "key4.db").exists()
        assert db.stat().st_mode & 0o777 == 0o700 and (db / ".hst-office-nssdb").is_file()
        checks["vietnamese_command_created_hst_store_and_registered_module"] = True
        if source:
            assert snapshot(source) == before
            preserved_records(saved, before["pkcs11.txt"][1])
            checks["old_store_byte_identical_and_records_carried_over"] = True
        result["repeat_dialog"] = text = bounded_setup(office, frame, signing)
        assert "Đã đăng ký từ trước: " + LABEL in text and "Khởi động lại HST Office rồi" in text, text
        assert saved == module_file.read_bytes()
        checks["repeat_before_restart_reports_existing"] = True
        doc.close(True)
        office.stop()
        with office.step("restart", 300):
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
        result["hst_store_pkcs11_before_restart"] = saved.decode("utf-8", "replace")
        result["hst_store_pkcs11_after_restart"] = module_file.read_text(encoding="utf-8", errors="replace")
        if source:
            # Core's NSS owns the selected store after restart and may rewrite its module file, so check
            # what it loads (as check_private does) rather than the bytes the setup wrote.
            assert snapshot(source) == before, changed(source, before)
            assert db.stat().st_mode & 0o777 == 0o700 and (db / ".hst-office-nssdb").is_file()
            # Setup carried every record over (checked before restart). LibreOffice core's own NSS start
            # then drops a "Builtin Roots" record from whatever store it opens and supplies its bundled
            # roots itself (also seen on the Firefox store in firefox-warm), so that one is only recorded.
            result["builtin_roots_record_after_core_start"] = "Builtin Roots" in listing
            for name in ("NSS Internal PKCS #11 Module", "Another vendor", "HST " + LABEL):
                assert name in listing, listing
            assert "Not loaded" not in listing, listing
            checks["inherited_vendor_module_loaded_after_restart"] = True
        else:
            assert "HST " + LABEL in listing and "Not loaded" not in listing, listing
            checks["vendor_module_loaded_after_restart"] = True
        subprocess.run(["certutil", "-A", "-d", "sql:" + str(db), "-n", "HST Test Root CA", "-t", "CT,C,C",
                        "-a", "-i", pki.ca_pem], env=pki.env, check=True, capture_output=True)
        for attempt in (1, 2):
            # The PIN and signing dialogs are driven through UITest. On Aqua, its nested executeAction
            # wrappers occasionally stall the main loop (stack samples show only UITest/VCL frames), so
            # one bounded retry in a restarted office is allowed and reported; product checks are unchanged.
            try:
                if attempt > 1:
                    office.stop()
                    with office.step("restart-for-retry", 300):
                        office.start(fresh=False)
                        doc = signing.load_visible(office, target.as_uri())
                with office.step("certificate-with-pin-%d" % attempt, 180):
                    subject, prompts = certificate_with_pin(office, signing, base / "shots")
                print("%s/%s: token certificate listed" % (tag or scenario, mode), flush=True)
                result["certificate_subject"] = subject
                assert signature_pki.USER_CN in subject and prompts == 1, (subject, prompts)
                checks["xsecurityenvironment_lists_token_certificate"] = True
                frame = doc.getCurrentController().getFrame()
                dialogs = signing.Dialogs(office, str(base / "shots"), [signature_pki.USER_PIN])
                with office.step("sign-odt-%d" % attempt, 360):
                    signed = dialogs.sign_open_document(frame, "usb-setup-%d" % attempt)
                result["signing"] = signed
                assert signed["signed"], signed
                checks["odt_signed_through_ui_with_pin"] = True
                break
            except Exception as exc:  # noqa: BLE001 - retried once, then reported
                office.diagnose("ui-attempt-%d" % attempt)
                result.setdefault("ui_retries", []).append(repr(exc)[:400])
                print("%s/%s: UI attempt %d failed: %r" % (tag or scenario, mode, attempt, exc), flush=True)
                if attempt == 2:
                    raise
        doc.close(True)
        with office.step("reload-signed-odt", 180):
            doc = signing.load_visible(office, target.as_uri())
            time.sleep(3)
            state = signing.signature_state(office, doc.getCurrentController().getFrame())
        assert state == "OK", state
        checks["office_validates_signature"] = True
        with zipfile.ZipFile(target) as archive:
            assert "META-INF/documentsignatures.xml" in archive.namelist()
        result["signed_odt"] = str(target)
        if source:
            assert snapshot(source) == before
            checks["old_store_unchanged_after_signing"] = True
        result["final_dialog"] = text = bounded_setup(office, doc.getCurrentController().getFrame(), signing)
        assert "Đã đăng ký từ trước: " + LABEL in text and "Khởi động lại HST Office rồi" not in text, text
        checks["rerun_after_restart_reports_existing_without_restart"] = True
        doc.close(True)
        if scenario == "fresh":
            assert not (home / ".pki/nssdb").exists()
            checks["no_unused_linux_store_after_fresh_setup"] = True
        result["passed"] = True
        result["pin_prompts"] = list(signing.Dialogs.log)
    except Exception as exc:  # noqa: BLE001 - keep the partial evidence of this scenario
        import traceback
        result["error"] = traceback.format_exc()
        result["pin_prompts"] = list(signing.Dialogs.log)
        if source:
            result["firefox_files_changed"] = changed(source, before)
        result["soffice_exit"] = office.crashed()
        office.diagnose("failure")
        print("%s/%s: %r (soffice exit %s)" % (tag or scenario, mode, exc, result["soffice_exit"]), flush=True)
        try:
            office.screenshot(str(base / "shots/failure.png"))
        except Exception:  # noqa: BLE001 - evidence only
            pass
    finally:
        office.stop()
        result["home_pki_nssdb_exists"] = (home / ".pki/nssdb").exists()
    return result



if __name__ == "__main__":
    code = main(run_case)
    sys.stdout.flush()
    sys.stderr.flush()
    # Daemon threads may still sit in UNO calls; a normal interpreter shutdown can then abort while
    # flushing stdout (seen as a LibreOfficePython crash report). Exit without finalization.
    os._exit(code)
