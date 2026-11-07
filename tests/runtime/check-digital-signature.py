#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Digital signatures with a USB token (PKCS#11) end to end, on a virtual SoftHSM2 token.

Signs ODT, DOCX, ODS, XLSX, ODP, PPTX and an existing PDF through the real dialogs
(Tệp tin → Chữ ký số → Ký tài liệu… → chọn chứng chỉ → nhập mã PIN), exports a signed PDF
(PDF export filter, optional time-stamp server), then verifies every file inside HST Office
(signature state and DocumentDigitalSignatures) and independently (signature_verify: XML-DSig
with lxml/cryptography, pdfsig, pyHanko). A second, fresh instance cancels the PIN prompt and
must leave the document unsigned without crashing. Throw-away keys live in --workdir only.

Needs: softhsm2, opensc (pkcs11-tool), libnss3-tools, openssl, poppler-utils, pyHanko, python3-lxml,
python3-cryptography, ImageMagick `import`, x11-utils, an X display (Xvfb). UITest drives the dialogs (gen plugin).

  check-digital-signature.py --instdir /opt/hst-office1.0 --workdir /tmp/sig [--display :93]
                             [--tsa http://timestamp.digicert.com]
Exit 0 only when every format is signed and verifies; 2 (BLOCKED) when a tool above is missing. --allow-skip: 77
for a missing token tool, and a PDF is then not checked by pyHanko when it is absent.
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HST_VCLPLUGIN", "gen")  # UITest reaches VCL dialogs only
import hst_gui  # noqa: E402
import signature_pki  # noqa: E402
import signature_verify  # noqa: E402,F401 - other checks reach it through this module
# Names other checks load from this module (check-pdf-viewer.py, usb_token_harness.py) stay importable here.
from signature_dialogs import Dialogs, props, start_office  # noqa: E402,F401
from signature_documents import (FORMATS, close_document, export_pdf, export_signed_pdf, hst_verify,  # noqa: E402,F401
                                 load_visible, make_documents, signature_state, tamper, token_certificate)
from signature_verdict import external_checks, verdict  # noqa: E402

# One window per document keeps the dialog flow independent of the document-tab feature;
# --tabs runs with the shipped default (tabs on).
TABS = [("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")]
# A PDF opened in a window goes to the HST PDF viewer, which has its own signing (check-pdf-viewer.py); this
# check signs an existing PDF through Draw's File ▸ Digital Signatures, the path the option below selects.
DRAW_PDF = [("/org.openoffice.Office.HSTPdfViewer/Viewer", "OpenPdfInViewer", "false")]


def run_signing(args, pki, results):
    work = os.path.join(args.workdir, "run-sign")
    docs = os.path.join(args.workdir, "docs")
    shutil.rmtree(docs, ignore_errors=True)
    os.makedirs(docs)
    subprocess_chown(args.workdir)  # soffice runs as the unprivileged user: token, NSS DB, documents
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb)] + TABS + DRAW_PDF,
                            env={"SOFTHSM2_CONF": pki.conf, "TZ": "Asia/Ho_Chi_Minh"})
    import uno
    welcome = start_office(office)
    try:
        # An unsigned PDF export before signing (the default) used to hide every token
        # certificate for the rest of the session; keep it as the regression check.
        paths = make_documents(office, docs, early_pdf=not args.late_pdf)
        dialogs = Dialogs(office, os.path.join(args.workdir, "shots"), pins=["000000", signature_pki.USER_PIN])
        for ext in [f[0] for f in FORMATS] + ["pdf"]:
            row = results.setdefault(ext, {})
            if ext == "pdf" and not os.path.exists(paths["pdf"]):
                source = office.load(uno.systemPathToFileUrl(paths["odt"]), hidden=True)
                export_pdf(source, paths["pdf"])
                close_document(source)
            doc = load_visible(office, uno.systemPathToFileUrl(paths[ext]))
            if doc is None:
                dialogs.shot(ext + "-not-loaded")
                row["gui"] = {"signed": False, "error": "document did not load"}
                continue
            frame = doc.getCurrentController().getFrame()
            time.sleep(2)
            try:
                row["gui"] = dialogs.sign_open_document(frame, ext)
            except Exception as error:  # noqa: BLE001 - reported per format
                row["gui"] = {"signed": False, "error": repr(error)}
                print("%s: %r" % (ext, error), flush=True)
            time.sleep(3)  # let the post-signing reload/idle work finish, as a user would
            close_document(doc)
            row["file"] = paths[ext]
        results["pin_prompts_signing_run"] = dialogs.prompts
        certificate = token_certificate(office)
        results["token_certificate"] = certificate.SubjectName if certificate else None
        for tag, tsa in (("pdf-export", None), ("pdf-export-tsa", args.tsa)):
            if tag.endswith("tsa") and not tsa:
                continue
            row = results.setdefault(tag, {})
            try:
                row["file"] = export_signed_pdf(office, paths["odt"], os.path.join(docs, tag + ".pdf"), certificate, tsa)
            except Exception as error:  # noqa: BLE001
                row["error"] = repr(error)
        paths["tampered"] = tamper(paths["odt"], os.path.join(docs, "tampered.odt"))
        results.setdefault("tampered-odt", {})["file"] = paths["tampered"]
        for tag, row in results.items():
            # PDFs through the API; packages through what the user sees (signature_state below)
            if isinstance(row, dict) and str(row.get("file", "")).endswith(".pdf") and os.path.exists(row["file"]):
                row["hst"] = hst_verify(office, row["file"])
        for ext in [f[0] for f in FORMATS] + ["pdf", "tampered"]:
            doc = load_visible(office, uno.systemPathToFileUrl(paths[ext]))
            key = "tampered-odt" if ext == "tampered" else ext
            if doc is None:
                results[key]["status_bar"] = "document did not load"
                continue
            time.sleep(3)
            results[key]["status_bar"] = signature_state(office, doc.getCurrentController().getFrame())
            dialogs.shot("opened-" + ext)
            doc.close(True)
    finally:
        welcome.set()
        office.stop()


def run_cancel(args, pki, results):
    """Fresh instance, the user cancels the PIN prompt: no signature, no crash."""
    work = os.path.join(args.workdir, "run-cancel")
    target = os.path.join(args.workdir, "docs", "cancel.odt")
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb)] + TABS,
                            env={"SOFTHSM2_CONF": pki.conf, "TZ": "Asia/Ho_Chi_Minh"})
    import uno
    welcome = start_office(office)
    row = results.setdefault("cancel-pin", {})
    try:
        doc = office.load("private:factory/swriter", hidden=True)
        doc.getText().setString("Hủy nhập mã PIN")
        doc.storeToURL(uno.systemPathToFileUrl(target), props(FilterName="writer8", Overwrite=True))
        doc.close(True)
        subprocess_chown(os.path.dirname(target))
        doc = office.load(uno.systemPathToFileUrl(target))
        time.sleep(2)
        dialogs = Dialogs(office, os.path.join(args.workdir, "shots-cancel"), pins=[])
        try:
            row["gui"] = dialogs.sign_open_document(doc.getCurrentController().getFrame(), "cancel", accept_errors=True)
        except Exception as error:  # noqa: BLE001
            row["gui"] = {"error": repr(error)}
        row["prompts"], row["messages"] = dialogs.prompts, dialogs.unexpected
        doc.close(True)
        row["office_alive"] = office.pid is not None
        with zipfile.ZipFile(target) as package:
            row["file_has_signature"] = "META-INF/documentsignatures.xml" in package.namelist()
    finally:
        welcome.set()
        office.stop()


def subprocess_chown(path):
    if os.geteuid() == 0:
        import subprocess
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--display", default=":93")
    ap.add_argument("--port", type=int, default=2093)
    ap.add_argument("--tsa", help="time-stamp server URL for an extra signed PDF export")
    ap.add_argument("--late-pdf", action="store_true", help="export the unsigned PDF only after the other formats")
    ap.add_argument("--tabs", action="store_true", help="keep document tabs on (shipped default)")
    ap.add_argument("--allow-skip", action="store_true",
                    help="missing token tools skip (exit 77), a missing pyHanko is no failure; default: BLOCKED (exit 2)")
    args = ap.parse_args()
    if args.tabs:
        TABS.clear()
    missing = signature_pki.missing_tools() + ([] if args.allow_skip else signature_verify.missing_verifiers())
    if missing:
        print(("SKIP: missing " if args.allow_skip else "BLOCKED: missing (or pass --allow-skip) ") + ", ".join(missing))
        return 77 if args.allow_skip else 2
    os.makedirs(args.workdir, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    pki = signature_pki.TokenPki(os.path.join(args.workdir, "pki")).create()
    modules, certs = pki.describe()
    results = {"nss_modules": modules, "nss_certificates": certs}
    run_signing(args, pki, results)
    run_cancel(args, pki, results)
    external_checks(pki, results, allow_missing=args.allow_skip)
    failures = verdict(results)
    with open(os.path.join(args.workdir, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1, default=str)
    for tag, row in results.items():
        if isinstance(row, dict) and "verdict" in row:
            print("%-15s %s  hst=%s  external=%s" % (tag, row["verdict"], [(s["valid"], s["certificate_status"]) for s in row.get("hst", [])],
                                                     row.get("external_valid")))
    print("tampered-odt    hst=%s status_bar=%s external=%s" % (results.get("tampered-odt", {}).get("hst"),
                                                                results.get("tampered-odt", {}).get("status_bar"),
                                                                results.get("tampered-odt", {}).get("external_valid")))
    print("PIN prompts:", results.get("pin_prompts_signing_run"))
    print("cancel:", {k: v for k, v in results.get("cancel-pin", {}).items() if k != "gui"})
    print("FAIL: " + ", ".join(failures) if failures else "OK: all formats signed with the token and verified")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
