# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of Trợ giúp ▸ Báo lỗi cho HASON TECH in a real HST Office (soffice runs as hstbuild, never root).

Usage: python3 tests/runtime/check-error-report.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/error-report-runtime] [--shots tests/output/screenshots-error-report] [--display :75]

Uses a hard-linked instdir copy with the test package (error_report_gui.prepare_instdir) and sends only to the local
fake server of tests/unit/error_report_fake_server.py (HST_ERROR_REPORT_TEST_URL, honoured by test packages only):
  1. the entry is in the classic Help menu of the Start Center, Writer, Sheets and Slides and in the ribbon ≡ menu;
  2. the dialog opens (light and dark), the preview shows the JSON, Gửi sends the payload typed in, without
     diagnostics; with the box ticked, systemInfo and the filtered HST log come along, free of profile paths;
  3. a 503 answer offers the e-mail fallback;
  4. Crashed = true in the profile: the next start asks once; Gửi opens the dialog with kind=crash.
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "unit")]
import error_report_gui as gui  # noqa: E402
import hst_gui  # noqa: E402
from error_report_fake_server import FakeServer, invalid  # noqa: E402

UNO_PORT = 22191
DIALOG, PREVIEW, PROMPT = (320, 262), (380, 262), (280, 62)
RESULTS = []


def record(label, ok, detail=""):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % detail) if detail and not ok else ""), flush=True)


def send_report(office, frame, server, shots, name, text, diagnostics=False, crash_wid=None):
    """Open (or reuse) the dialog, type `text`, optionally tick the box, preview, send; returns the dialog wid."""
    thread = None if crash_wid else gui.dispatch_async(office, frame)
    wid = crash_wid or gui.dialog(office)
    record(name + ": dialog opens", wid)
    if not wid:
        return None
    if text:  # Xvfb has no window manager: give the dialog the X focus before typing
        gui.xdo(office, "windowfocus", "--sync", wid)
        gui.click(office, wid, 160, 70, DIALOG)
        gui.xdo(office, "type", "--delay", "40", text)
    if diagnostics:
        gui.click(office, wid, 40, 191, DIALOG)
    time.sleep(0.8)
    gui.shot(office, wid, os.path.join(shots, name + "-dialog.png"))
    gui.click(office, wid, 54, 249, DIALOG)
    view = gui.wait(lambda: gui.windows(office, "^Nội dung sẽ gửi$"), 10)
    record(name + ": preview opens", view)
    if view:
        time.sleep(0.8)
        gui.shot(office, view[0][0], os.path.join(shots, name + "-preview.png"))
        gui.click(office, view[0][0], 345, 249, PREVIEW)
    before = len(server.requests)
    gui.click(office, wid, 227, 249, DIALOG)
    gui.wait(lambda: len(server.requests) > before, 20)
    box = gui.dialog(office, small=True)
    time.sleep(0.8)
    gui.shot(office, box, os.path.join(shots, name + "-result.png"))
    if box:
        gui.click_message_button(office, box)
    if thread:
        thread.join(10)
    return wid


def check_payload(name, server, profile_dir, expect):
    doc = json.loads(server.requests[-1]["body"]) if server.requests else {}
    record(name + ": the server accepts the payload", doc and not invalid(doc), invalid(doc) if doc else "no request")
    for key, value in expect.items():
        got = doc.get(key) if "." not in key else doc.get(key.split(".")[0], {}).get(key.split(".")[1])
        record("%s: %s" % (name, key), got == value if not callable(value) else value(got), repr(got)[:200])
    raw = server.requests[-1]["body"].decode("utf-8") if server.requests else ""
    record(name + ": no profile path or user name", raw and profile_dir not in raw and hst_gui.BUILD_USER not in raw)
    return doc


def menus(office, shots):
    title, contexts = gui.help_addon(office)
    record("classic Help menus: the entry is merged", title == gui.LABEL, title)
    record("Start Center: classic Help menu has the entry", "com.sun.star.frame.StartModule" in contexts)
    start = gui.windows(office, "^HST Office$")
    if start:
        gui.open_start_center_help(office, start[0][0], os.path.join(shots, "menu-start-center.png"))
    for module in ("swriter", "scalc", "simpress"):
        doc = office.load("private:factory/" + module)
        time.sleep(3)
        record(module + ": ribbon ≡ menu has the entry", (gui.COMMAND, gui.LABEL) in gui.ribbon_menu_items(office, module))
        record(module + ": classic Help menu has the entry", gui.MODULES[module] in contexts)
        wid = gui.windows(office, "HST (Writer|Sheets|Slides)")
        if wid:
            gui.open_ribbon_menu(office, wid[0][0], os.path.join(shots, "menu-%s.png" % module))
        if module == "swriter":
            writer = doc.getCurrentController().getFrame()
        else:
            doc.close(True)
    return writer


def crash_phase(instdir, out, shots, server, display):
    office = hst_gui.Office(instdir, os.path.join(out, "gui"), UNO_PORT, display=display, nodefault=False,
                            env={"HST_ERROR_REPORT_TEST_URL": server.url},
                            config=[("/org.openoffice.Office.Recovery/RecoveryInfo", "Crashed", "true")])
    try:
        office.start()
        prompt = gui.wait(lambda: [w for w in gui.windows(office, "^HST Office$")
                                   if gui.size(display, w[0])[0] < 700], 40)
        record("crash: the next start asks", prompt)
        if not prompt:
            return
        time.sleep(1.5)
        gui.shot(office, prompt[0][0], os.path.join(shots, "crash-prompt.png"))
        gui.click(office, prompt[0][0], 193, 49, PROMPT)
        wid = gui.dialog(office)
        send_report(office, None, server, shots, "crash", "", diagnostics=True, crash_wid=wid)
        check_payload("crash", server, os.path.join(out, "gui"), {
            "kind": "crash", "diagnostics": lambda d: bool(d) and "Emergency save ran: yes" in d.get("crash", "")})
        node = office.service("com.sun.star.configuration.ConfigurationProvider")
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Recovery/RecoveryInfo")
        crashed = node.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
        record("crash: asked once (Crashed cleared)", crashed.getPropertyValue("Crashed") is False)
    finally:
        office.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(gui.ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(gui.ROOT, "tests", "output", "error-report-runtime"))
    ap.add_argument("--shots", default=os.path.join(gui.ROOT, "tests", "output", "screenshots-error-report"))
    ap.add_argument("--display", default=":75")
    args = ap.parse_args()
    for folder in (args.shots, args.out):
        os.makedirs(folder, exist_ok=True)
    instdir = gui.prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = FakeServer()
    tmp = os.path.join(args.out, "tmp")
    os.makedirs(tmp, exist_ok=True)  # TMPDIR of soffice: holds the HST log the filter must clean
    profile = os.path.join(args.out, "gui")
    with open(os.path.join(tmp, "hst-office-errors.log"), "w", encoding="utf-8") as log:
        log.write("2026-11-06 10:00:01 ConvertEncoding\nIOError: %s/home/Tài liệu/Báo cáo.docx\n" % profile)
    os.system("chmod -R a+rwX %s" % tmp)
    env = {"HST_ERROR_REPORT_TEST_URL": server.url, "TMPDIR": tmp}
    try:
        for dark in (False, True):
            config = [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2" if dark else "1"),
                      ("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]
            office = hst_gui.Office(instdir, profile, UNO_PORT, display=args.display, nodefault=False,
                                    env=dict(env, GTK_THEME="Adwaita:dark" if dark else "Adwaita"), config=config)
            try:
                office.start()
                if gui.wait(office.close_welcome, 20):  # the test profile shows it; it would cover the menus
                    gui.wait(lambda: not gui.windows(office, "chào đón"), 10)
                tag = "dark" if dark else "light"
                frame = menus(office, args.shots) if not dark else office.load("private:factory/swriter") \
                    .getCurrentController().getFrame()
                send_report(office, frame, server, args.shots, tag, "Khong luu duoc tep docx")
                check_payload(tag, server, profile, {"kind": "user", "app": "writer", "diagnostics": None,
                                                    "description": "Khong luu duoc tep docx"})
                if not dark:
                    send_report(office, frame, server, args.shots, "diagnostics", "Loi khi in", diagnostics=True)
                    check_payload("diagnostics", server, profile, {"diagnostics": lambda d: bool(d)
                                  and "VCL: gtk3" in d.get("systemInfo", "") and "<PATH>" in d.get("log", "")
                                  and "Báo cáo" not in d.get("log", "")})  # noqa: E127
                    server.mode = 503
                    send_report(office, frame, server, args.shots, "server-error", "Loi 503")
                    server.mode = None
                    wid = gui.dialog(office)
                    if wid:
                        gui.click(office, wid, 285, 249, DIALOG)  # Hủy
            finally:
                office.stop()
        crash_phase(instdir, args.out, args.shots, server, args.display)
    finally:
        server.close()
    failed = [label for label, ok in RESULTS if not ok]
    print("error report runtime: %d checks, %d failed%s" % (len(RESULTS), len(failed),
                                                             (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
