#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST explains why a PDF signature is invalid, keeps the signer, and never changes the verdict.

pdf_signature_fixtures signs a sample PDF with a throw-away key (pyHanko) and changes copies the
way real files get broken. For each file, HST Office is asked twice:
  - DocumentDigitalSignatures.verifyDocumentContentSignatures: the verdict and the signer;
  - HST PDF (.uno:HSTPdfInfo): SignatureProblems, the status bar text and the signature panel.
Expected: valid files stay valid (self-signed: "certificate not validated"); every invalid one
names its signer and gives its reason (rewritten, modified, content, broken).

With --owner-pdf, a read-only copy of a real file that a document system rewrote after signing is
checked too: every signature is invalid, rewritten, with its signer. The file itself is never
changed and never copied outside --workdir.

Needs an X display (Xvfb), python3-cryptography and pyHanko. Example:
  check-pdf-signature-reasons.py --instdir upstream/libreoffice/instdir --workdir /tmp/sigr --display :71
Exit status 0 only when every file has the expected verdict, signer and reason; 77 without pyHanko.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import hst_gui
import pdf_samples
import pdf_signature_fixtures
from pdf_viewer_uno import VIEWER

INVALID_STATUS = "Chữ ký số không hợp lệ"
UNTRUSTED_STATUS = "Đã ký, chưa xác thực được chứng thư số"
ASK = "Hãy xin tệp gốc từ người gửi để kiểm tra."
SHORT_REASON = {"rewritten": "nội dung tệp đã thay đổi sau khi ký. " + ASK,
                "incomplete": "tệp ngắn hơn phần dữ liệu đã ký", "modified": "tệp đã được sửa thêm sau khi ký",
                "content": "nội dung không khớp với chữ ký", "broken": "dữ liệu chữ ký bị hỏng"}
WHY = {"rewritten": "Nội dung tệp đã thay đổi sau khi ký. " + ASK, "incomplete": "ví dụ do tải về chưa hết",
       "modified": "theo cách mà chữ ký không cho phép", "content": "Nội dung tệp không còn khớp với chữ ký",
       "broken": "Dữ liệu chữ ký bị hỏng hoặc không đọc được"}
UNVERIFIED_SIGNER = "Ký bởi (chưa xác minh): "
UNVERIFIED_TIME = "Thời điểm ký (chưa xác minh): "
CERTIFICATE_VALID = 0  # css.security.CertificateValidity.VALID
INFO_KEYS = ("SignatureCount", "ValidSignatures", "UntrustedSignatures", "InvalidSignatures", "SignatureStatus",
             "SignatureLines", "SignatureProblems", "SignatureDetails", "SignaturesChecked")


def api_verify(office, path):
    """The verdict and signer of every signature, as the document signature service reports them."""
    import uno
    dds = office.smgr.createInstanceWithArgumentsAndContext(
        "com.sun.star.security.DocumentDigitalSignatures", ("1.2",), office.ctx)
    stream = office.service("com.sun.star.ucb.SimpleFileAccess").openFileRead(uno.systemPathToFileUrl(path))
    return [{"signer": i.Signer.SubjectName if i.Signer else None, "valid": bool(i.SignatureIsValid),
             "certificate_status": i.CertificateStatus}
            for i in dds.verifyDocumentContentSignatures(None, stream)]


def viewer_signatures(office, path, timeout=60):
    """Open a PDF in HST PDF and return what it shows about the signatures."""
    import uno
    component = office.load(uno.systemPathToFileUrl(path))
    assert component is not None and component.ImplementationName == VIEWER, component
    frame = component.getFrame()
    deadline, data = time.time() + timeout, {}
    while time.time() < deadline:
        data = {i.Name: i.Value for i in office.dispatch(frame, ".uno:HSTPdfInfo").Result}
        if data.get("SignaturesChecked"):
            break
        time.sleep(0.2)
    frame.close(True)
    time.sleep(0.5)
    return {k: list(data[k]) if isinstance(data.get(k), tuple) else data.get(k) for k in INFO_KEYS}


def expectations_failed(api, viewer, valid, problem, signer):
    """The verdict is unchanged, and the reason and signer are shown: the failed expectations.
    signer: the expected common name, or None when the CMS is not read (damaged, or ranges longer
    than the file)."""
    failed = []
    if not api or any(s["valid"] != valid for s in api):
        failed.append("verdict %s" % [s["valid"] for s in api])
    if signer is not None and any(not s["signer"] or signer not in s["signer"] for s in api):
        failed.append("signer %s" % [s["signer"] for s in api])
    if viewer["SignatureCount"] != len(api) or viewer["SignatureProblems"] != [problem] * len(api):
        failed.append("problems %s" % viewer["SignatureProblems"])
    if valid:
        if viewer["SignatureStatus"] != UNTRUSTED_STATUS or viewer["InvalidSignatures"]:
            failed.append("status %r" % viewer["SignatureStatus"])
        return failed
    if viewer["SignatureStatus"] != "%s: %s" % (INVALID_STATUS, SHORT_REASON[problem]):
        failed.append("status %r" % viewer["SignatureStatus"])
    if WHY[problem] not in (viewer["SignatureDetails"] or ""):
        failed.append("details %r" % viewer["SignatureDetails"])
    lines = viewer["SignatureLines"] or []
    if len(lines) != len(api) or any(WHY[problem] not in line for line in lines):
        failed.append("panel lines %r" % lines)
    if signer and any(UNVERIFIED_SIGNER + signer not in line or UNVERIFIED_TIME not in line for line in lines):
        failed.append("signer not labelled as unverified in the panel %r" % lines)
    if any(s["certificate_status"] == CERTIFICATE_VALID for s in api):
        failed.append("certificate of an invalid signature checked as valid")
    return failed


def make_cases(args, fixtures):
    """{name: (path, valid, problem, signer CN or None when no signer can be read)}."""
    source = pdf_samples.make(args.instdir, os.path.join(fixtures, "nguon.pdf"), 2)
    cases = {}
    for name, path in pdf_signature_fixtures.make_signature_fixtures(source, fixtures).items():
        valid, problem = pdf_signature_fixtures.SIGNATURE_FIXTURES[name]
        # a damaged CMS names no signer; ranges longer than the file are never hashed
        unread = name in ("broken-cms", "range-past-eof")
        cases[name] = (path, valid, problem, None if unread else pdf_signature_fixtures.SIGNER_CN)
    if args.owner_pdf:
        copy = os.path.join(fixtures, "owner-copy.pdf")
        shutil.copyfile(args.owner_pdf, copy)
        os.chmod(copy, 0o444)
        cases["owner-copy"] = (copy, False, "rewritten", None)
    return cases


def run(args):
    fixtures = os.path.join(args.workdir, "fixtures")
    shutil.rmtree(fixtures, ignore_errors=True)
    os.makedirs(fixtures)
    cases = make_cases(args, fixtures)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.workdir], check=True)
    office = hst_gui.Office(args.instdir, os.path.join(args.workdir, "office"), args.port, display=args.display,
                            config=[("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")],
                            env={"TZ": "Asia/Ho_Chi_Minh"})
    results = {}
    office.start()
    try:
        for name, (path, valid, problem, signer) in cases.items():
            row = results[name] = {"file": path, "expected": {"valid": valid, "problem": problem}}
            row["api"] = api_verify(office, path)
            row["viewer"] = viewer_signatures(office, path)
            row["failed"] = expectations_failed(row["api"], row["viewer"], valid, problem, signer)
            row["named_signers"] = sum(1 for s in row["api"] if s["signer"])
            row["verdict"] = "FAIL" if row["failed"] else "PASS"
    finally:
        office.stop()
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instdir", default="/opt/hst-office1.0")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--display", default=":97")
    ap.add_argument("--port", type=int, default=2095)
    ap.add_argument("--owner-pdf", help="also check a read-only copy of this signed PDF (rewritten after signing)")
    args = ap.parse_args()
    try:
        import pyhanko  # noqa: F401
    except ImportError:
        print("SKIP: pyHanko is not installed")
        return 77
    args.workdir = os.path.abspath(args.workdir)
    os.makedirs(args.workdir, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    results = run(args)
    with open(os.path.join(args.workdir, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1, default=str)
    for name, row in results.items():
        print("%-20s %s  problems=%s  named=%d  status=%r  %s" % (
            name, row["verdict"], row["viewer"]["SignatureProblems"], row["named_signers"],
            row["viewer"]["SignatureStatus"], "; ".join(row["failed"])))
    failures = [name for name, row in results.items() if row["verdict"] == "FAIL"]
    print("FAIL: " + ", ".join(failures) if failures else "OK: every PDF signature has its verdict, signer and reason")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
