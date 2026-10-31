# SPDX-License-Identifier: AGPL-3.0-only
"""Check that window titles show HST Office without the engine version (26.8).

Usage: python3 tests/runtime/check-window-title.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/window-title] [--shots tests/output/screenshots-tabs] [--display :97]

Starts the GUI (Start Center), opens a Writer, a Calc and an Impress document and the About
dialog, and asserts on the X window names and the frames' Title property:
  - no title contains the engine version ("26.8");
  - the Start Center window is titled exactly "HST Office";
  - document windows end with "HST Writer", "HST Sheets", "HST Slides" (and "HST Draw" for Draw);
  - the HST release version from /VERSION is what About shows (static: libcuilo.so).
Exit 1 when a check fails.
"""
import argparse
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
ENGINE = re.compile(r"\b26\.8\b")


def names(display):
    out = subprocess.run(["xwininfo", "-display", display, "-root", "-children"], capture_output=True, text=True).stdout
    return [m.group(1) for m in re.finditer(r'0x[0-9a-f]+ "([^"]*)"', out)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/window-title"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-tabs"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    version = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
    with open(os.path.join(args.instdir, "program", "libcuilo.so"), "rb") as handle:
        # about.cxx: u"" HST_VERSION " (" -> a UTF-16 literal in the library
        check("About shows the HST version from /VERSION", f"{version} (".encode("utf-16-le") in handle.read(), version)

    hst_gui.setup_uno(args.instdir)
    # Tabs off: every document window is mapped, so all titles can be read from X.
    office = hst_gui.Office(args.instdir, args.out, 21995, display=args.display, nodefault=False,
                            config=[("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")]).start()
    try:
        time.sleep(4)
        start = [n for n in hst_gui.mapped_toplevels(args.display, pid=office.pid) if "HST" in n]
        check("Start Center title is \"HST Office\"", start == ["HST Office"], repr(start))
        for factory in ("swriter", "scalc", "simpress", "sdraw"):
            office.load(f"private:factory/{factory}", "_blank")
        time.sleep(4)
        frames = office.desktop().getFrames()
        titles = [frames.getByIndex(i).Title for i in range(frames.getCount())]
        mapped = hst_gui.mapped_toplevels(args.display, pid=office.pid)
        check("no frame title contains the engine version", not any(ENGINE.search(t) for t in titles), repr(titles))
        check("no mapped window title contains the engine version", not any(ENGINE.search(n) for n in mapped),
              repr(mapped))
        for module in ("HST Writer", "HST Sheets", "HST Slides"):
            check(f"window titled '... — {module}'",
                  any(t.endswith(f" — {module}") for t in titles), repr(titles))
        check("Draw window titled '... — HST Draw'", any(t.endswith(" — HST Draw") for t in titles), repr(titles))
        check("no title keeps the long \"HST Office <module>\" form",
              not any(re.search(r"HST Office (Writer|Calc|Impress|Sheets|Slides|Draw|Math|Base)$", t) for t in titles),
              repr(titles))
        worker = threading.Thread(target=office.dispatch, args=(frames.getByIndex(0), ".uno:About"), daemon=True)
        worker.start()
        time.sleep(5)
        office.screenshot(os.path.join(args.shots, "20-about-version.png"))
        # every window of this instance, mapped or not (also the hidden helper windows)
        own = [n for _w, n in hst_gui.toplevels(args.display, office.pid, mapped=False)]
        check("no window of the process names the engine version", not any(ENGINE.search(n) for n in own),
              repr(sorted(set(own))))
        about = [n for n in own if "HST Office" in n and n not in titles and n != "HST Office"]
        check("About dialog title has no engine version", bool(about) and not any(ENGINE.search(n) for n in about),
              repr(about))
        subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=args.display), check=False)
        worker.join(20)
    finally:
        office.stop()
    failed = sum(r["status"] == "FAIL" for r in results)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
