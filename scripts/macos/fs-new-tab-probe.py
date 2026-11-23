# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Native full screen "+" probe (bundled Python, UNO over a pipe):
  fs-new-tab-probe.py <pid> <out> <label> <pipe> <profile> <layout: writer-fs|both-fs> <adopter: on|off>
Writer from the Start Center (Command-N), a Sheets window, native full screen (AXFullScreen), then the tab strip
"+" -> New document (real click; in-process dispatch as fallback), then typing. In-process state dumps
(NSWindows, frames, enabled) at each stage. RESULT lines go to the summary."""
import importlib.util
import json
import os
import subprocess
import sys
import time

import uno

PID, OUT, LABEL, PIPE, PROFILE, LAYOUT, ADOPTER = sys.argv[1:8]
PID = int(PID)
T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("tabprobe", os.path.join(HERE, "tab-probe.py"))
TP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TP)
PROC = f"(first process whose unix id is {PID})"


def log(*a):
    print(f"[{time.time() - T0:7.2f}]", *a, flush=True)


def osa(script, timeout=15):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def shot(name):
    subprocess.run(["screencapture", "-x", f"{OUT}/{LABEL}-{name}.png"], check=False)


def ax_alive():
    t = time.time()
    rc, out = osa(f'tell application "System Events" to get name of windows of {PROC}', 5)
    return rc == 0, round(time.time() - t, 2), out


class Office:
    def __init__(self):
        ctx = uno.getComponentContext()
        res = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
        for _ in range(90):
            try:
                self.ctx = res.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            raise SystemExit("no office")
        d = os.path.join(PROFILE, "user", "Scripts", "python")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(HERE, "fs-new-tab-inproc.py"), encoding="utf-8") as s, \
                open(os.path.join(d, "hstfsprobe.py"), "w", encoding="utf-8") as t:
            t.write(s.read())
        self.factory = self.ctx.getValueByName("/singletons/com.sun.star.script.provider.theMasterScriptProviderFactory")
        self.n = 0

    def call(self, fn, *args, wait=8.0):
        self.n += 1
        path = f"{OUT}/{LABEL}-{self.n:02d}-{fn}.json"
        try:
            script = self.factory.createScriptProvider("").getScript(
                f"vnd.sun.star.script:hstfsprobe.py${fn}?language=Python&location=user")
            script.invoke((path, *args), (), ())
        except Exception as error:  # noqa: BLE001
            log("call failed", fn, repr(error))
            return None
        end = time.time() + wait
        while time.time() < end:
            if os.path.exists(path):
                time.sleep(0.2)
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return data
            time.sleep(0.2)
        if wait > 1:
            log("call timeout (main thread did not run the callback)", fn)
        return {"timeout": fn}

    def state(self, tag):
        data = self.call("state")
        log("STATE", tag, json.dumps(data, ensure_ascii=False))
        return data


def front():
    osa(f'tell application "System Events" to set frontmost of {PROC} to true', 8)
    time.sleep(0.5)


def fullscreen(title):
    rc, out = osa(f'tell application "System Events" to tell {PROC} to set value of attribute "AXFullScreen" of '
                  f'(first window whose name contains "{title}") to true', 20)
    log("fullscreen", title, rc, out)
    time.sleep(5)


def locate_tab_row(path):
    """(plus_x, plus_y, first_tab_x) of the document tab strip: the row (y 60-420) with the most tab close
    glyphs (a small dark "x"), the "+" (a small dark cross) right of its last "x"."""
    width, height, rows, bpp = TP.png_pixels(path)

    def lum(x, y):
        i = x * bpp
        return (rows[y][i] + rows[y][i + 1] + rows[y][i + 2]) // 3

    def dark(x, y):
        return lum(x, y) < 150

    def light(x, y):
        return lum(x, y) > 190

    xs, pluses = {}, {}
    for y in range(64, min(420, height - 6)):
        for x in range(6, width - 6):
            if lum(x, y) >= 110:
                continue
            main = sum(dark(x + d, y + d) or dark(x + d + 1, y + d) for d in range(-3, 4))
            anti = sum(dark(x + d, y - d) or dark(x + d + 1, y - d) for d in range(-3, 4))
            if main >= 6 and anti >= 6 and light(x, y - 3) and light(x, y + 3) and light(x - 3, y) and light(x + 3, y):
                xs.setdefault(y, []).append(x)
            row = sum(dark(x + d, y) for d in range(-4, 5))
            col = sum(dark(x, y + d) for d in range(-4, 5))
            if row >= 8 and col >= 8 and all(light(x + a, y + b) for a in (-3, 3) for b in (-3, 3)):
                pluses.setdefault(y, []).append(x)
    best_y = max(xs, key=lambda y: len(set(v // 20 for v in xs[y])), default=None)
    if best_y is None:
        return None, None, None, {}
    last_x = max(xs[best_y])
    cands = [(abs(y - best_y), x, y) for y, v in pluses.items() if abs(y - best_y) <= 3 for x in v
             if last_x < x < last_x + 80]
    info = {"x_row": best_y, "x_glyphs": sorted(set(xs[best_y])), "plus_cands": sorted(cands)[:5]}
    if not cands:
        return None, None, min(xs[best_y]), info
    _d, px, py = sorted(cands)[0]
    return px, py, min(xs[best_y]), info


def tab_targets(info):
    """Label points of the tabs: the row's glyph list holds each tab's coloured dot and its close "x"; a tab is a
    dot followed 60-130 px later by its "x"; its label starts about 30 px right of the dot."""
    g = sorted(set(info.get("x_glyphs", [])))
    out, i = [], 0
    while i + 1 < len(g):
        if 60 <= g[i + 1] - g[i] <= 130:
            out.append(g[i] + 30)
            i += 2
        else:
            i += 1
    return out


def frames_count(state):
    try:
        return len(state["frames"])
    except Exception:  # noqa: BLE001
        return -1


def plus(office, which, title):
    """The tab strip "+" of the front window, first entry (New ...)."""
    front()
    before = office.state(f"{which}-before-plus")
    n0 = frames_count(before)
    path = f"{OUT}/{LABEL}-{which}-locate.png"
    subprocess.run(["screencapture", "-x", path], check=False)
    x, y, first_x, info = locate_tab_row(path)
    log("plus", which, x, y, info)
    office.call("watch", 20, 1 if ADOPTER == "fixsel" else 0, wait=0.1)  # NSWindow trace, written after 20 s
    t = time.time()
    how = "click"
    if x is not None:
        subprocess.run(["cliclick", f"m:{x},{y}", "w:300", f"c:{x},{y}"], check=False, timeout=20)
        time.sleep(1.2)
        shot(f"{which}-popup")
        osa('tell application "System Events" to key code 125')
        time.sleep(0.3)
        osa('tell application "System Events" to key code 36')
    else:
        how = "no plus found"
    series = []
    after = None
    for k in range(12):
        time.sleep(1)
        alive = ax_alive()
        series.append((round(time.time() - t, 1), alive[0], alive[1]))
        if k in (1, 4, 9):
            after = office.state(f"{which}-after-plus-{k + 1}s")
            shot(f"{which}-after-plus-{k + 1}s")
    if frames_count(after) <= n0:
        how += " -> no new frame, in-process dispatch"
        log("fallback dispatch", office.call("new_tab", title))
        time.sleep(4)
        after = office.state(f"{which}-after-dispatch")
        shot(f"{which}-after-dispatch")
    subprocess.run(["sample", str(PID), "5", "-file", f"{OUT}/{LABEL}-{which}-sample.txt"], check=False,
                   capture_output=True)
    # switch: click the first tab (its label, left of its close glyph), as the owner tried
    # the tab row may have moved (a native tab bar): locate it again on the current screen
    again = f"{OUT}/{LABEL}-{which}-relocate.png"
    subprocess.run(["screencapture", "-x", again], check=False)
    _x2, _y2, _f2, info2 = locate_tab_row(again)
    labels = tab_targets(info2)
    if labels and info2.get("x_row"):
        fx, y = labels[0], info2["x_row"]
        subprocess.run(["cliclick", f"c:{fx},{y}"], check=False, timeout=20)
        time.sleep(2)
        sw = office.state(f"{which}-after-tab-click")
        shot(f"{which}-after-tab-click")
        print(f"RESULT {LABEL} {which}: tab click at {fx},{y}: active frame "
              f"{[f['title'] for f in (sw or {}).get('frames', []) if f.get('active')]}", flush=True)
    # input test: type into whatever has the key focus
    osa('tell application "System Events" to keystroke "zq7"')
    osa('tell application "System Events" to key code 36')
    time.sleep(1.5)
    typed = office.state(f"{which}-after-typing")
    shot(f"{which}-after-typing")
    got = any((f.get("text") or "").lower().find("zq7") >= 0 for f in (typed or {}).get("frames", []))
    ns = (typed or {}).get("ns", {})
    print(f"RESULT {LABEL} {which}: {how}; frames {n0}->{frames_count(after)}; typed reached a document: {got}; "
          f"app key={ns.get('app', {}).get('key')} modal={ns.get('app', {}).get('modal')} "
          f"ax={series}", flush=True)


def switch_probe(office):
    """Windowed: three Writer tabs and a Sheets tab, then real clicks on each tab twice; the NSWindow frame of every
    office window after each click (state dumps) and the on-screen window rects at 50 Hz (sampler, shell)."""
    front()
    for _ in range(3):
        osa('tell application "System Events" to keystroke "n" using command down')
        time.sleep(5)
    log("calc", office.call("load", "private:factory/scalc"))
    time.sleep(6)
    office.state("switch-ready")
    path = f"{OUT}/{LABEL}-switch-locate.png"
    subprocess.run(["screencapture", "-x", path], check=False)
    _x, row_y, _f, info = locate_tab_row(path)
    targets = tab_targets(info)
    log("tab targets", targets, "row", info.get("x_row"), info.get("x_glyphs"))
    with open(f"{OUT}/{LABEL}-switch-marks.txt", "w", encoding="utf-8") as marks:
        for rnd in range(2):
            for i, tx in enumerate(targets):
                marks.write(f"{int(time.time() * 1000)} click tab {i + 1} at {tx},{info.get('x_row')}\n")
                marks.flush()
                subprocess.run(["cliclick", f"c:{tx},{info.get('x_row')}"], check=False, timeout=20)
                time.sleep(1.5)
                st = office.state(f"switch-r{rnd + 1}-tab{i + 1}")
                shot(f"switch-r{rnd + 1}-tab{i + 1}")
                rects = [(w["n"], w["title"][:14], w.get("frame")) for w in (st or {}).get("ns", {}).get("windows", [])
                         if w.get("visible") and w.get("title") and "ImplGetDef" not in w["title"]]
                print(f"RESULT {LABEL} switch r{rnd + 1} tab{i + 1}: visible {rects}", flush=True)


def main():
    office = Office()
    if LAYOUT == "switch":
        time.sleep(2)
        switch_probe(office)
        os._exit(0)
    time.sleep(2)
    if ADOPTER == "off":  # "fixsel": the trace also selects the new native tab (hypothesis check)
        log("adopter", office.call("disable_adopter"))
    office.state("start")
    front()
    osa('tell application "System Events" to keystroke "n" using command down')
    time.sleep(6)
    log("calc", office.call("load", "private:factory/scalc"))
    time.sleep(6)
    office.state("writer+calc")
    shot("two-tabs")
    if LAYOUT == "fullscreen":
        front()
        rc, out = osa(f'tell application "System Events" to tell {PROC} to set value of attribute "AXFullScreen" '
                      f'of window 1 to true', 20)
        log("fullscreen", rc, out)
        time.sleep(6)
    shot("ready")
    office.state("ready")
    plus(office, "plus-1", "")
    plus(office, "plus-2", "")
    if LAYOUT == "fullscreen":
        # Command-W in full screen on an unmodified new tab (no save question), then click the first tab
        log("clean tab", office.call("new_tab", ""))
        time.sleep(4)
        before = office.state("before-cmdw")
        front()
        osa('tell application "System Events" to keystroke "w" using command down')
        time.sleep(4)
        after = office.state("after-cmdw")
        shot("after-cmdw")
        ns = (after or {}).get("ns", {})
        vis = [(w["n"], w["title"][:14], "F" if w["fullscreen"] else "", "S" if w["active_space"] else "o",
                "K" if w["key"] else "", w["tabbed"]) for w in ns.get("windows", [])
               if w.get("visible") and w.get("title") and "ImplGetDef" not in w["title"]]
        print(f"RESULT {LABEL} cmd-w in full screen: frames {frames_count(before)}->{frames_count(after)} "
              f"active {[f['title'] for f in (after or {}).get('frames', []) if f.get('active')]} visible {vis}", flush=True)
        path = f"{OUT}/{LABEL}-cmdw-locate.png"
        subprocess.run(["screencapture", "-x", path], check=False)
        _x, _y, _f, info = locate_tab_row(path)
        labels = tab_targets(info)
        if labels and info.get("x_row"):
            subprocess.run(["cliclick", f"c:{labels[0]},{info['x_row']}"], check=False, timeout=20)
            time.sleep(2)
            st = office.state("after-cmdw-tab-click")
            print(f"RESULT {LABEL} cmd-w then click tab 1: active "
                  f"{[f['title'] for f in (st or {}).get('frames', []) if f.get('active')]}", flush=True)
        # leave native full screen with several tabs, then switch tabs by real clicks
        front()
        rc, out = osa(f'tell application "System Events" to tell {PROC} to set value of attribute "AXFullScreen" '
                      f'of window 1 to false', 20)
        log("leave fullscreen", rc, out)
        time.sleep(6)
        shot("left-fullscreen")
        st = office.state("left-fullscreen")
        vis = [(w["n"], w["title"][:14], "F" if w["fullscreen"] else "", "S" if w["active_space"] else "o", w.get("frame"))
               for w in (st or {}).get("ns", {}).get("windows", []) if w.get("visible") and w.get("title")]
        print(f"RESULT {LABEL} left full screen: visible {vis}", flush=True)
        path = f"{OUT}/{LABEL}-left-locate.png"
        subprocess.run(["screencapture", "-x", path], check=False)
        _x, _y, _f, info = locate_tab_row(path)
        for i, tx in enumerate(tab_targets(info)[:4]):
            subprocess.run(["cliclick", f"c:{tx},{info.get('x_row')}"], check=False, timeout=20)
            time.sleep(1.5)
            st = office.state(f"left-click-tab{i + 1}")
            act = [f["title"] for f in (st or {}).get("frames", []) if f.get("active")]
            vis = [(w["title"][:14], w.get("frame")) for w in (st or {}).get("ns", {}).get("windows", [])
                   if w.get("visible") and w.get("title") and "ImplGetDef" not in w["title"]]
            print(f"RESULT {LABEL} after leaving: click tab {i + 1}: active {act} visible {vis}", flush=True)
    office.state("end")
    os._exit(0)


if __name__ == "__main__":
    main()
