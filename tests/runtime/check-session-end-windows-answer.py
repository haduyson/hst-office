# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: at log off / shut down the office answers WM_QUERYENDSESSION at once and quits by itself.

Run with the office's Python in the test user's own session (windows-own-session-task.ps1):
  <inst>\\program\\python.exe check-session-end-windows-answer.py --program <inst>\\program --work D:\\hst-test\\...

  saved   a .docx file opened from disk, nothing unsaved. What Windows does at log off: WM_QUERYENDSESSION to
          every top-level window of the office (Windows waits about 5 s for each answer), then WM_ENDSESSION(TRUE).
          The office must answer "yes" within the 5 s and quit by itself soon after; the next start shows neither the
          recovery dialog nor the crash report question, and the file holds the text.
Before hst-session-end-answer-now.patch the answer never came within the 5 s (the quit ran inside the call, 98-115 s):
Windows shows that an application blocks the shut down. No key or mouse input is sent. Exit 1 on a failure.
"""
import argparse
import ctypes
import importlib.util
import os
import re
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recovery_windows as rw  # noqa: E402
from recovery_windows import record, wait  # noqa: E402
from recovery_windows_ui import find_window  # noqa: E402

_spec = importlib.util.spec_from_file_location("session_end_windows", os.path.join(HERE, "check-session-end-windows.py"))
sew = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sew)

WM_QUERYENDSESSION, WM_ENDSESSION, ENDSESSION_LOGOFF = 0x11, 0x16, 0x80000000
RECOVERY = r"Khôi phục tài liệu|Document Recovery"


def send(hwnd, msg, wparam, timeout_ms=5000):
    """(answered within the timeout, the window's answer, seconds) as Windows' SendMessageTimeout sees it."""
    result = ctypes.c_size_t()
    start = time.time()
    done = sew.user32.SendMessageTimeoutW(hwnd, msg, wparam, ENDSESSION_LOGOFF, 0, timeout_ms, ctypes.byref(result))
    return bool(done), result.value, round(time.time() - start, 2)


def log_off(o):
    """WM_QUERYENDSESSION to every top-level window, then WM_ENDSESSION(TRUE); returns the answers to the first."""
    answers = [send(hwnd, WM_QUERYENDSESSION, 0) for hwnd, _t, _w, _h in sew.windows_of(o.bins(), visible=False)]
    ended = time.time()
    for hwnd, _t, _w, _h in sew.windows_of(o.bins(), visible=False):
        send(hwnd, WM_ENDSESSION, 1)
    return answers, ended


def crash_question(o):
    return [w for w in sew.windows_of(o.bins()) if w[1] == "HST Office" and w[2] < 900 and w[3] and w[2] / w[3] > 3.2]


def file_text(path):
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.read("word/document.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""


def docx_from_disk(o, marker):
    """A synthetic .docx written by the office, closed, and opened again from disk (as a user opens a file)."""
    import uno
    from com.sun.star.beans import PropertyValue
    path = os.path.join(o.work, "saved.docx")
    url = uno.systemPathToFileUrl(path)
    doc = o.new("writer", marker)
    o.end_welcome()  # a modal welcome would veto the close
    flt = PropertyValue()
    flt.Name, flt.Value = "FilterName", "MS Word 2007 XML"
    doc.storeToURL(url, (flt,))
    doc.close(True)
    return o.desktop().loadComponentFromURL(url, "_default", 0, ()), path


def saved(o):
    o.start()
    doc, path = docx_from_disk(o, "TRALOI-A")
    record("saved: nothing unsaved before the log off", not doc.isModified())
    time.sleep(3)
    answers, ended = log_off(o)
    first = answers[0] if answers else (False, 0, None)
    print("saved: answers (answered, value, seconds) %r" % answers, flush=True)
    record("saved: WM_QUERYENDSESSION answered 'yes' within 5 s", first[0] and first[1] == 1, answers)
    gone = wait(lambda: not rw.own_pids(o.work), 30, 0.5)
    print("saved: office processes after WM_ENDSESSION: %s" % ("gone after %.1f s" % (time.time() - ended) if gone
                                                                  else "still running"), flush=True)
    record("saved: the office quits by itself within 30 s of WM_ENDSESSION", gone,
           "%.1f s" % (time.time() - ended) if gone else rw.own_pids(o.work))
    o.kill()  # what Windows does with a process still running at the end of the session
    o.start(())
    question = wait(lambda: crash_question(o), 45, 1)
    record("saved: the next start asks no crash report question", not question, question)
    dialog = find_window(RECOVERY, rw.own_pids(o.work))
    record("saved: the next start shows no recovery dialog", not dialog, dialog)
    for hwnd, _t, _w, _h in question or []:
        sew.user32.PostMessageW(hwnd, 0x10, 0, 0)  # WM_CLOSE to our own question
    o.end_welcome(4)
    record("saved: that start quits normally", o.quit())
    record("saved: the file holds the text", "TRALOI-A" in file_text(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--work", required=True)
    args = ap.parse_args()
    if not re.match(r"(?i)^[cd]:\\hst-test\\", args.work):
        raise SystemExit("--work must be under C:\\hst-test or D:\\hst-test")
    sys.path.insert(0, args.program)
    o = sew.Office(args.program, os.path.join(args.work, "saved"), 1)
    try:
        saved(o)
    except Exception as exc:  # noqa: BLE001 - report, then clean up
        record("saved: ran without error", False, repr(exc))
    o.kill()
    print("windows session end answer: %d checks, %d failed" % (len(rw.RESULTS), rw.RESULTS.count(False)))
    return 0 if all(rw.RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
