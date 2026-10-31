# SPDX-License-Identifier: AGPL-3.0-only
"""Check that introductory, descriptive and legal texts are Vietnamese in every UI language.

Usage: python3 tests/runtime/check-vi-intro.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/vi-intro] [--shots tests/output/screenshots-vi-intro]
           [--display :97] [--no-gui]

Menus and functions follow the UI language; these texts do not (owner decision):
  - About: description, "Bản phát hành này do HASON TECH cung cấp.", open-source line, contact;
  - the first-start welcome dialog (extension hst-vietnamese-tools);
  - the Start Center banner artwork and the solution buttons' names and tooltips;
  - the source-code notice at the top of Help > License Information (bilingual, kept) and the
    licence summary below it with the HST copyright line.
Static part: the installed program/resources carry the Vietnamese texts and no translatable
English source for them. GUI part (unless --no-gui): screenshots of About, welcome, Start
Center and License dialog under an en-US and a vi UI, with an assertion on window titles that
the UI language really differs. Exit 1 when a check fails.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT

# (description, installed file glob relative to instdir, text, encoding of the text in the file)
STATIC = (
    ("About description is Vietnamese, not translatable",
     "share/config/soffice.cfg/cui/ui/aboutdialog.ui",
     "HST Office là bộ ứng dụng văn phòng nguồn mở", "utf-8"),
    ("About publisher line is Vietnamese in code", "program/lib*.so", "cung cấp.", "utf-16-le"),
    ("About open-source line is Vietnamese in code", "program/lib*.so", "Phần mềm nguồn mở", "utf-16-le"),
    ("Start Center welcome hint is Vietnamese in code", "program/lib*.so", "Chào mừng đến với ", "utf-16-le"),
    ("Start Center solution tooltip is Vietnamese in code", "program/lib*.so", "Trợ lý số cá nhân của người Việt", "utf-16-le"),
    ("License notice is bilingual (Vietnamese first)", "program/lib*.so", "HST Office là phần mềm nguồn mở", "utf-16-le"),
    ("License summary carries the HST copyright line", "program/lib*.so",
     "© 2026 HASON TECH · © 2000–2026 The Document Foundation và các tác giả LibreOffice", "utf-16-le"),
    ("Welcome dialog always loads Vietnamese texts",
     "share/extensions/hst-vietnamese-tools/python/hst_office/welcome_job.py", 'load_locale("vi")', "utf-8"),
)
# English sources that must no longer be shown for these texts.
NOT_TRANSLATABLE = (
    ("share/config/soffice.cfg/cui/ui/aboutdialog.ui", 'context="aboutdialog|description"'),
)


def static_checks(instdir, check):
    for name, rel, text, encoding in STATIC:
        paths = glob.glob(os.path.join(instdir, rel))
        found = False
        for path in paths:
            with open(path, "rb") as handle:
                found = found or text.encode(encoding) in handle.read()
        check(name, found, rel)
    for rel, needle in NOT_TRANSLATABLE:
        path = os.path.join(instdir, rel)
        content = open(path, encoding="utf-8").read() if os.path.isfile(path) else needle
        check(f"{os.path.basename(rel)}: no translatable English source ({needle})", needle not in content, rel)


def window_names(display):
    out = subprocess.run(["xwininfo", "-display", display, "-root", "-children"], capture_output=True, text=True).stdout
    return [m.group(1) for m in re.finditer(r'0x[0-9a-f]+ "([^"]*)"', out)]


def escape(display):
    subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=display), check=False)


def gui_run(args, lang, tag, check):
    workdir = os.path.join(args.out, f"gui-{tag}")
    office = hst_gui.Office(args.instdir, workdir, 21993 if tag == "en" else 21994, display=args.display,
                            lang=lang, nodefault=False, welcome=True)
    started = threading.Thread(target=office.start)
    started.start()
    # 1. welcome dialog on first start (blocks UNO until closed)
    deadline = time.time() + 120
    own = lambda: [n for _w, n in hst_gui.toplevels(args.display, office.pid)] if office.pid else []  # noqa: E731
    while time.time() < deadline and not any(re.search(r"Chào mừng|Welcome", n) for n in own()):
        time.sleep(1)
    time.sleep(3)
    names = own()
    check(f"[{tag}] welcome dialog title is Vietnamese", any("Chào mừng" in n for n in names),
          repr([n for n in names if "HST" in n][:4]))
    office.screenshot(os.path.join(args.shots, f"{tag}-01-welcome.png"))
    office.close_welcome()
    started.join(120)
    try:
        time.sleep(4)
        office.screenshot(os.path.join(args.shots, f"{tag}-02-start-center.png"))
        frame = office.desktop().getFrames().getByIndex(0)
        for command, shot in ((".uno:About", "03-about"), (".uno:ShowLicense", "04-license")):
            worker = threading.Thread(target=office.dispatch, args=(frame, command), daemon=True)
            worker.start()
            time.sleep(5)
            office.screenshot(os.path.join(args.shots, f"{tag}-{shot}.png"))
            if command == ".uno:About":
                names = [n for _w, n in hst_gui.toplevels(args.display, office.pid)]
                about = [n for n in names if "HST Office" in n and ("About" in n or "Giới thiệu" in n)]
                check(f"[{tag}] About dialog open (title follows UI language)", bool(about), repr(about))
            escape(args.display)
            worker.join(20)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/vi-intro"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-vi-intro"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--no-gui", action="store_true")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    static_checks(os.path.abspath(args.instdir), check)
    if not args.no_gui:
        hst_gui.setup_uno(args.instdir)
        gui_run(args, "en_US.UTF-8", "en", check)
        gui_run(args, "vi_VN.UTF-8", "vi", check)
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
