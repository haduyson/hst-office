#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Digital signatures with a USB token (PKCS#11) end to end, on a virtual SoftHSM2 token.

Signs ODT, DOCX, ODS, XLSX, ODP, PPTX and an existing PDF through the real dialogs
(Tập tin → Chữ ký số → Ký tài liệu… → chọn chứng chỉ → nhập mã PIN), exports a signed PDF
(PDF export filter, optional time-stamp server), then verifies every file inside HST Office
(signature state and DocumentDigitalSignatures) and independently (signature_verify: XML-DSig
with lxml/cryptography, pdfsig, pyHanko). A second, fresh instance cancels the PIN prompt and
must leave the document unsigned without crashing. Throw-away keys live in --workdir only.

Needs: softhsm2, opensc (pkcs11-tool), libnss3-tools, openssl, poppler-utils, python3-lxml,
python3-cryptography, ImageMagick `import`, x11-utils, an X display (Xvfb). The UITest service
drives the dialogs, so soffice runs with the gen VCL plugin.

  check-digital-signature.py --instdir /opt/hst-office1.0 --workdir /tmp/sig [--display :93]
                             [--tsa http://timestamp.digicert.com]
Exit status 0 only when every format is signed and verifies.
"""
import argparse
import json
import os
import shutil
import sys
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HST_VCLPLUGIN", "gen")  # UITest reaches VCL dialogs only
import hst_gui  # noqa: E402
import signature_pki  # noqa: E402
import signature_verify  # noqa: E402

FORMATS = (("odt", "swriter", "writer8"), ("docx", "swriter", "MS Word 2007 XML"),
           ("ods", "scalc", "calc8"), ("xlsx", "scalc", "Calc MS Excel 2007 XML"),
           ("odp", "simpress", "impress8"), ("pptx", "simpress", "Impress MS PowerPoint 2007 XML"))
SIGNATURE_STATE = {0: "NOSIGNATURES", 1: "OK", 2: "BROKEN", 3: "INVALID", 4: "NOTVALIDATED", 5: "PARTIAL_OK"}
CANCEL = object()
# One window per document keeps the dialog flow independent of the document-tab feature;
# --tabs runs with the shipped default (tabs on).
TABS = [("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")]


def props(**values):
    import uno
    from com.sun.star.beans import PropertyValue
    out = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name = name
        prop.Value = uno.Any("[]com.sun.star.beans.PropertyValue", value) if name == "FilterData" else value
        out.append(prop)
    return tuple(out)


class Dialogs:
    """UITest-driven dialog steps; answers token PIN prompts from a queue on the way."""

    def __init__(self, office, shots, pins):
        self.office, self.shots, self.pins = office, shots, list(pins)
        self.ui = office.service("org.libreoffice.uitest.UITest")
        self.prompts, self.unexpected = [], []

    def top(self):
        try:
            win = self.ui.getTopFocusWindow()
            return win, set(win.getChildren())
        except Exception:  # noqa: BLE001 - no focus window between dialogs
            return None, set()

    def shot(self, name):
        try:
            return self.office.screenshot(os.path.join(self.shots, name + ".png"))
        except Exception:  # noqa: BLE001 - evidence only
            return None

    @staticmethod
    def later(obj, action="CLICK", args=()):
        """Run a UI action in its own thread: buttons that open modal dialogs block the call."""
        thread = threading.Thread(target=obj.executeAction, args=(action, args), daemon=True)
        thread.start()
        return thread

    def _answer_pin(self, win):
        label = ""
        try:
            label = {p.Name: p.Value for p in win.getChild("openPasswordLabel").getState()}.get("Text", "")
        except Exception:  # noqa: BLE001
            pass
        answer = self.pins.pop(0) if self.pins else CANCEL
        self.prompts.append({"label": label, "answer": "cancel" if answer is CANCEL else "pin(%d digits)" % len(answer)})
        self.shot("pin-prompt-%d" % len(self.prompts))
        if answer is CANCEL:
            self.later(win.getChild("cancel"))
        else:
            win.getChild("newpassEntry").executeAction("TYPE", props(TEXT=answer))
            self.later(win.getChild("ok"))
        time.sleep(1.5)

    def wait(self, wanted, timeout=60, gone=False, accept_errors=False):
        """Wait until the top dialog has all ids in `wanted` (or, gone=True, until it has none)."""
        deadline = time.time() + timeout
        stale_since = None
        while time.time() < deadline:
            win, kids = self.top()
            if "newpassEntry" in kids:
                self._answer_pin(win)
                continue
            if (not gone and wanted <= kids) or (gone and not (wanted & kids)):
                return win
            # message boxes (wrong PIN, signing error): record, confirm, carry on
            if kids and "ok" in kids and not (kids & {"signatures", "searchbox", "newpassEntry"}):
                stale_since = stale_since or time.time()
                if time.time() - stale_since > 2:  # an error/info message box: record and confirm
                    self.unexpected.append(sorted(kids))
                    self.shot("message-%d" % len(self.unexpected))
                    self.later(win.getChild("ok"))
                    stale_since = None
                    time.sleep(1.5)
            time.sleep(0.5)
        self.shot("timeout")
        raise TimeoutError("dialog %s %s not reached; top has %s" % ("without" if gone else "with", sorted(wanted), sorted(self.top()[1])))

    def certificate_rows(self, accept_errors, timeout=40):
        """The certificate chooser lists token certificates only after the token login (PIN)."""
        deadline = time.time() + timeout
        while True:
            chooser = self.wait({"searchbox", "signatures", "ok"}, accept_errors=accept_errors)
            tree = chooser.getChild("signatures")
            rows = [(cid, {p.Name: p.Value for p in tree.getChild(cid).getState()}.get("Text", "")) for cid in tree.getChildren()]
            if rows or time.time() > deadline:
                return chooser, rows
            time.sleep(1)

    def sign_open_document(self, frame, tag, accept_errors=False):
        """Tập tin → Chữ ký số… → Ký tài liệu… → certificate → Ký → Đóng, on the loaded document."""
        threading.Thread(target=self.office.dispatch, args=(frame, ".uno:Signature"), daemon=True).start()
        dialog = self.wait({"signatures", "sign", "close"}, accept_errors=accept_errors)
        self.later(dialog.getChild("sign"))
        chooser, rows = self.certificate_rows(accept_errors)
        self.shot(tag + "-1-chooser")
        match = [cid for cid, text in rows if signature_pki.USER_CN in text]
        if not match:
            self.later(chooser.getChild("cancel"))
            self.wait({"searchbox"}, gone=True, accept_errors=accept_errors)
            dialog, _ = self.top()
            self.later(dialog.getChild("close"))
            self.wait({"sign", "close"}, gone=True, accept_errors=accept_errors)
            return {"chooser_rows": [t for _c, t in rows], "signed": False}
        chooser.getChild("signatures").getChild(match[0]).executeAction("SELECT", ())
        self.later(chooser.getChild("ok"))
        dialog = self.wait({"signatures", "sign", "close"}, timeout=90, accept_errors=accept_errors)
        time.sleep(1)
        entries = list(dialog.getChild("signatures").getChildren())
        self.shot(tag + "-2-signed-dialog")
        self.later(dialog.getChild("close"))
        self.wait({"sign", "close"}, gone=True, accept_errors=accept_errors)
        # "Bạn có muốn ghi nhớ chữ ký đó cho mỗi lần lưu không?" follows a new signature: Không
        remember = False
        for _ in range(10):
            win, kids = self.top()
            if {"yes", "no"} <= kids:
                remember = True
                self.later(win.getChild("no"))
                time.sleep(1.5)
                break
            time.sleep(0.5)
        return {"chooser_rows": [t for _c, t in rows], "signed": bool(entries), "dialog_entries": len(entries),
                "remember_question": remember}


def dismiss_welcome(office, stop):
    """Close the HST welcome dialog if it shows; under the gen plugin its title is COMPOUND_TEXT,
    which hst_gui.toplevels() cannot read, so match the raw WM_NAME instead."""
    import re
    import subprocess
    while not stop.wait(1.0):
        pid = office.pid
        if pid is None:
            continue
        tree = subprocess.run(["xwininfo", "-display", office.display, "-root", "-children"], capture_output=True, text=True).stdout
        for wid in re.findall(r"^\s*(0x[0-9a-f]+) ", tree, re.M):
            prop = subprocess.run(["xprop", "-display", office.display, "-id", wid, "WM_NAME", "_NET_WM_PID"],
                                  capture_output=True, text=True).stdout
            if ("= %d" % pid) in prop and re.search(r"Ch\\340o m|Chào mừng|Welcome to", prop):
                office.click_close(wid)


def start_office(office):
    office.start()
    stop = threading.Event()
    threading.Thread(target=dismiss_welcome, args=(office, stop), daemon=True).start()
    return stop


def load_visible(office, url):
    """loadComponentFromURL can return None right after a signed document was closed (the
    document still opens, e.g. as a tab): find it among the desktop components then."""
    doc = office.load(url)
    deadline = time.time() + 30
    while doc is None and time.time() < deadline:
        time.sleep(1)
        components = office.desktop().getComponents().createEnumeration()
        while components.hasMoreElements():
            candidate = components.nextElement()
            if getattr(candidate, "URL", None) == url or (hasattr(candidate, "getURL") and candidate.getURL() == url):
                doc = candidate
    return doc


def close_document(doc):
    """Close a document; a dialog left open by a failed step vetoes close(True) (reported)."""
    try:
        doc.close(True)
    except Exception as error:  # noqa: BLE001 - a dialog still open vetoes; never dispose under it
        print("close vetoed: %r" % error, flush=True)


def signature_state(office, frame):
    """What the status bar shows: SID_SIGNATURE state of the frame (SignatureState)."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL

    class Listener(unohelper.Base, XStatusListener):
        state = None

        def statusChanged(self, event):
            Listener.state = event.State

        def disposing(self, _event):
            pass

    url = URL()
    url.Complete = ".uno:Signature"
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    listener = Listener()
    dispatch.addStatusListener(listener, url)
    time.sleep(1)
    dispatch.removeStatusListener(listener, url)
    return SIGNATURE_STATE.get(Listener.state, Listener.state)


def hst_verify(office, path):
    """DocumentDigitalSignatures.verifyDocumentContentSignatures of a PDF, as HST shows it."""
    import uno
    dds = office.smgr.createInstanceWithArgumentsAndContext("com.sun.star.security.DocumentDigitalSignatures", ("1.2",), office.ctx)
    stream = office.service("com.sun.star.ucb.SimpleFileAccess").openFileRead(uno.systemPathToFileUrl(path))
    infos = dds.verifyDocumentContentSignatures(None, stream)
    return [{"signer": i.Signer.SubjectName if i.Signer else None, "valid": bool(i.SignatureIsValid),
             "certificate_status": i.CertificateStatus} for i in infos]


def make_documents(office, outdir, early_pdf=True):
    import uno
    paths = {}
    for ext, factory, filt in FORMATS:
        doc = office.load("private:factory/" + factory, hidden=True)
        if factory == "swriter":
            doc.getText().setString("Văn bản kiểm thử ký số bằng USB Token — HST Office.")
        elif factory == "scalc":
            sheet = doc.Sheets.getByIndex(0)
            sheet.getCellByPosition(0, 0).setString("Bảng tính ký số")
            sheet.getCellByPosition(1, 0).setValue(30)
        else:
            page = doc.DrawPages.getByIndex(0)
            shape = doc.createInstance("com.sun.star.drawing.TextShape")
            page.add(shape)
            shape.setString("Trình chiếu ký số")
        paths[ext] = os.path.join(outdir, "test." + ext)
        doc.storeToURL(uno.systemPathToFileUrl(paths[ext]), props(FilterName=filt, Overwrite=True))
        if ext == "odt":
            paths["pdf"] = os.path.join(outdir, "existing.pdf")
            if early_pdf:
                export_pdf(doc, paths["pdf"])
        doc.close(True)
    return paths


def export_pdf(doc, target):
    import uno
    doc.storeToURL(uno.systemPathToFileUrl(target), props(FilterName="writer_pdf_Export", Overwrite=True))


def export_signed_pdf(office, odt, target, certificate, tsa=None):
    import uno
    doc = office.load(uno.systemPathToFileUrl(odt), hidden=True)
    data = props(SignPDF=True, SignatureCertificate=certificate, SignatureReason="Kiểm thử ký số",
                 SignatureLocation="Đà Nẵng", SignatureContactInfo="lienhe@hasontech.vn", **({"SignatureTSA": tsa} if tsa else {}))
    try:
        doc.storeToURL(uno.systemPathToFileUrl(target), props(FilterName="writer_pdf_Export", FilterData=data, Overwrite=True))
    finally:
        doc.close(True)
    return target


def token_certificate(office):
    context = office.service("com.sun.star.xml.crypto.SEInitializer").createSecurityContext("")
    for cert in context.getSecurityEnvironment().getPersonalCertificates():
        if signature_pki.USER_CN in cert.SubjectName:
            return cert
    return None


def tamper(path, target):
    """Copy of a signed ODF file whose content.xml changed after signing."""
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(target, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "content.xml":
                data = data.replace("kiểm thử".encode(), "ĐÃ SỬA".encode(), 1)
            dst.writestr(item, data)
    return target


def run_signing(args, pki, results):
    work = os.path.join(args.workdir, "run-sign")
    docs = os.path.join(args.workdir, "docs")
    shutil.rmtree(docs, ignore_errors=True)
    os.makedirs(docs)
    subprocess_chown(args.workdir)  # soffice runs as the unprivileged user: token, NSS DB, documents
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb)] + TABS,
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
            time.sleep(3)
            key = "tampered-odt" if ext == "tampered" else ext
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


def external_checks(pki, results):
    for tag, row in results.items():
        if not isinstance(row, dict) or not row.get("file") or not os.path.exists(row["file"]):
            continue
        if row["file"].endswith(".pdf"):
            row["external"] = signature_verify.verify_pdf(row["file"], pki.nssdb, pki.ca_pem)
            row["external_valid"] = bool(row["external"]["pdfsig_valid"]) and row["external"]["pyhanko_valid"] is not False
        else:
            row["external"] = signature_verify.verify_package(row["file"], pki.ca_pem)
            row["external_valid"] = bool(row["external"]) and all(s["valid"] for s in row["external"])


def verdict(results):
    failures = []
    for tag in [f[0] for f in FORMATS] + ["pdf", "pdf-export"] + (["pdf-export-tsa"] if "pdf-export-tsa" in results else []):
        row = results.get(tag, {})
        api_ok = bool(row.get("hst")) and all(s["valid"] and s["certificate_status"] == 0 for s in row["hst"])
        # OOXML: docProps/core.xml, docProps/app.xml and [Content_Types].xml stay unsigned by
        # convention, so HST reports the signature as valid but partial (PARTIAL_OK)
        accepted = ("OK", "PARTIAL_OK") if tag in ("docx", "xlsx", "pptx") else ("OK",)
        hst_ok = row.get("status_bar") in accepted if "status_bar" in row else api_ok
        row["verdict"] = "PASS" if hst_ok and row.get("external_valid") else "FAIL"
        if row["verdict"] != "PASS":
            failures.append(tag)
    tampered = results.get("tampered-odt", {})
    if tampered.get("external_valid") or any(s["valid"] for s in tampered.get("hst", [])) or tampered.get("status_bar") == "OK":
        failures.append("tampered-odt (accepted)")
    prompts = results.get("pin_prompts_signing_run", [])
    if len(prompts) < 2:
        failures.append("wrong PIN was not re-prompted")
    cancel = results.get("cancel-pin", {})
    if cancel.get("file_has_signature") or not cancel.get("office_alive") or not cancel.get("prompts"):
        failures.append("cancel-pin")
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--display", default=":93")
    ap.add_argument("--port", type=int, default=2093)
    ap.add_argument("--tsa", help="time-stamp server URL for an extra signed PDF export")
    ap.add_argument("--late-pdf", action="store_true", help="export the unsigned PDF only after the other formats")
    ap.add_argument("--tabs", action="store_true", help="keep document tabs on (shipped default)")
    args = ap.parse_args()
    if args.tabs:
        TABS.clear()
    missing = signature_pki.missing_tools()
    if missing:
        print("SKIP: missing " + ", ".join(missing))
        return 77
    os.makedirs(args.workdir, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    pki = signature_pki.TokenPki(os.path.join(args.workdir, "pki")).create()
    modules, certs = pki.describe()
    results = {"nss_modules": modules, "nss_certificates": certs}
    run_signing(args, pki, results)
    run_cancel(args, pki, results)
    external_checks(pki, results)
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
