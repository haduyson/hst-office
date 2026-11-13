# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helper of the recovery runtime checks (check-recovery-kill.py, check-profile-corruption.py,
check-unsaved-documents.py): one HST Office with AutoRecovery on, documents driven over UNO, crashes injected with
signals, the recovery dialogs answered with the pointer and the Return key (their default buttons: "Khôi phục mục đã
chọn" and OK of the emergency save), and the profile inspected on disk.

The X display must already run; soffice runs as the unprivileged build user (hst_gui)."""
import glob
import os
import re
import signal
import subprocess
import time

import hst_gui

RECOVERY_TITLE = r"Khôi phục tài liệu|Document Recovery"
KINDS = {"writer": "private:factory/swriter", "calc": "private:factory/scalc", "impress": "private:factory/simpress"}
RESULTS = []


def record(label, ok, detail=""):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % str(detail)[:300]) if not ok else ""), flush=True)
    return ok


def summary(name):
    failed = [label for label, ok in RESULTS if not ok]
    print("%s: %d checks, %d failed%s" % (name, len(RESULTS), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


def wait(predicate, timeout=30.0, step=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def office(instdir, workdir, port, display, interval_minutes=3):
    """An Office with AutoRecovery (no --norestore); the interval is the HST default unless a check shortens it."""
    config = [("/org.openoffice.Office.Recovery/AutoSave", "TimeIntervall", str(interval_minutes))]
    return hst_gui.Office(instdir, workdir, port, display=display, restore=True, config=config)


def user_dir(off):
    return os.path.join(off.workdir, "profile", "user")


def new_document(off, kind, marker):
    doc = off.desktop().loadComponentFromURL(KINDS[kind], "_default", 0, ())
    append(doc, marker)
    return doc


def append(doc, marker):
    if doc.supportsService("com.sun.star.text.TextDocument"):
        doc.Text.insertString(doc.Text.End, " " + marker, False)
    elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        cell = doc.Sheets.getByIndex(0).getCellByPosition(0, 0)
        cell.String = (cell.String + " " + marker).strip()
    else:
        page = doc.DrawPages.getByIndex(0)
        shape = doc.createInstance("com.sun.star.drawing.TextShape")
        page.add(shape)
        shape.String = marker
    doc.setModified(True)


def text_of(doc):
    if doc.supportsService("com.sun.star.text.TextDocument"):
        return doc.Text.String
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return doc.Sheets.getByIndex(0).getCellByPosition(0, 0).String
    page = doc.DrawPages.getByIndex(0)
    return " ".join(page.getByIndex(i).String for i in range(page.Count) if hasattr(page.getByIndex(i), "String"))


def documents(off):
    out = []
    enum = off.desktop().Components.createEnumeration()
    while enum.hasMoreElements():
        comp = enum.nextElement()
        if hasattr(comp, "getURL") and hasattr(comp, "supportsService"):
            out.append(comp)
    return out


def backups(off):
    """{name: (size, mtime)} of the recovery folder."""
    folder = os.path.join(user_dir(off), "backup")
    return {os.path.basename(p): (os.path.getsize(p), os.path.getmtime(p)) for p in glob.glob(folder + "/*")}


def copies(off):
    return {n: v for n, v in backups(off).items() if re.search(r"_[0-9a-z]+\.od[tspg]$", n) and v[0] > 0}


def recovery_list(off):
    """TempURLs of the RecoveryList entries in registrymodifications.xcu as on disk."""
    try:
        with open(os.path.join(user_dir(off), "registrymodifications.xcu"), encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return None
    items = re.findall(r'<item oor:path="/org.openoffice.Office.Recovery/RecoveryList">.*?</item>', text, re.S)
    return [m.group(1) if m else "" for m in
            (re.search(r'oor:name="TempURL"[^>]*>(?:<value>([^<]*)</value>|<value/>)', item) for item in items)]


def index_entries(off):
    try:
        with open(os.path.join(user_dir(off), "backup", "hst-recovery-index.txt"), encoding="utf-8") as handle:
            return [line.split("\t") for line in handle.read().splitlines()[1:] if line.startswith("entry\t")]
    except OSError:
        return []


def kill(off, sig=signal.SIGKILL):
    pid = off.pid
    if pid:
        os.kill(pid, sig)
    return pid


def gone(off, pid, timeout=60):
    return wait(lambda: off.pid != pid, timeout)


def answer(off, title_re, keys=("Return",), corner=None, timeout=60):
    """Answer the dialog whose title matches: keys (mnemonics of both UI languages, e.g. alt+k then alt+r for
    "Khôi phục mục đã chọn" / "Recover Selected") or a pointer click `corner` = (dx, dy) from its bottom right."""
    found = wait(lambda: [w for w in hst_gui.toplevels(off.display) if re.search(title_re, w[1])], timeout)
    if not found:
        return False
    wid = found[0][0]
    env = dict(os.environ, DISPLAY=off.display)
    xdo = lambda *args: subprocess.run(["xdotool", *args], env=env, check=False, timeout=10)  # noqa: E731
    xdo("windowraise", wid)
    if corner:
        info = subprocess.run(["xwininfo", "-display", off.display, "-id", wid], capture_output=True, text=True).stdout
        width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
        xdo("mousemove", "--window", wid, str(width - corner[0]), str(height - corner[1]), "click", "1")
        return True
    xdo("mousemove", "--window", wid, "40", "10")  # the pointer gives the dialog the keyboard focus
    time.sleep(0.5)
    for key in keys:
        xdo("key", key)
        time.sleep(0.3)
    return True


# Pointer targets from the bottom right of the recovery dialogs (Vietnamese and English labels; Return would only
# toggle the focused list row): "Khôi phục mục đã chọn" / "Recover Selected" (the left of the two buttons),
# "Kết thúc" / "Finish" (the same place after the run) and OK of the emergency save dialog.
RECOVER_AT, FINISH_AT, EMERGENCY_OK = (260, 26), (200, 26), (50, 26)


def restart_and_recover(off, port_wait=180):
    """Start the office on the same profile, accept the recovery dialog, reconnect; False without a dialog."""
    off.start(fresh=False)
    return reconnect_after_recovery(off, port_wait)


def reconnect_after_recovery(off, port_wait=180):
    if not answer(off, RECOVERY_TITLE, corner=RECOVER_AT, timeout=90):
        return False
    time.sleep(8)
    hst_gui.screenshot(os.path.join(off.workdir, "after-recover.png"), off.display)
    # a recovery with failures stops at "Kết thúc"
    if [w for w in hst_gui.toplevels(off.display) if re.search(RECOVERY_TITLE, w[1])]:
        answer(off, RECOVERY_TITLE, corner=FINISH_AT, timeout=5)
    off.ctx = off._connect(port_wait)
    return True


def finish(off):
    """Close every document without saving (no question at quit), then quit normally."""
    try:
        for doc in documents(off):
            doc.setModified(False)
            doc.close(True)
    except Exception:  # noqa: BLE001 - the office may be gone already
        pass
    off.stop()


def tabs_file(off):
    return os.path.exists(os.path.join(user_dir(off), "backup", "hst-document-tabs.txt"))
