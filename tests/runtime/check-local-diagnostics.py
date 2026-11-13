# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of HST's local diagnostics on Linux (soffice runs as hstbuild, never root).

Usage: python3 tests/runtime/check-local-diagnostics.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/local-diagnostics] [--display :75]

Uses a hard-linked instdir copy with the test package (error_report_gui.prepare_instdir) and the local fake server:
  1. a Python exception in an HST component (the dispatcher's test-package hook, HST_DIAG_TEST_RAISE) lands in
     <profile>/user/hst-office/hst-office.log with its traceback, filtered; the session start entry is there too;
  2. the office is killed with SIGSEGV: the office's own fatal-signal handler writes the signal and
     the stack to last-session.err (kept as crashed-session.err in --out), the session marker stays;
  3. the next start asks once; Gửi opens the crash report with diagnostics ticked by default; the payload the server
     receives carries systemInfo, the log with the exception and the crash signature (the fatal signal, module +offset frames).
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "unit")]
import error_report_gui as gui  # noqa: E402
import hst_gui  # noqa: E402
from error_report_fake_server import FakeServer, invalid  # noqa: E402

UNO_PORT = 22193
DIALOG, PROMPT = (320, 262), (280, 62)
FAILING_COMMAND = "org.hst.office.vi:ToggleDuplex"
TEST_RAISE = {"HST_DIAG_TEST_RAISE": "ToggleDuplex"}  # read by test packages only (hst_office.dispatch.raise_for_test)
RESULTS = []


def record(label, ok, detail=""):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % str(detail)[:300]) if not ok else ""), flush=True)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


class DesktopStderr:
    """soffice inherits /dev/null as stderr, like a start from the desktop menu (a pipe or terminal is left alone)."""
    def __enter__(self):
        self.saved = os.dup(2)
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, 2)
        os.close(null)

    def __exit__(self, *exc):
        os.dup2(self.saved, 2)
        os.close(self.saved)


def first_session(office, diag, out):
    with DesktopStderr():
        office.start()
    start = gui.wait(lambda: gui.windows(office, "^HST Office$"), 30)
    record("start center shown", start)
    frame = office.desktop().getCurrentFrame() or office.desktop().getFrames().getByIndex(0)
    thread = gui.dispatch_async(office, frame, FAILING_COMMAND)
    box = gui.wait(lambda: gui.windows(office, "^Công cụ tiếng Việt HST$"), 20)
    record("the failing command tells the user", box)
    if box:
        gui.click_message_button(office, box[0][0])
    thread.join(10)
    log = read(os.path.join(diag, "hst-office.log"))
    record("log: session start with version and OS", "INFO session: start " in log and " python " in log, log[:300])
    record("log: the exception with its traceback", "ERROR dispatch ToggleDuplex: RuntimeError: diagnostics test" in log
           and "\n  Traceback (most recent call last):" in log and "<PATH>/dispatch.py" in log, log[-600:])
    record("log: the user-visible error as a warning", "WARNING command: RuntimeError" in log, log[-300:])
    record("log: no profile path or build user", office.workdir not in log and hst_gui.BUILD_USER not in log)
    record("session marker written", os.path.exists(os.path.join(diag, "session.json")))
    pid = office.pid
    os.kill(pid, signal.SIGSEGV)
    gone = gui.wait(lambda: office.pid is None, 60)
    record("the office ended on SIGSEGV", gone)
    err = read(os.path.join(diag, "last-session.err"))
    with open(os.path.join(out, "crashed-session.err"), "w", encoding="utf-8") as handle:
        handle.write(err)  # kept for the report: the next start truncates it
    record("last-session.err has the signal and stack", "Fatal exception: Signal 11" in err and "Stack:" in err, err[-500:])
    record("session marker left after the crash", os.path.exists(os.path.join(diag, "session.json")))
    office.proc.wait(30)


def crash_report(office, server, out):
    with DesktopStderr():
        office.start(fresh=False)
    prompt = gui.wait(lambda: [w for w in gui.windows(office, "^HST Office$")
                               if gui.size(office.display, w[0])[0] < 700], 40)
    record("next start asks about the crash", prompt)
    if not prompt:
        return
    time.sleep(1.5)
    gui.shot(office, prompt[0][0], os.path.join(out, "crash-prompt.png"))
    gui.click(office, prompt[0][0], 193, 49, PROMPT)  # Gửi
    wid = gui.dialog(office)
    record("crash report dialog opens", wid)
    if not wid:
        return
    time.sleep(1)
    gui.shot(office, wid, os.path.join(out, "crash-dialog.png"))
    before = len(server.requests)
    gui.click(office, wid, 227, 249, DIALOG)  # Gửi, diagnostics left as ticked by default
    gui.wait(lambda: len(server.requests) > before, 20)
    box = gui.dialog(office, small=True)
    if box:
        gui.click_message_button(office, box)
    doc = json.loads(server.requests[-1]["body"]) if len(server.requests) > before else {}
    with open(os.path.join(out, "crash-payload.json"), "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)
    diagnostics = doc.get("diagnostics", {})
    record("server accepts the payload", doc and not invalid(doc), invalid(doc) if doc else "no request")
    record("payload: kind crash", doc.get("kind") == "crash")
    record("payload: systemInfo", "VCL: gtk3" in diagnostics.get("systemInfo", ""), diagnostics.get("systemInfo"))
    record("payload: log with the exception", "diagnostics test hook" in diagnostics.get("log", ""), diagnostics.get("log"))
    crash = diagnostics.get("crash", "")
    record("payload: crash signature", "Office handler: Signal 11 (SIGSEGV)" in crash and ".so " in crash, crash)
    raw = server.requests[-1]["body"].decode("utf-8") if len(server.requests) > before else ""
    record("payload: no profile path or build user", raw and office.workdir not in raw
           and hst_gui.BUILD_USER not in raw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(gui.ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(gui.ROOT, "tests", "output", "local-diagnostics"))
    ap.add_argument("--display", default=":75")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    instdir = gui.prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = FakeServer()
    profile = os.path.join(args.out, "gui")
    diag = os.path.join(profile, "profile", "user", "hst-office")
    office = hst_gui.Office(instdir, profile, UNO_PORT, display=args.display, nodefault=False,
                            env=dict(TEST_RAISE, HST_ERROR_REPORT_TEST_URL=server.url))
    try:
        first_session(office, diag, args.out)
        crash_report(office, server, args.out)
    finally:
        office.stop()
        server.close()
    failed = [label for label, ok in RESULTS if not ok]
    print("local diagnostics runtime: %d checks, %d failed%s" % (len(RESULTS), len(failed),
                                                                 (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
