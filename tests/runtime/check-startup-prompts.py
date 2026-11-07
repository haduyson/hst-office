#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up questions on the real build (Linux): one modal question per start, welcome first, then
"Mở tài liệu văn phòng bằng HST Office?" once; "Đồng ý" sets the launchers with xdg-mime, "Để sau" waits.

Usage: python3 tests/runtime/check-startup-prompts.py --display :131 [--instdir upstream/libreoffice/instdir] [--out DIR]
                                                      [--port 2196]
The display must already run; it is never started or stopped here. Everything happens under the test's own HOME
(xdg-mime writes $HOME/.config/mimeapps.list there), so the machine's file associations never change. Exit 1 on failure.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402

ROWS = []
QUESTION_TITLE = "HST Office"
WELCOME = re.compile(r"Chào mừng|chào đón bạn|Welcome to")
LAUNCHERS = {"writer": "application/vnd.oasis.opendocument.text;application/msword;"
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document;text/plain;",
             "calc": "application/vnd.oasis.opendocument.spreadsheet;application/vnd.ms-excel;"
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;text/csv;",
             "impress": "application/vnd.oasis.opendocument.presentation;application/vnd.ms-powerpoint;"
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation;"}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:200]), flush=True)


def dialogs(display, pid):
    """(window id, name) of this office's mapped dialog windows."""
    found = []
    for wid, name in hst_gui.toplevels(display, pid):
        kind = subprocess.run(["xprop", "-display", display, "-id", wid, "_NET_WM_WINDOW_TYPE"],
                              capture_output=True, text=True).stdout
        if "_NET_WM_WINDOW_TYPE_DIALOG" in kind:
            found.append((wid, name))
    return found


def watch(office, seconds):
    """Every dialog name seen during `seconds` (polled), in order of appearance."""
    seen, deadline = [], time.time() + seconds
    while time.time() < deadline:
        for _wid, name in dialogs(office.display, office.pid):
            if name not in seen:
                seen.append(name)
        time.sleep(1)
    return seen


def question(office, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for wid, name in dialogs(office.display, office.pid):
            if name == QUESTION_TITLE:
                return wid
        time.sleep(1)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/startup-prompts"))
    parser.add_argument("--port", type=int, default=2196)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    env = dict(os.environ, DISPLAY=args.display)

    def office_for(name, config, fresh=True):
        home = os.path.join(os.path.abspath(out), name, "home")
        # runuser resets HOME to the build user's: hand the private HOME to soffice (and so to xdg-mime) explicitly
        office = hst_gui.Office(args.instdir, os.path.join(out, name), args.port, display=args.display,
                                nodefault=False, welcome=True,
                                config=[("/org.hasontech.hstoffice.DefaultApps", "Ask", "true")] + list(config),
                                env={"HOME": home, "XDG_CONFIG_HOME": os.path.join(home, ".config"),
                                     "XDG_DATA_HOME": os.path.join(home, ".local", "share")})
        if fresh:
            shutil.rmtree(home, ignore_errors=True)  # a mimeapps.list left by an earlier run would count as answered
            apps = os.path.join(home, ".local", "share", "applications")
            os.makedirs(apps, exist_ok=True)
            for module, types in LAUNCHERS.items():
                with open(os.path.join(apps, "vn.hasontech.hstoffice-%s.desktop" % module), "w", encoding="utf-8") as handle:
                    handle.write("[Desktop Entry]\nType=Application\nName=HST %s\nExec=true %%U\nMimeType=%s\n" % (module, types))
        return office.start(fresh=fresh), home

    def query(home, mime):
        return subprocess.run(["xdg-mime", "query", "default", mime], env=dict(env, HOME=home, XDG_DATA_HOME=os.path.join(
                              home, ".local", "share"), XDG_CONFIG_HOME=os.path.join(home, ".config")),
                              capture_output=True, text=True).stdout.strip()

    def key(wid, *keys):
        subprocess.run(["xdotool", "windowfocus", "--sync", wid], env=env, check=False, timeout=10)
        for item in keys:
            subprocess.run(["xdotool", "key", item], env=env, check=False, timeout=10)
            time.sleep(0.4)

    # 1. a new user: the welcome dialog only, no second question in the same start
    office, home = office_for("first", [("/org.hasontech.hstoffice.Welcome", "Shown", "false")])
    try:
        seen = watch(office, 25)
        check("first start: the welcome dialog is shown", any(WELCOME.search(n) for n in seen), seen)
        office.close_welcome()
        seen += watch(office, 12)
        check("first start: the default-apps question is not shown with it", QUESTION_TITLE not in seen, seen)
    finally:
        office.stop()
    # 2. next start: the question, once; Đồng ý sets HST for the office types of the launchers
    office, home = office_for("first", [], fresh=False)
    try:
        wid = question(office)
        check("second start: the question is shown", wid is not None)
        hst_gui.screenshot(os.path.join(out, "question.png"), args.display)
        before = query(home, DOCX)
        if wid:
            key(wid, "Tab", "space")  # the focus starts on "Để sau"; Tab reaches "Đồng ý"
        time.sleep(4)
        after = query(home, DOCX)
        check("Đồng ý makes HST Writer open .docx", after == "vn.hasontech.hstoffice-writer.desktop", (before, after))
        check("Đồng ý leaves plain text alone", query(home, "text/plain") != "vn.hasontech.hstoffice-writer.desktop")
        others = [n for n in watch(office, 6) if n != QUESTION_TITLE]
        check("no other modal question in that start", not any(WELCOME.search(n) for n in others), others)
    finally:
        office.stop()
    office, home = office_for("first", [], fresh=False)
    try:
        check("third start: never asked again", question(office, 20) is None)
    finally:
        office.stop()
    # 3. Để sau (Esc): not asked at the next start (14 days), counted once
    office, home = office_for("later", [])  # the harness seeds Welcome/Shown = true
    try:
        wid = question(office)
        check("welcome already seen: the question comes on this start", wid is not None)
        if wid:
            key(wid, "Escape")
    finally:
        office.stop()
    office, home = office_for("later", [], fresh=False)
    try:
        check("after Để sau: not asked at the next start", question(office, 20) is None)
        check("after Để sau: nothing was registered", query(home, DOCX) != "vn.hasontech.hstoffice-writer.desktop")
    finally:
        office.stop()
    with open(os.path.join(out, "later", "profile", "user", "registrymodifications.xcu"), encoding="utf-8") as handle:
        state = handle.read()
    check("after Để sau: asked once is stored", re.search(r'DefaultApps"><prop oor:name="Asked" oor:op="fuse"><value>1<', state) is not None)
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
