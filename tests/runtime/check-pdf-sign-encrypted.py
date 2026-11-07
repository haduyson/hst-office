#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF signs encrypted PDFs like other signing applications, and keeps their encryption.

On samples of pdf_encrypted_samples.py, each signed in the HST PDF viewer with a USB token
(softhsm), then checked with pyHanko and pdfsig:
  aes128-objstm, aes256, rc4-128, rc4-40  a new signature field, the file stays encrypted
  signed-before                           aes128-objstm signed by pyHanko first: it stays intact
  perm-6, perm-9                          only form filling allowed: the empty field is signed
  perm-none                               refused with the permission message; then the
                                          permissions password "chu" signs it
Every --pdf (read-only copies, e.g. the owner's files) is expected to be refused when its
permissions forbid signing, and to stay byte for byte unchanged.
  check-pdf-sign-encrypted.py --instdir upstream/libreoffice/instdir --workdir /tmp/se --display :71
Needs Xvfb, softhsm2/opensc/libnss3-tools, pikepdf and pyHanko.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

os.environ.setdefault("HST_VCLPLUGIN", "gen")  # UITest drives the PIN, password and message boxes
import hst_gui
import pdf_encrypted_samples
import pdf_signature_fixtures
import pdf_watermark_paths as paths
import signature_pki
from pdf_viewer_uno import info, open_viewer, signing_props
from usb_token_harness import signing_helpers

REFUSED = "không cho phép ký số"
SIGNED_KINDS = ("aes128-objstm", "aes256", "rc4-128", "rc4-40", "signed-before", "perm-6", "perm-9")


def verdicts(pdf, password=b""):
    """pyHanko per signature: (field, intact, valid, whole file); and whether it is encrypted."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    with open(pdf, "rb") as handle:
        reader = PdfFileReader(handle, strict=False)
        encrypted = reader.encrypted
        if encrypted:
            reader.decrypt(password)
        rows = []
        for sig in reader.embedded_signatures:
            status = validate_pdf_signature(sig, ValidationContext(allow_fetching=False))
            rows.append((sig.field_name, status.intact, status.valid,
                         status.coverage is not None and status.coverage.name == "ENTIRE_FILE"))
    return rows, encrypted


def pdfsig_last(pdf):
    out = subprocess.run(["pdfsig", str(pdf)], capture_output=True, text=True).stdout
    lines = [line.strip() for line in out.splitlines() if "Signature Validation:" in line]
    return lines[-1] if lines else ""


def sign_in_viewer(office, dialogs, pdf, target, user_cn, permissions_password=None):
    """Signs pdf into target; answers the PIN, the permission message and the password box."""
    frame, _ = open_viewer(office, pdf)
    office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
    if user_cn not in (info(office, frame).get("Certificate") or ""):
        paths.choose_viewer_certificate(office, dialogs, frame, user_cn)
    import uno
    done, seen = {}, []

    def sign():
        done["result"] = office.dispatch(frame, ".uno:HSTPdfSign", signing_props(
            TargetURL=uno.systemPathToFileUrl(str(target)), Visible=True, Width=200.0, Height=70.0,
            Page=1, X=40.0, Y=40.0)).Result
    thread = threading.Thread(target=sign, daemon=True)
    thread.start()
    deadline = time.time() + 120
    while thread.is_alive() and time.time() < deadline:
        win, kids = dialogs.top()
        if "newpassEntry" in kids:
            dialogs._answer_pin(win)
        elif "pass1ed" in kids and permissions_password and not done.get("typed"):
            done["typed"] = True
            win.getChild("pass1ed").executeAction("TYPE", signing_props(TEXT=permissions_password))
            dialogs.later(win.getChild("ok"))
        elif {"yes", "close"} <= kids and REFUSED in (info(office, frame).get("StatusText") or ""):
            # the permission message: "Nhập mật khẩu quyền" (yes) or close
            seen.append(sorted(kids))
            dialogs.later(win.getChild("yes" if permissions_password else "close"))
        time.sleep(0.7)
    thread.join(5)
    status = info(office, frame).get("StatusText") or ""
    frame.close(True)
    time.sleep(0.5)
    return {"result": done.get("result"), "status": status, "boxes": seen}


def make_inputs(workdir):
    inputs = {}
    for kind in ("aes128-objstm", "aes256", "rc4-128", "rc4-40", "perm-6", "perm-9", "perm-none"):
        inputs[kind] = pdf_encrypted_samples.make(kind, workdir / ("%s.pdf" % kind))
    signer = pdf_signature_fixtures._throwaway_signer(str(workdir))
    inputs["signed-before"] = workdir / "signed-before.pdf"
    pdf_signature_fixtures._sign(signer, inputs["aes128-objstm"], inputs["signed-before"], password=b"")
    return inputs


def check_signed(name, source, target, results):
    before, _ = verdicts(source)
    after, encrypted = verdicts(target)
    new = after[-1] if after else None
    row = {"encrypted": encrypted, "signatures": len(after), "pdfsig": pdfsig_last(target),
           "new": new, "earlier_unchanged": [tuple(r[1:3]) for r in after[:len(before)]] == [tuple(r[1:3]) for r in before]}
    row["ok"] = bool(new and new[1] and new[2] and new[3] and encrypted and row["earlier_unchanged"]
                     and "Signature is Valid" in row["pdfsig"])
    results[name] = row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instdir", default="/opt/hst-office1.0")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--display", default=":97")
    ap.add_argument("--port", type=int, default=2099)
    ap.add_argument("--pdf", action="append", default=[], help="a file whose permissions forbid signing")
    args = ap.parse_args()
    workdir = args.workdir.resolve()
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    hst_gui.setup_uno(args.instdir)
    inputs = make_inputs(workdir)
    for number, pdf in enumerate(args.pdf, 1):
        copy = workdir / ("pdf-%d.pdf" % number)
        shutil.copyfile(pdf, copy)
        os.chmod(copy, 0o444)
        inputs["pdf-%d" % number] = copy
    pki = signature_pki.TokenPki(str(workdir / "pki")).create()
    config = [("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false"),
              ("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb)]
    env = {"TZ": "Asia/Ho_Chi_Minh", "SOFTHSM2_CONF": pki.conf,
           "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-hst-test-bus"}
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(workdir)], check=True)
    signing = signing_helpers()
    office = hst_gui.Office(args.instdir, str(workdir / "office"), args.port, display=args.display,
                            config=config, env=env)
    stop = signing.start_office(office)
    results = {}
    try:
        dialogs = signing.Dialogs(office, str(workdir / "shots"), [signature_pki.USER_PIN] * 8)
        for name, pdf in inputs.items():
            target = workdir / ("%s-hst.pdf" % name)
            refused_expected = name == "perm-none" or name.startswith("pdf-")
            digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
            try:
                run = sign_in_viewer(office, dialogs, pdf, target, signature_pki.USER_CN)
                if not refused_expected:
                    check_signed(name, pdf, target, results)
                    results[name]["viewer"] = run
                    continue
                unchanged = hashlib.sha256(Path(pdf).read_bytes()).hexdigest() == digest
                results[name] = {"refused": REFUSED in run["status"] and not target.exists(),
                                 "unchanged": unchanged, "viewer": run}
                results[name]["ok"] = results[name]["refused"] and unchanged
                if name == "perm-none":
                    unlocked = workdir / "perm-none-unlocked.pdf"
                    run = sign_in_viewer(office, dialogs, pdf, unlocked, signature_pki.USER_CN, "chu")
                    check_signed("perm-none-password", pdf, unlocked, results)
                    results["perm-none-password"]["viewer"] = run
            except Exception as error:  # noqa: BLE001 - one file failing must not hide the others
                results[name] = {"ok": False, "error": repr(error)[:300]}
    finally:
        stop.set()
        office.stop()
        (workdir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str) + "\n")
    failures = [name for name, row in results.items() if not row.get("ok")]
    for name, row in results.items():
        print("%-20s %s" % (name, json.dumps({k: v for k, v in row.items() if k != "viewer"}, ensure_ascii=False, default=str)))
    print("FAIL: " + ", ".join(failures) if failures else "OK: encrypted PDFs are signed and refused as specified")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
