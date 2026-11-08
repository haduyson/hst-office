#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up questions of an INSTALLED HST Office on Windows, start 1, 2 and 3 of a new user, as the user meets them.

The Windows counterpart of check-startup-prompts.py (Linux), with its question and welcome titles. Unlike the Linux
check the profile is not warmed up or seeded: start 1 is the very first start of an empty profile, with the bundled
extension sync it does, the Start Center shown and no setting forced. One modal question per start:
  start 1: the welcome dialog, and nothing else in that start;
  start 2: "Mở tài liệu văn phòng bằng HST Office?" when the installer checkbox was left unticked
           (--expect question; answered with real keys), none when it was ticked (--expect registered: the installer
           wrote DefaultApps\\ChosenAtInstall = 1, so HST is already chosen);
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


def watch(office, seconds, out, label, close=None):
    """Every dialog seen during `seconds`: [(title, shown texts)]. A screenshot of each; `close(title, texts)` returns
    True for a dialog this function should close (with endExecute) once recorded."""
    seen, deadline = [], time.time() + seconds
    while time.time() < deadline:
        for window, title in wg.dialogs(office):
            texts = wg.texts(window)
            key = (title, tuple(texts[:3]))
            if any(key == (t, tuple(x[:3])) for t, x in seen):
                continue
            seen.append((title, texts))
            time.sleep(1.5)  # let it paint
            wg.screenshot(os.path.join(out, "%s-%d.png" % (label, len(seen))))
            dump_tree(window, os.path.join(out, "%s-%d-accessibility.txt" % (label, len(seen))))
            if close and close(title, texts):
                wg.close_dialog(window)
        time.sleep(0.5)
    return seen


def is_question(title, texts):
    """The default-apps question: a dialog titled exactly "HST Office" at start-up. Its text is checked when UNO
    accessibility reaches it; either way the state it writes once answered (Asked, Done) proves which dialog it was."""
    return title == QUESTION_TITLE and (not texts or any(QUESTION in text for text in texts))


def dump_tree(window, path):
    """Role and name of every node of a dialog's accessibility tree (diagnostics)."""
    lines = []
    for context, depth in wg.walk(window):
        try:
            lines.append("%s%s %r showing=%s" % ("  " * depth, context.getAccessibleRole(), context.getAccessibleName(),
                                                  wg.showing(context)))
        except Exception as error:  # noqa: BLE001
            lines.append("%s<%s>" % ("  " * depth, type(error).__name__))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


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
    try:
        # ---- start 1 ----
        began = time.time()
        office.start(fresh=not args.carried)
        check.note("start 1: UNO up after", "%.1f s, soffice.bin %s" % (time.time() - began, office.bin_pids()))
        check.note("start 1: state at once", state(office))
        seen = watch(office, 45, out, "start1", close=lambda title, texts: WELCOME.search(title) is not None)
        check.note("start 1: soffice.bin after 45 s (another id: the office restarted itself)", office.bin_pids())
        check.note("start 1: dialogs", seen)
        welcome = [title for title, _texts in seen if WELCOME.search(title)]
        if args.carried:
            check.note("start 1 (carried profile): welcome shown", bool(welcome))
        else:
            check("start 1: the welcome dialog is shown", bool(welcome), seen)
        check("start 1: the default-apps question is not shown with it", not any(is_question(*s) for s in seen), seen)
        first = state(office)
        check.note("start 1: state", first)
        check("start 1: the extension's settings are registered", not any(str(v).startswith("ERROR") for v in first.values()),
              first)
        check("start 1: the welcome is stored as seen", first.get("Shown") is True, first)
        for window, _title in wg.dialogs(office):  # anything left open would veto the quit
            wg.close_dialog(window)
        check.note("start 1: exit code", office.stop())
        # ---- start 2 ----
        office.start()
        check.note("start 2: soffice.bin", office.bin_pids())
        answered = {}

        def answer(title, texts):
            if not is_question(title, texts):
                return True  # any other dialog: recorded and closed
            hwnd = wg.hwnd_of(title)
            answered["foreground"] = bool(hwnd) and wg.foreground(hwnd)
            # the focus starts on "Để sau" (default, Esc and Enter decline); Tab reaches "Đồng ý"
            wg.keys(*(("tab", "space") if args.answer == "accept" else ("escape",)))
            answered["keys"] = args.answer
            return False
        seen = watch(office, 60, out, "start2", close=answer)
        check.note("start 2: dialogs", seen)
        questions = [s for s in seen if is_question(*s)]
        second = state(office)
        check.note("start 2: state", second)
        check.note("registry at start 2", registry_evidence())
        if args.expect == "question":
            check("start 2: the default-apps question is shown", len(questions) == 1, seen)
            check("start 2: no welcome again", not any(WELCOME.search(title) for title, _texts in seen), seen)
            check("start 2: the question was answered with the keyboard", answered.get("keys") == args.answer, answered)
            check("start 2: the answer is stored", second.get("Asked") == 1
                  and second.get("Done") is (args.answer == "accept"), second)
        else:
            check("start 2: no question (the installer already chose HST Office)", not questions, seen)
            check("start 2: the installer's choice counts as answered", second.get("Done") is True, second)
        for window, _title in wg.dialogs(office):
            wg.close_dialog(window)
        check.note("start 2: exit code", office.stop())
        # ---- start 3 ----
        office.start()
        seen = watch(office, 30, out, "start3", close=lambda title, texts: True)
        check.note("start 3: dialogs", seen)
        check("start 3: no default-apps question", not any(is_question(*s) for s in seen), seen)
        check("start 3: no welcome", not any(WELCOME.search(title) for title, _texts in seen), seen)
        check.note("start 3: state", state(office))
        check.note("start 3: exit code", office.stop())
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        if office.proc is not None:
            office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
