# SPDX-License-Identifier: AGPL-3.0-only
"""Switching document tabs never shows a blank, partial or missing window (Linux, GUI build, existing X display).

The Linux counterpart of check-windows-tab-switch-flash.py. X11 without a compositor shows a mapped window at once,
so a tab window mapped before it is painted, or a gap between hiding the old tab and showing the new one, is on the
screen until the next paint. Window modes: office (documents opened from the HST Office window: tabs of every
application and the Start Center) and tabs (documents opened as from the file manager: one window per application).
Switches are real key presses (xdotool XTEST, Ctrl+Alt+. = NextDocumentTab) after focusing the office's own window
on the private test display. screen_patches_x11 samples a patch grid of the window with XGetImage as fast as the X server answers;
screen_patch_compare classifies each sampled picture against the screen before and after the switch and the empty
root window. Usage: python3 tests/runtime/check-tab-switch-flash.py [--instdir upstream/libreoffice/instdir]
[--out tests/output/tab-switch-flash] [--display :97] [--modes office,tabs] [--switches 22]. Exit 1 when a switch
showed the root window (desktop) or a blank/partial window.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import screen_patch_compare as cmp  # noqa: E402
import screen_patches_x11 as sx  # noqa: E402
import tab_switch_flash_matrix as matrix  # noqa: E402

PORT = 21984  # deterministic per check (see hst_gui)
APPS = ("writer", "calc", "impress", "draw", "pdf")


def switch_keys(display, pid, title):
    """Ctrl+Alt+. (XTEST) after focusing the office's own top-level window titled `title` on the private display."""
    env = dict(os.environ, DISPLAY=display)
    wid = next((w for w, name in hst_gui.toplevels(display, pid) if title and name == title), None)
    if not wid:
        return "skipped: no window of this office titled %r" % title
    subprocess.run(["xdotool", "windowfocus", "--sync", wid], env=env, check=False, timeout=10)
    subprocess.run(["xdotool", "key", "ctrl+alt+period"], env=env, check=False, timeout=10)
    return "keys"


def measure(office, display, mode, switches, desktop, patches):
    pid = office.pid
    recorder = sx.Recorder(patches)
    recorder.start()
    time.sleep(0.6)
    marks = []
    for _ in range(switches):
        current = office.desktop().getCurrentFrame()
        start = time.perf_counter()
        driven = switch_keys(display, pid, current.Title if current else "")
        time.sleep(1.4)
        after = office.desktop().getCurrentFrame()
        marks.append((matrix.label(current.Title if current else ""), matrix.label(after.Title if after else ""),
                      driven, start))
    recorder.stop.set()
    recorder.join(10)
    rows = []
    for before, after, driven, start in marks:
        prior = [f for t, f in recorder.frames if t < start]
        during = [f for t, f in recorder.frames if start <= t <= start + 1.2]
        if not prior or not during:
            continue
        distinct = [f for i, f in enumerate(during) if i == 0 or f != during[i - 1]]
        kinds = ["" if f in (prior[-1], during[-1]) else cmp.classify(patches, f, prior[-1], during[-1], desktop)
                 for f in distinct]
        odd = next((f for f, k in zip(distinct, kinds) if k), None)
        rows.append(dict(mode=mode, to=after, driven=driven, frames=len(distinct), desktop=kinds.count("desktop"),
                         partial=kinds.count("partial"), odd=str(cmp.describe(patches, odd, prior[-1], during[-1])[:3])
                         if odd else "", grabs=len(recorder.frames), **{"from": before}))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/tab-switch-flash"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--modes", default="office,tabs")
    parser.add_argument("--switches", type=int, default=22)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    os.makedirs(args.out, exist_ok=True)
    patches = sx.Patches(args.display, (0, 0, 1280, 900))
    desktop = patches.grab()  # the empty root window
    config = [(matrix.MISC, "DocumentTabs" + key, "true") for _f, _e, _flt, key in matrix.APPS.values()]
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False,
                            config=config + [("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    results, failed = [], 0

    class Uno:  # what tab_switch_flash_matrix.open_documents expects
        desktop = property(lambda self: office.desktop())
        set_config = staticmethod(office.set_config)
    try:
        for mode in args.modes.split(","):
            folder = os.path.join(args.out, "docs", mode)
            os.makedirs(folder, exist_ok=True)
            if os.geteuid() == 0:  # the office runs as the build user (hst_gui)
                os.chmod(os.path.dirname(folder), 0o777)
                os.chmod(folder, 0o777)
            matrix.open_documents(Uno(), APPS, mode, folder)
            frames = matrix.visible_frames(Uno())
            for frame in frames if mode == "tabs" else frames[:1]:
                frame.getContainerWindow().setPosSize(0, 0, 1280, 900, 15)
                frame.activate()
                frame.getContainerWindow().setFocus()
                time.sleep(1.5)
                results += measure(office, args.display, mode, max(args.switches // len(frames), 4)
                                   if mode == "tabs" else args.switches, desktop, patches)
            matrix.close_all(Uno())
    finally:
        office.stop()
        patches.close()
    for row in results:
        bad = row["desktop"] or row["partial"] or row["driven"].startswith("skipped")
        failed += bool(bad)
        print("%s  %s %s -> %s  %s" % ("FAIL" if bad else "PASS", row["mode"], row["from"], row["to"],
                                       json.dumps({k: row[k] for k in ("frames", "desktop", "partial", "driven", "odd")})))
    with open(os.path.join(args.out, "switches.jsonl"), "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in results)
    print("%d switches, %d failed" % (len(results), failed))
    return 1 if failed or not results else 0


if __name__ == "__main__":
    raise SystemExit(main())
