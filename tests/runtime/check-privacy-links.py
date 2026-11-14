#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The four privacy policy links on a real HST Office: About, Tùy chọn ▸ HST Office ▸ Cập nhật, Báo lỗi cho HASON
TECH and the citation source form (Nguồn tài liệu mới). Each is clicked with the mouse and must hand exactly its URL
(https://office.hasontech.vn/quyen-rieng-tu/ + utm_medium of its place) to the system browser; nothing may reach the
browser before the clicks.

Usage: python3 tests/runtime/check-privacy-links.py --instdir DIR --display :N [--out DIR] [--shots DIR]
                                                    [--lang vi_VN.UTF-8|en_US.UTF-8] [--port 2231]
The browser is a recording stand-in (privacy_links_gui.install_browser): xdg-open on PATH (the office's
SystemShellExecute) and the https handler of GIO in test XDG directories (GTK link buttons). The X display must
already run (Xvfb); it is never started or stopped here. Screenshots: <place>.png. Exit 1 when a check fails.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import privacy_links_gui as gui  # noqa: E402

PAGE = "https://office.hasontech.vn/quyen-rieng-tu/"
TAIL = "?utm_source=hst-office&utm_medium=%s&utm_campaign=hst-office-1-0"
RESULTS = []


def record(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % detail) if detail and not ok else ""), flush=True)


def expect_click(office, browser, place, medium, wid, point, shots):
    """Click `point` (screen pixels) and check the browser got exactly the URL of `medium`."""
    before = len(browser.urls())
    record(place + ": the link is shown", point, "no link-coloured text found")
    gui.shot(office, wid, os.path.join(shots, place + ".png"))
    if not point:
        return
    gui.mouse_click(office, *point)
    got = gui.wait(lambda: browser.urls()[before:], 15) or []
    record(place + ": opens %s" % medium, got == [PAGE + TAIL % medium], got)


def about(office, frame, browser, shots):
    thread = gui.dispatch_async(office, frame, ".uno:About")
    wid = gui.wait_window(office, gui.ABOUT_TITLE)
    record("About: dialog opens", wid)
    if wid:
        time.sleep(1.5)
        expect_click(office, browser, "about", "about", wid, gui.rightmost_link(office, wid), shots)
        gui.key(office, wid, "Escape")
    thread.join(15)


def options(office, frame, browser, shots):
    url = gui.update_page_url(office.ctx)
    thread = gui.dispatch_async(office, frame, ".uno:OptionsTreeDialog", (("OptionsPageURL", url),))
    wid = gui.wait_window(office, gui.OPTIONS_TITLE)
    record("Options: dialog opens on HST Office ▸ Cập nhật", wid)
    if wid:
        time.sleep(2)
        point = gui.rightmost_link(office, wid, left_fraction=0.3)
        expect_click(office, browser, "options-update", "options", wid, point, shots)
        gui.key(office, wid, "Escape")
    thread.join(15)


def error_report(office, frame, browser, shots):
    thread = gui.dispatch_async(office, frame, "org.hst.office.vi:ReportError")
    wid = gui.wait_window(office, "^Báo lỗi cho HASON TECH$")
    record("Error report: dialog opens", wid)
    if wid:
        time.sleep(1.5)
        expect_click(office, browser, "error-report", "error-report", wid, gui.rightmost_link(office, wid), shots)
        gui.key(office, wid, "Escape")
    thread.join(15)


def citations(office, frame, browser, shots, titles):
    thread = gui.dispatch_async(office, frame, "org.hst.office.vi:CitationLibrary")
    library = gui.wait_window(office, "^%s$" % titles[0])
    record("Citations: library opens", library)
    if not library:
        return
    time.sleep(1.5)
    gui.key(office, library, "Tab", "Tab", "Tab", "space")
    wid = gui.wait_window(office, "^%s$" % titles[1])
    record("Citations: source form opens", wid)
    if wid:
        time.sleep(1.5)
        point = gui.rightmost_link(office, wid, top_fraction=0.0, bottom_fraction=0.3)
        expect_click(office, browser, "citation-source", "citations", wid, point, shots)
        gui.key(office, wid, "Escape")
        time.sleep(1)
    gui.key(office, library, "Escape")
    thread.join(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", required=True)
    parser.add_argument("--out", default="tests/output/privacy-links")
    parser.add_argument("--shots", default=None)
    parser.add_argument("--lang", default="vi_VN.UTF-8")
    parser.add_argument("--port", type=int, default=2231)
    args = parser.parse_args()
    shots = os.path.abspath(args.shots or os.path.join(args.out, "shots"))
    hst_gui.setup_uno(args.instdir)
    workdir = os.path.abspath(os.path.join(args.out, "office"))
    browser = gui.install_browser(workdir)
    office = hst_gui.Office(args.instdir, workdir, args.port, display=args.display, lang=args.lang,
                            env=browser.env, config=gui.QUIET_CONFIG)
    try:
        office.start()
        frame = office.load("private:factory/swriter").getCurrentController().getFrame()
        time.sleep(3)
        titles = gui.citation_titles(args.lang, args.instdir)
        record("nothing reached the browser before the first click", browser.urls() == [], browser.urls())
        about(office, frame, browser, shots)
        options(office, frame, browser, shots)
        error_report(office, frame, browser, shots)
        citations(office, frame, browser, shots, titles)
        record("nothing reached the browser except the four clicks", len(browser.urls()) == 4, browser.urls())
    finally:
        office.stop()
    print("%d/%d passed" % (sum(RESULTS), len(RESULTS)))
    return 0 if RESULTS and all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
