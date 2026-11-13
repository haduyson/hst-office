#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Saving over an existing file replaces it through a temporary file (hst-save-atomic-replace.patch), Linux and macOS.

Run with the office's own Python (it needs pyuno), headless, no display:
  Linux: <instdir>/program/python tests/runtime/check-save-replace.py --program <instdir>/program
  macOS: "/Applications/HST Office.app/Contents/Resources/python" tests/runtime/check-save-replace.py \\
             --program "/Applications/HST Office.app/Contents/MacOS"

Cases: a plain file (macOS: every save takes the new path; Linux: upstream's rename), a symbolic link to a file in
another folder (both systems). After Save the file holds the new text and is a new inode (replaced, not truncated and
rewritten), the link is still a link to the same file, permissions and an extended attribute survive (macOS: the
Finder info that hides the extension; Linux plain files keep upstream's rename and its attributes), and no
.~hst-save-*.tmp is left. A stale .~hst-save-<dead pid>-0.tmp older than
10 minutes in the folder is removed by the save. Exit 1 when a check fails.
"""
import argparse
import os
import platform
import subprocess
import sys
import tempfile
import time
import zipfile

RESULTS = []
MAC = platform.system() == "Darwin"
XATTR = "com.apple.FinderInfo" if MAC else "user.hst-test"
XVALUE = b"\0" * 8 + b"\x00\x10" + b"\0" * 22 if MAC else b"giu-lai"  # FinderInfo: kIsExtensionHidden 0x0010


def record(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % detail) if not ok else ""), flush=True)


def get_xattr(path):
    try:
        return os.getxattr(path, XATTR) if not MAC else subprocess.run(
            ["xattr", "-px", XATTR, path], capture_output=True, text=True).stdout.replace(" ", "").replace("\n", "")
    except OSError:
        return None


def set_xattr(path):
    try:
        if MAC:
            subprocess.run(["xattr", "-wx", XATTR, XVALUE.hex(), path], check=True)
        else:
            os.setxattr(path, XATTR, XVALUE)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False  # file system without user xattrs: that check is skipped


def connect(port):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(120):
        try:
            return resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(1)
    raise RuntimeError("office not reachable")


def make_docx(desktop, path, text):
    import uno
    from com.sun.star.beans import PropertyValue
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    doc.Text.String = text
    prop = PropertyValue()
    prop.Name, prop.Value = "FilterName", "MS Word 2007 XML"
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop,))
    doc.close(True)


def check_case(desktop, label, open_path, real_path, attr_ok):
    import uno
    folder = os.path.dirname(real_path)
    # the save writes its temporary file next to the path it was opened from (the link's folder)
    stale = os.path.join(os.path.dirname(open_path), ".~hst-save-999999-0.tmp")
    open(stale, "wb").close()
    os.utime(stale, (time.time() - 3600, time.time() - 3600))
    before = os.stat(real_path)
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(open_path), "_blank", 0, ())
    doc.Text.insertString(doc.Text.End, " NOI-DUNG-MOI", False)
    doc.store()
    doc.close(True)
    after = os.stat(real_path)
    with zipfile.ZipFile(real_path) as archive:
        record("%s: the file holds the new text" % label, b"NOI-DUNG-MOI" in archive.read("word/document.xml"))
    if open_path != real_path:
        record("%s: the link stays a link to the same file" % label,
               os.path.islink(open_path) and os.path.realpath(open_path) == os.path.realpath(real_path))
    if MAC or open_path != real_path:
        record("%s: replaced through a new file, not rewritten in place" % label, after.st_ino != before.st_ino)
    record("%s: permissions kept" % label, (after.st_mode & 0o7777) == (before.st_mode & 0o7777),
           oct(after.st_mode))
    if attr_ok and (MAC or open_path != real_path):  # Linux plain files keep upstream's rename (no xattr copy)
        record("%s: extended attribute kept" % label, get_xattr(real_path) not in (None, "", b""))
    left = [n for d in {folder, os.path.dirname(open_path)} for n in os.listdir(d) if n.startswith(".~hst-save-")]
    record("%s: no temporary file left, the stale one removed" % label, not left, left)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True, help="folder with soffice (Linux program/, macOS Contents/MacOS)")
    ap.add_argument("--port", type=int, default=22234)
    args = ap.parse_args()
    work = tempfile.mkdtemp(prefix="hst-save-replace-")
    proc = subprocess.Popen([os.path.join(args.program, "soffice"), "--headless", "--norestore", "--nologo",
                             "-env:UserInstallation=file://" + os.path.join(work, "profile"),
                             "--accept=socket,host=127.0.0.1,port=%d;urp;" % args.port])
    try:
        ctx = connect(args.port)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        for sub in ("plain", "real", "links"):
            os.makedirs(os.path.join(work, sub))
        plain = os.path.join(work, "plain", "van-ban.docx")
        real = os.path.join(work, "real", "that.docx")
        link = os.path.join(work, "links", "lien-ket.docx")
        for path in (plain, real):
            make_docx(desktop, path, "NOI-DUNG-CU")
            os.chmod(path, 0o640)
        os.symlink(real, link)
        check_case(desktop, "plain file", plain, plain, set_xattr(plain))
        check_case(desktop, "symbolic link", link, real, set_xattr(real))
        desktop.terminate()
    finally:
        try:
            proc.wait(60)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("save replace runtime: %d checks, %d failed" % (len(RESULTS), RESULTS.count(False)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
