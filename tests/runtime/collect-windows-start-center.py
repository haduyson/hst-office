#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: screenshots and accessible boxes of the new Start Center (hst-start-center-redesign.patch), then a verdict.

Collect (console session, under C:\\hst-test\\console-lock.txt, with an environment free of another image's
URE_BOOTSTRAP/UNO_PATH/PYTHON*; the real display scaling set before with tests/runtime/r1auto/scaling.py):
  "<install>\\program\\python.exe" tests/runtime/collect-windows-start-center.py --install DIR --out DIR --label 125
      [--modes native,1366x768] [--themes light,dark]
Per theme (the office's own appearance, set in a fresh profile, the office started again) the five sample documents
of check-start-center-redesign.py are the recent ones, two of them pinned. For each display mode the Start Center
window is maximised, the screen is saved as <out>\\shots\\start-center-<theme>-<label>-<mode>.png and the boxes of its
accessible regions and items (screen pixels) go to <out>\\collected-<label>.json. Checks there: the scaling is the
label, the Start Center is shown, the solutions region holds its six cards and the link to more, every item lies
inside the Start Center (it fits without scrolling; only noted when the window is shorter than the 674 logical px of a
maximised window on a 1366 x 768 screen) and no scroll bar shows. The display mode is put back at the end.

Judge (Linux, with Pillow), for every collected shot: the solutions heading above the first card is one line.
  python3 tests/runtime/collect-windows-start-center.py --judge DIR
"""
import argparse
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

HEADINGS = ("HASON TECH - Giải pháp chuyển đổi số", "HASON TECH - Digital solutions")
CARDS = 7  # the six solution cards and the link to more solutions
FIT_FROM = 674  # logical px: what a maximised window of a 1366 x 768 screen keeps at 100 %


def _const(group, name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.%s.%s" % (group, name))


def make_samples(office, root, samples, prop):
    """The sample documents (stored once, hidden) as [(name, url)]."""
    import uno
    import uno_main_thread_load
    urls = []
    for folder, name, factory, filter_name in samples:
        os.makedirs(os.path.join(root, folder), exist_ok=True)
        path = os.path.join(root, folder, name)
        if not os.path.exists(path):
            doc = uno_main_thread_load.load(office.desktop, "private:factory/" + factory, "_blank", Hidden=True)
            doc.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", filter_name),))
            doc.close(True)
        urls.append((name, uno.systemPathToFileUrl(path)))
    return urls


def start_center_frame(office):
    frames = office.desktop.getFrames()
    for index in range(frames.getCount()):
        frame = frames.getByIndex(index)
        controller = frame.getController()
        if controller is not None and controller.getImplementationName() == "com.sun.star.comp.sfx2.BackingComp":
            return frame
    return None


def accessible_root(window):
    try:
        return window.getAccessibleContext()
    except AttributeError:  # toolkit windows hand their XAccessible out as a property (VCLXWindow)
        return window.getProperty("XAccessible").getAccessibleContext()


def nodes(window):
    """[{role, name, box, depth}] of the showing accessible nodes of the Start Center window."""
    import windows_gui as wg
    roles = {_const("AccessibleRole", name): name for name in
             ("PANEL", "LIST", "LIST_ITEM", "PUSH_BUTTON", "SCROLL_BAR", "TEXT", "LABEL", "FILLER", "ROOT_PANE")}
    found = []
    for context, depth in wg.walk(accessible_root(window), limit=12):
        try:
            if not wg.showing(context):
                continue
            where, size = context.getLocationOnScreen(), context.getSize()
            role = context.getAccessibleRole()
            found.append(dict(role=roles.get(role, str(role)), name=context.getAccessibleName() or "",
                              box=[where.X, where.Y, size.Width, size.Height], depth=depth))
        except Exception:  # noqa: BLE001 - nodes come and go
            continue
    return found


def inside(box, outer, slack=1):
    x, y, w, h = box
    ox, oy, ow, oh = outer
    return x >= ox - slack and y >= oy - slack and x + w <= ox + ow + slack and y + h <= oy + oh + slack


def verdict(case, found, res, scale):
    """The Start Center's own checks on the collected nodes; the cards' boxes for the judge."""
    heading = next((n for n in found if n["role"] == "PANEL" and n["name"] in HEADINGS), None)
    if not res(f"[{case}] solutions region named", heading is not None, sorted({n["name"] for n in found
                                                                                if n["role"] == "PANEL"})):
        return []
    start = found.index(heading)
    end = next((i for i in range(start + 1, len(found)) if found[i]["depth"] <= heading["depth"]), len(found))
    cards = [n for n in found[start + 1:end] if n["role"] == "PUSH_BUTTON" and n["box"][2] > 0]
    canvas = max((n for n in found if n["role"] == "PANEL"), key=lambda n: n["box"][2] * n["box"][3])
    items = [n for n in found if n["role"] in ("PUSH_BUTTON", "LIST_ITEM") and n["box"][2] > 0 and n["box"][3] > 0]
    outside = [(n["name"], n["box"]) for n in items if not inside(n["box"], canvas["box"])]
    checks = [(f"[{case}] solution cards and the link to more", len(cards) == CARDS, [n["name"] for n in cards]),
              (f"[{case}] every item fits in the Start Center (no scrolling)", not outside,
               outside or f"{len(items)} items in {canvas['box']}")]
    for name, ok, detail in checks:
        if canvas["box"][3] * 100 / scale >= FIT_FROM:
            res(name, ok, detail)
        else:  # shorter than a maximised window of a 1366 x 768 screen at 100 %: the left column may scroll
            res.note(name, detail)
    bars = [n["box"] for n in found if n["role"] == "SCROLL_BAR"]
    res(f"[{case}] no scroll bar", not bars, bars)
    return [n["box"] for n in cards]


def collect_theme(theme, args, res, collected, mods):
    import windows_gui as wg
    import windows_display_mode as dm
    redesign = wg.load_check("check-start-center-redesign")
    profile = os.path.join(args.out, f"profile-{args.label}-{theme}")
    office = wg.WinOffice(args.install, profile, args.port, args.out)
    office.start(fresh=True)
    try:
        time.sleep(10)
        wg.dismiss_startup(office, os.path.join(args.out, f"{theme}-{args.label}-startup.png"))
        from com.sun.star.beans import PropertyValue
        provider = office.service("com.sun.star.configuration.ConfigurationProvider")
        access = provider.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess",
            (PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Common/Appearance"),))
        access.setPropertyValue("ApplicationAppearance", {"light": 1, "dark": 2}[theme])
        access.commitChanges()
        samples = make_samples(office, os.path.join(args.out, "samples"), redesign.SAMPLES, redesign.prop)
        redesign.seed_history(office, samples)
        office.stop()
        office.start()  # the appearance and the history apply from the next start
        time.sleep(10)
        wg.dismiss_startup(office, os.path.join(args.out, f"{theme}-{args.label}-restart.png"), timeout=10, settle=2)
        for mode in mods:
            case = f"{theme}-{args.label}-{mode[0]}x{mode[1]}"
            if dm.current() != mode:
                dm.set_mode(*mode)
                time.sleep(3)
            frame = start_center_frame(office)
            if not res(f"[{case}] Start Center shown", frame is not None):
                return
            window = frame.getContainerWindow()
            window.IsMaximized = False
            time.sleep(1)
            window.IsMaximized = True
            time.sleep(4)
            canvas = accessible_root(window)
            where, size = canvas.getLocationOnScreen(), canvas.getSize()
            hwnd = wg.find_window(lambda text: "HST Office" in text, timeout=20)
            if hwnd:
                wg.foreground(hwnd[0])
                # the pointer rests on the window's bottom right corner: no hover state, no tooltip in the shot
                try:
                    wg.mouse_move(where.X + size.Width - 3, where.Y + size.Height - 3)
                except wg.BlockedInput as error:  # the gate found no office window under the point: keep going
                    res.note(f"[{case}] pointer not moved", repr(error))
            time.sleep(1.5)
            shot = os.path.join(args.out, "shots", f"start-center-{case}.png")
            wg.screenshot(shot, cursor=False)
            found = nodes(window)
            cards = verdict(case, found, res, int(args.label))
            collected[case] = dict(shot=os.path.basename(shot), window=[where.X, where.Y, size.Width, size.Height],
                                   cards=cards, nodes=found)
    finally:
        office.stop()


def collect(args):
    import windows_gui as wg
    import windows_display_mode as dm
    from r1auto.scaling import windows_scale
    os.makedirs(os.path.join(args.out, "shots"), exist_ok=True)
    res = wg.Results(args.out, os.path.join(args.out, "profile"))
    scale = windows_scale()
    if not res("display scaling is the label", scale == int(args.label), f"{scale} %"):
        return res.exit_code()
    native = dm.current()
    mods = [native if m == "native" else tuple(int(v) for v in m.split("x")) for m in args.modes.split(",")]
    collected = {"scale": scale, "native": list(native)}
    try:
        for theme in args.themes.split(","):
            try:
                collect_theme(theme, args, res, collected, mods)
            except Exception as error:  # noqa: BLE001 - one theme's failure must not lose the other
                res(f"[{theme}-{args.label}] crashed", False, repr(error))
    finally:
        if dm.current() != native:
            dm.set_mode(*native)
        with open(os.path.join(args.out, f"collected-{args.label}.json"), "w", encoding="utf-8") as handle:
            json.dump(collected, handle, ensure_ascii=False, indent=1)
    return res.exit_code()


def text_lines(image, cards, scale):
    """Heights of the text lines (ink runs at least 5 px high) right above the first solution card: the heading."""
    left = min(c[0] for c in cards)
    right = max(c[0] + c[2] for c in cards)
    top = min(c[1] for c in cards)
    width = right - left
    rows = []
    for y in range(top - 3, max(0, top - int(90 * scale)), -1):
        row = [image.getpixel((x, y)) for x in range(left, right)]
        rows.append((y, row))
    background = max(set(rows[0][1]), key=rows[0][1].count)

    def ink(pixel):
        return sum(abs(a - b) for a, b in zip(pixel[:3], background[:3])) > 120

    runs, height, gap = [], 0, 0
    for _y, row in rows:
        count = sum(1 for pixel in row if ink(pixel))
        if count > 0.9 * width:  # the separator above the heading
            break
        if count:
            height, gap = height + 1, 0
        elif runs and not height and gap > 0.4 * runs[0]:
            break  # past the heading: the lines of a wrapped heading lie closer than this
        else:
            gap += 1
            if height and gap >= 2:
                if height >= 5:  # a diacritic above the line is not a line
                    runs.append(height)
                height = 0
    if height:
        runs.append(height)
    return [run for run in runs if run >= 5]


def judge(out):
    from PIL import Image
    failures = 0
    for name in sorted(os.listdir(out)):
        if not (name.startswith("collected-") and name.endswith(".json")):
            continue
        with open(os.path.join(out, name), encoding="utf-8") as handle:
            collected = json.load(handle)
        scale = collected.get("scale", 100) / 100
        for case, data in collected.items():
            if not isinstance(data, dict) or not data.get("cards"):
                continue
            image = Image.open(os.path.join(out, "shots", data["shot"])).convert("RGB")
            lines = text_lines(image, data["cards"], scale)
            ok = len(lines) == 1
            failures += not ok
            print("%s %s: heading %d line(s) %s" % ("PASS" if ok else "FAIL", case, len(lines), lines))
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge", metavar="DIR", help="judge a collected output directory (Linux, Pillow)")
    parser.add_argument("--install")
    parser.add_argument("--out")
    parser.add_argument("--label", choices=("100", "125", "150"))
    parser.add_argument("--modes", default="native,1366x768")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--port", type=int, default=2397)
    args = parser.parse_args()
    if args.judge:
        return judge(args.judge)
    if not (args.install and args.out and args.label):
        parser.error("--install, --out and --label are required to collect")
    return collect(args)


if __name__ == "__main__":
    sys.exit(main())
