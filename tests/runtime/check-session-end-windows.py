# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: a session the system ended (log off, shut down, restart) is not a crash.

Run with the office's Python in the test user's own session (windows-own-session-task.ps1):
  <inst>\\program\\python.exe check-session-end-windows.py --program <inst>\\program --work D:\\hst-test\\session-end

  logoff  a new document changed after its first recovery copy; what Windows does at log off: WM_QUERYENDSESSION to
          every top-level window of the office (its save question holds it past the 5 s Windows waits), then
          WM_ENDSESSION(TRUE), then the process is ended ("Đóng bắt buộc"). The next start asks no crash report
          question and its log says "session end"; a later normal start still offers the recovery copy.
  kill    the same ended with taskkill /F only: the question is still asked ("not closed").
The first start after the end uses --norestore (the recovery dialog would wait for input that a disconnected session
cannot give); the recovery state is left as it was and the next normal start shows the dialog. Exit 1 on a failure.
"""
import argparse
import ctypes
import os
import re
import subprocess
import sys
import threading
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recovery_windows as rw  # noqa: E402
from recovery_windows import record, wait  # noqa: E402
from recovery_windows_ui import find_window  # noqa: E402

user32 = ctypes.windll.user32
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
                                       wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_size_t


def windows_of(pids, visible=True):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and (user32.IsWindowVisible(hwnd) or not visible):
            title, rect = ctypes.create_unicode_buffer(512), wintypes.RECT()
            user32.GetWindowTextW(hwnd, title, 512)
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append((hwnd, title.value, rect.right - rect.left, rect.bottom - rect.top))
        return True
    user32.EnumWindows(visit, 0)
    return found


def log_off(pids):
    """WM_QUERYENDSESSION (5 s each, as Windows waits) then WM_ENDSESSION(TRUE) to every top-level window."""
    result = ctypes.c_size_t()
    for msg, wparam in ((0x11, 0), (0x16, 1)):
        for hwnd, _title, _w, _h in windows_of(pids, visible=False):
            user32.SendMessageTimeoutW(hwnd, msg, wparam, 0x80000000, 0, 5000, ctypes.byref(result))


class Office(rw.Office):
    def start(self, args=("--nodefault",)):
        import uno
        self.seed()
        url = uno.systemPathToFileUrl(os.path.join(self.work, "profile"))
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + url,
                                      "--nologo", "--accept=socket,host=127.0.0.1,port=%d;urp;" % rw.PORT, *args])
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        self.ctx = wait(lambda: self._try(resolver), 180, 1)
        return self.ctx

    def end_welcome(self, settle=15):
        """Some fresh profiles still show the modal welcome after the first window: end it over UNO, never keys."""
        toolkit = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        quiet_since = time.time()
        while time.time() - quiet_since < settle:
            for index in range(toolkit.getTopWindowCount()):
                window = toolkit.getTopWindow(index)
                if hasattr(window, "endExecute") and re.search("chào|Welcome", window.getTitle() or ""):
                    window.endExecute()
                    quiet_since = time.time()
            time.sleep(1)

    def bins(self):
        return {pid for pid in rw.own_pids(self.work)}

    def quit(self):
        desktop = self.desktop()
        for doc in self.texts_docs():
            doc.setModified(False)
        desktop.setPropertyValue("SuspendQuickstartVeto", True)
        threading.Thread(target=lambda: _quiet(desktop.terminate), daemon=True).start()
        return wait(lambda: not rw.own_pids(self.work), 40, 1)

    def texts_docs(self):
        out, enum = [], self.desktop().Components.createEnumeration()
        while enum.hasMoreElements():
            comp = enum.nextElement()
            if hasattr(comp, "setModified"):
                out.append(comp)
        return out


def _quiet(fn):
    try:
        fn()
    except Exception:  # noqa: BLE001 - the bridge goes away with the office
        pass


def log_lines(o):
    try:
        with open(os.path.join(o.user, "hst-office", "hst-office.log"), encoding="utf-8") as handle:
            return [line for line in handle.read().splitlines() if "previous session ended" in line]
    except OSError:
        return []


def scenario(o, name, how, expect_question):
    o.start()
    doc = o.new("writer", "PHIEN-A")
    o.end_welcome()
    record("%s: a recovery copy within 60 s" % name, wait(o.copies, 60, 1))
    rw.append(doc, "PHIEN-B")
    time.sleep(2)
    if how == "logoff":
        log_off(o.bins())
        record("%s: the save question holds the log off (office still running)" % name, rw.own_pids(o.work))
    o.kill()
    before = len(log_lines(o))
    o.start(("--norestore",))
    question = wait(lambda: [w for w in windows_of(o.bins()) if w[1] == "HST Office" and w[2] < 900 and w[3] < 400],
                    45, 1)
    record("%s: crash report question %s" % (name, "asked" if expect_question else "not asked"),
           bool(question) == expect_question, question)
    want = "previous session ended: %s" % ("not closed" if expect_question else "session end")
    lines = log_lines(o)[before:]
    record("%s: the log says '%s'" % (name, want), any(want in line for line in lines), lines)
    for hwnd, _t, _w, _h in question or []:
        user32.PostMessageW(hwnd, 0x10, 0, 0)  # WM_CLOSE to our own question: "Không"
    o.end_welcome(4)
    record("%s: that start quits normally" % name, o.quit())
    o.kill()
    o.start(())
    found = wait(lambda: find_window(r"Khôi phục tài liệu|Document Recovery", rw.own_pids(o.work)), 60)
    record("%s: a normal start offers the recovery copy" % name, found)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--work", required=True)
    args = ap.parse_args()
    if not re.match(r"(?i)^[cd]:\\hst-test\\", args.work):
        raise SystemExit("--work must be under C:\\hst-test or D:\\hst-test")
    sys.path.insert(0, args.program)
    for name, how, expect in (("logoff", "logoff", False), ("kill", "kill", True)):
        o = Office(args.program, os.path.join(args.work, name), 1)
        try:
            scenario(o, name, how, expect)
        except Exception as exc:  # noqa: BLE001 - one broken scenario must not hide the other
            record("%s: ran without error" % name, False, repr(exc))
        o.kill()
    print("windows session end: %d checks, %d failed" % (len(rw.RESULTS), rw.RESULTS.count(False)))
    return 0 if all(rw.RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
