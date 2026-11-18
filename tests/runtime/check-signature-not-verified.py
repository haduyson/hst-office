#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Digital signatures dialog with a signature that does not verify, in a visible office (Linux X display, gen plugin;
Windows: the test user's own session). Widgets are read by id through the UITest service.

The signer's row must say "(not verified)" / "(chưa xác minh)" next to the name, and the certificate viewer opened
from that row must say that the signature is not valid instead of "This certificate is validated." (it judged the
certificate alone, and did so online). Upstream showed the bare name with only a small icon.
Usage: <office python> check-signature-not-verified.py --soffice PATH --out DIR --doc SIGNED-BAD.odt
(xmlsecurity/qa/unit/signing/data/bad.odt: content changed after signing). Exit 1 on a failure.
"""
import argparse, importlib.util, os, shutil, socket, sys, time  # noqa: E401

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
check, failures, state = base.check, base.failures, base.state

NOT_VERIFIED = ("(not verified)", "(chưa xác minh)")
NOT_VALID_HINT = ("signature is not valid", "chữ ký không hợp lệ")
CERT_VALID_HINT = ("This certificate is validated.", "Chứng chỉ này đã được xác thực.")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--doc", required=True, help="a document whose signature does not verify")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    doc_path = os.path.join(out, os.path.basename(args.doc))
    shutil.copyfile(args.doc, doc_path)  # a copy: the lock file goes next to it
    base.PORT = free_port()  # VisibleOffice reads the module's port
    office = base.VisibleOffice(args.soffice, out, None)
    try:
        doc = office.desktop.loadComponentFromURL(office.uno.systemPathToFileUrl(doc_path), "_blank", 0, ())
        time.sleep(3)
        office.close_welcome()
        office.ui.executeDialog(".uno:Signature")
        dialog = office.wait_dialog("DigitalSignaturesDialog")
        check(dialog is not None, "the digital signatures dialog opens")
        if dialog is None:
            return 1
        rows = dialog.getChild("signatures")
        count = int(state(rows).get("Children", 0))
        check(count >= 1, f"the dialog lists the signature ({count} row(s))")
        row = rows.getChild("0")
        text = str(state(row).get("Text", ""))
        check(any(mark in text for mark in NOT_VERIFIED), f"the signer's row says it is not verified: {text!r}")
        row.executeAction("SELECT", ())
        time.sleep(0.5)
        dialog.getChild("view").executeAction("CLICK", ())
        viewer = office.wait_dialog("ViewCertDialog", timeout=20)
        if viewer is None:  # no certificate in the signature: an information box, nothing that says "valid"
            top = office.ui.getTopFocusWindow()
            check("ok" in top.getChildren(), "without a certificate the dialog shows the no-certificate message")
            top.getChild("ok").executeAction("CLICK", ())
        else:
            hint = str(state(viewer.getChild("hintnotrust")).get("Text", ""))
            check(any(mark in hint.lower() for mark in NOT_VALID_HINT),
                  f"the certificate viewer says the signature is not valid: {hint!r}")
            check(not any(mark == hint for mark in CERT_VALID_HINT), "the viewer does not say the certificate is valid")
            tabs = viewer.getChild("tabcontrol")
            check(int(state(tabs).get("PageCount", 0)) <= 2, "no certification path page for an invalid signature")
            viewer.getChild("ok").executeAction("CLICK", ())
        time.sleep(0.5)
        dialog = office.wait_dialog("DigitalSignaturesDialog", timeout=10)
        if dialog is not None:
            dialog.getChild("close").executeAction("CLICK", ())
        doc.close(True)
    finally:
        office.stop()
    print("RESULT", "FAIL" if failures else "PASS", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
