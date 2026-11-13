# SPDX-License-Identifier: AGPL-3.0-only
"""Recovery after taskkill /F on Windows (power cuts cannot be simulated there; NTFS power loss stays untested).

Run with the office's Python in the interactive session of the test user (the recovery dialog needs a desktop):
  <inst>\\program\\python.exe check-recovery-kill-windows.py --program <inst>\\program --work D:\\hst-test\\recovery

Every scenario uses its own profile under --work (never the user's %APPDATA% profile) and synthetic documents:
  first    a new document killed 40 s after its first change: its first recovery copy (30 s) is offered, with the text;
  after    taskkill right after a later copy replaced the previous one (interval 1 minute): the configuration and the
           recovery index on disk name an existing copy, the recovery brings the latest text;
  bigsave  taskkill in the middle of saving a ~20 MB .docx (lon.docx next to this script: text and a noise picture): the file is the old or the new version (valid zip), the next
           save in that folder removes the dead process's .~hst-save-*.tmp once it is 10 minutes old (checked by
           name pattern and owner pid);
  tabs     five documents (Writer, Sheets, Slides) in tabs, taskkill: all five are offered and recovered.
Prints PASS/FAIL lines and a summary; exit 1 when a check fails.
"""
import argparse
import glob
import os
import re
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recovery_windows import RESULTS, Office, append, kill_profile, record, wait  # noqa: E402

def scenario(office, name, body):
    print("== " + name, flush=True)
    try:
        body(office)
    except Exception as exc:  # noqa: BLE001 - one broken scenario must not hide the others
        record("%s: ran without error" % name, False, repr(exc))
    office.kill()


def first(o):
    o.start(); o.configure(); o.new("writer", "MOT-CHUA-LUU")
    record("first: a copy within 45 s", wait(o.copies, 45, 1))
    o.kill()
    record("first: recovery dialog", o.recover())
    texts = wait(lambda: [t for t in o.texts() if t.strip()], 60) or []
    record("first: text recovered", any("MOT-CHUA-LUU" in t for t in texts), texts)


def after(o):
    o.start(); o.configure()
    doc = o.new("writer", "HAI-BAN-DAU")
    old = set(wait(o.copies, 45, 0.5) or {})
    append(doc, "HAI-BAN-SAU")
    record("after: a newer copy", wait(lambda: set(o.copies()) - old, 200, 0.02))
    o.kill()
    xcu = open(os.path.join(o.user, "registrymodifications.xcu"), encoding="utf-8").read()
    named = re.findall(r'oor:name="TempURL"[^>]*><value>[^<]*/([^/<]+)</value>', xcu)
    present = {os.path.basename(p) for p in glob.glob(os.path.join(o.user, "backup", "*"))}
    record("after: configuration names an existing copy", named and all(n in present for n in named), named)
    record("after: recovery index present", os.path.exists(os.path.join(o.user, "backup", "hst-recovery-index.txt")))
    record("after: recovery dialog", o.recover())
    texts = wait(lambda: [t for t in o.texts() if t.strip()], 60) or []
    record("after: latest text recovered", any("HAI-BAN-SAU" in t for t in texts), texts)


def bigsave(o):
    import uno
    o.start()
    folder = os.path.join(o.work, "docs")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "lon.docx")
    import shutil
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lon.docx"), path)  # ~19 MB fixture
    doc = o.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_default", 0, ())
    append(doc, "LON-MOI")
    import threading
    threading.Timer(2.0, kill_profile, (o.work,)).start()
    try:
        doc.store()
    except Exception:  # noqa: BLE001 - the bridge dies with the office
        pass
    time.sleep(5)
    with zipfile.ZipFile(path) as archive:
        record("bigsave: the file is a valid zip after the kill", archive.testzip() is None)
    left = glob.glob(os.path.join(folder, ".~hst-save-*.tmp"))
    print("bigsave: temporary files left by the killed save:", [os.path.basename(p) for p in left])
    record("bigsave: no upstream-style lu*.tmp next to the file", not glob.glob(os.path.join(folder, "lu*.tmp")))


def tabs(o):
    o.start(); o.configure()
    for i, kind in enumerate(("writer", "writer", "calc", "calc", "impress")):
        o.new(kind, "THE-%d" % i)
    record("tabs: five copies", wait(lambda: len(o.copies()) >= 5, 90, 1), o.copies())
    o.kill()
    record("tabs: recovery dialog", o.recover())
    texts = wait(lambda: o.texts() if len([t for t in o.texts() if t.strip()]) >= 5 else None, 90) or o.texts()
    record("tabs: all five recovered", all(any("THE-%d" % i in t for t in texts) for i in range(5)), texts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--only", help="run one scenario: first, after, bigsave or tabs")
    args = ap.parse_args()
    if not re.match(r"(?i)^[cd]:\\hst-test\\", args.work):
        raise SystemExit("--work must be under C:\\hst-test or D:\\hst-test")
    sys.path.insert(0, args.program)
    for name, body, minutes in (("first", first, 3), ("after", after, 1), ("bigsave", bigsave, 3), ("tabs", tabs, 1)):
        if args.only and name != args.only:
            continue
        scenario(Office(args.program, os.path.join(args.work, name), minutes), name, body)
    print("windows recovery kill: %d checks, %d failed" % (len(RESULTS), RESULTS.count(False)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
