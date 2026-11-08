#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up questions of an INSTALLED HST Office on Windows, start 1, 2 and 3 of a new user, as the user meets them.

The Windows counterpart of check-startup-prompts.py (Linux), with its question and welcome titles. Unlike the Linux
check the profile is not warmed up or seeded: start 1 is the very first start of an empty profile, with the bundled
extension sync it does, the Start Center shown and no setting forced. One modal question per start:
  the welcome dialog at start 1 of a new profile, and nothing else in that start;
  "Mở tài liệu văn phòng bằng HST Office?" once, at the first start without the welcome, when the installer checkbox
           was left unticked (--expect question; answered with real keys), never when it was ticked (--expect
           registered: the installer wrote DefaultApps\\ChosenAtInstall = 1, so HST is already chosen);
  start 3: no question.
--carried: start 1 reuses the profile already in --profile (one an older version left behind), as after uninstalling
the old version and installing this one; the welcome may then be already seen. --warm-only: one start of a new
profile in --profile (of whatever version is installed), its start-up dialogs closed, then quit; no checks.

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-startup-prompts.py --install DIR --out DIR
           --expect question|registered [--answer accept|later] [--profile DIR] [--carried] [--port 2116]
Screenshots: <out>/start<N>-*.png. Results: <out>/results.json. Exit 1 on any FAIL.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402

LINUX = wg.load_check("check-startup-prompts")
QUESTION_TITLE, WELCOME = LINUX.QUESTION_TITLE, LINUX.WELCOME
QUESTION = "Mở tài liệu văn phòng bằng HST Office?"  # hst_office/default_apps.py QUESTION


def registry_evidence():
    """What the default-apps test of the extension reads (default_apps_os.windows_is_registered)."""
    import winreg
    out = {}
    for hive, label in ((winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\HASON TECH\HST Office\DefaultApps") as key:
                out[label + " ChosenAtInstall"] = winreg.QueryValueEx(key, "ChosenAtInstall")[0]
        except OSError:
            out[label + " ChosenAtInstall"] = None
    for extension in (".docx", ".xlsx", ".pptx"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\%s"
                                r"\UserChoice" % extension) as key:
                out[extension] = winreg.QueryValueEx(key, "ProgId")[0]
        except OSError:
            out[extension] = None
    return out


def state(office):
    """The per-user state of both questions, read from the running office."""
    values = {}
    for node, names in (("/org.hasontech.hstoffice.Welcome", ("Shown",)),
                        ("/org.hasontech.hstoffice.DefaultApps", ("Ask", "Asked", "LastAsked", "Done"))):
        for name in names:
            try:
                values[name] = office.config(node, name)
            except Exception as error:  # noqa: BLE001 - schema missing: the extension's config is not registered
                values[name] = "ERROR %s" % type(error).__name__
    return values


def chain_probe(office, install):
    """What the start-up chain (startup_prompts.py) decides from, read in the running office: the jobs bound to
    onFirstVisibleTask, whether the dispatcher job can be made, and the default-apps decision with the installed code."""
    import importlib
    probe = {}
    try:
        probe["onFirstVisibleTask jobs"] = list(office.config(
            "/org.openoffice.Office.Jobs/Events/onFirstVisibleTask/JobList", None).getElementNames())
    except Exception as error:  # noqa: BLE001
        probe["onFirstVisibleTask jobs"] = "ERROR %s" % error
    for service in ("org.hst.office.vi.StartupPromptsJob", "org.hst.office.vi.OptionsAppearance"):
        try:
            probe[service] = office.service(service) is not None
        except Exception as error:  # noqa: BLE001
            probe[service] = "ERROR %s" % error
    python = os.path.join(install, "share", "extensions", "hst-vietnamese-tools", "python")
    if python not in sys.path:
        sys.path.insert(0, python)
    try:
        default_apps = importlib.import_module("hst_office.default_apps")
        loaded = default_apps.load_state(office.ctx)
        probe["load_state"] = loaded
        probe["should_ask"] = default_apps.should_ask(loaded, int(time.time()), False)
        probe["is_registered"] = default_apps.osx.is_registered("Windows")
    except Exception as error:  # noqa: BLE001
        probe["default apps"] = "ERROR %s: %s" % (type(error).__name__, error)
    try:
        crash = importlib.import_module("hst_office.error_report_crash")
        probe["crash question enabled"] = crash.ask_enabled(office.ctx)
    except Exception as error:  # noqa: BLE001
        probe["crash"] = "ERROR %s: %s" % (type(error).__name__, error)
    return probe


def watch(office, seconds, out, label, close=None):
    """Every dialog seen during `seconds`: [(title, shown texts)]. A screenshot of each; `close(title, texts)` returns
    True for a dialog this function should close (with endExecute) once recorded."""
    seen, windows, deadline = [], [], time.time() + seconds
    while time.time() < deadline:
        for window, title in wg.dialogs(office):
            if any(window == known for known in windows):  # pyuno proxies compare by UNO object identity
                continue
            windows.append(window)
            texts = wg.texts(window)
            seen.append((title, texts))
            time.sleep(1.5)  # let it paint
            wg.screenshot(os.path.join(out, "%s-%d.png" % (label, len(seen))))
            if close and close(title, texts):
                wg.close_dialog(window)
        time.sleep(0.5)
    return seen


def is_question(title, texts):
    """The default-apps question: a dialog titled exactly "HST Office" at start-up. Its text is checked when UNO
    accessibility reaches it; either way the state it writes once answered (Asked, Done) proves which dialog it was."""
    return title == QUESTION_TITLE and (not texts or any(QUESTION in text for text in texts))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expect", choices=("question", "registered"))
    parser.add_argument("--answer", choices=("accept", "later"), default="accept")
    parser.add_argument("--profile")
    parser.add_argument("--carried", action="store_true")
    parser.add_argument("--warm-only", action="store_true")
    parser.add_argument("--port", type=int, default=2116)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    if not args.warm_only and not args.expect:
        parser.error("--expect is required")
    check = wg.Results(out, "startup-prompts-%s%s" % (args.expect or "warm", "-carried" if args.carried else ""))
    profile = os.path.abspath(args.profile or os.path.join(out, "profile"))
    office = wg.WinOffice(os.path.abspath(args.install), profile, args.port, os.path.join(out, "logs"))
    if args.warm_only:
        office.start(fresh=True)
        check.note("dialogs of that start", watch(office, 45, out, "warm", close=lambda title, texts: True))
        check.note("state", state(office))
        check.note("exit code", office.stop())
        return 0
    check.note("registry before start 1", registry_evidence())
    answered = {}

    def handle(start):
        def close(title, texts):
            if not is_question(title, texts):
                return True  # the welcome or any other dialog: recorded and closed
            hwnd = wg.hwnd_of(title)
            answered.update(start=start, active=bool(hwnd) and wg.activate(hwnd))
            # the focus starts on "Để sau" (default, Esc and Enter decline); Tab reaches "Đồng ý"
            if args.answer == "accept":
                wg.keys("tab")
                wg.screenshot(os.path.join(out, "start%d-after-tab.png" % start))
                wg.keys("space")
            else:
                wg.keys("escape")
            answered["keys"] = args.answer
            time.sleep(3)
            wg.screenshot(os.path.join(out, "start%d-after-answer.png" % start))
            return False
        return close

    starts = []  # per start: (welcome shown, question shown, dialogs)
    try:
        for start in (1, 2, 3):
            began = time.time()
            office.start(fresh=start == 1 and not args.carried)
            check.note("start %d: UNO up after" % start, "%.1f s, soffice.bin %s" % (time.time() - began, office.bin_pids()))
            if start == 1:
                check.note("start 1: state at once", state(office))
            seen = watch(office, 60 if start < 3 else 30, out, "start%d" % start, close=handle(start))
            check.note("start %d: soffice.bin at the end (another id: the office restarted itself)" % start, office.bin_pids())
            check.note("start %d: dialogs" % start, seen)
            check.note("start %d: chain inputs" % start, chain_probe(office, args.install))
            values = state(office)
            check.note("start %d: state" % start, values)
            welcome = any(WELCOME.search(title) for title, _texts in seen)
            # after Đồng ý a second box, titled the same, says what to do in Settings: only the first counts
            question = bool(seen) and is_question(*seen[0]) if not welcome else any(is_question(*x) for x in seen)
            starts.append((welcome, question, seen))
            check("start %d: at most one start-up question" % start, not (welcome and question), seen)
            check("start %d: the extension's settings are registered" % start,
                  not any(str(v).startswith("ERROR") for v in values.values()), values)
            if start == 1:
                check.note("registry at start 1", registry_evidence())
            for window, _title in wg.dialogs(office):  # anything left open would veto the quit
                wg.close_dialog(window)
            check.note("start %d: exit code" % start, office.stop())
        welcomes = [n + 1 for n, (w, _q, _s) in enumerate(starts) if w]
        questions = [n + 1 for n, (_w, q, _s) in enumerate(starts) if q]
        if args.carried:
            check.note("welcome shown at starts (carried profile)", welcomes)
        else:
            check("the welcome dialog is shown at start 1 only", welcomes == [1], welcomes)
        office.start()  # a fourth start only reads what the three left behind
        final = state(office)
        for window, _title in wg.dialogs(office):
            wg.close_dialog(window)
        office.stop()
        if args.expect == "question":
            # one modal per start: the question comes at the first start without the welcome
            due = next((n + 1 for n, (w, _q, _s) in enumerate(starts) if not w), None)
            check("the default-apps question is shown once, at start %s" % due, questions == [due], questions)
            check("the question was answered with real keys", answered.get("keys") == args.answer, answered)
            check("the answer is stored", final.get("Asked") == 1 and final.get("Done") is (args.answer == "accept"), final)
        else:
            check("no default-apps question in any start (the installer already chose HST Office)", not questions, questions)
            check("the installer's choice counts as answered", final.get("Done") is True, final)
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        if office.proc is not None:
            office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
