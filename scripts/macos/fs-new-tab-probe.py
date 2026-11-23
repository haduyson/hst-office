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


def find_plus_anywhere(path):
    width, height, rows, bpp = TP.png_pixels(path)

    def dark(x, y):
        i = x * bpp
        return (rows[y][i] + rows[y][i + 1] + rows[y][i + 2]) // 3 < 120

    best, xy = 0, (None, None)
    for y in range(60, min(420, height - 7)):
        for x in range(8, width - 8):
            if not dark(x, y):
                continue
            cross = sum(dark(x + d, y) for d in range(-5, 6)) + sum(dark(x, y + d) for d in range(-5, 6))
            if cross < 14:
                continue
            corners = sum(dark(x + dx, y + dy) for dx in (-4, 4) for dy in (-4, 4))
            # the "+" is thin: its row and column neighbours 2 px off the cross are light
            side = sum(dark(x + dx, y + dy) for dx in (-2, 2) for dy in (-2, 2))
            score = cross - 3 * corners - 3 * side
            if score > best:
                best, xy = score, (x, y)
    return xy[0], xy[1], best


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
    x, y, score = find_plus_anywhere(path)
    log("plus", which, x, y, score)
    t = time.time()
    how = "click"
    if x is not None and score >= 14:
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
    # input test: type into whatever has the key focus
    front()
    osa('tell application "System Events" to keystroke "zq7"')
    time.sleep(1.5)
    typed = office.state(f"{which}-after-typing")
    shot(f"{which}-after-typing")
    got = any((f.get("text") or "").find("zq7") >= 0 for f in (typed or {}).get("frames", []))
    ns = (typed or {}).get("ns", {})
    print(f"RESULT {LABEL} {which}: {how}; frames {n0}->{frames_count(after)}; typed reached a document: {got}; "
          f"app key={ns.get('app', {}).get('key')} modal={ns.get('app', {}).get('modal')} "
          f"ax={series}", flush=True)


def main():
    office = Office()
    time.sleep(2)
    if ADOPTER == "off":
        log("adopter", office.call("disable_adopter"))
    office.state("start")
    front()
    osa('tell application "System Events" to keystroke "n" using command down')
    time.sleep(5)
    log("calc", office.call("load", "private:factory/scalc"))
    time.sleep(5)
    st = office.state("writer+calc")
    titles = [f["title"] for f in st.get("frames", [])]
    writer = next((t for t in titles if t and "Không tên 1" in t), titles[0] if titles else "")
    calc = next((t for t in titles if t != writer), "")
    log("writer", writer, "calc", calc)
    if LAYOUT == "both-fs":
        office.call("to_front", calc)
        time.sleep(1)
        fullscreen(calc)
    office.call("to_front", writer)
    time.sleep(2)
    fullscreen(writer)
    shot("writer-fs")
    office.state("writer-fullscreen")
    plus(office, "writer-plus", writer)
    # Sheets: its window to the front (full screen in both-fs), then "+"
    office.call("to_front", calc)
    time.sleep(3)
    if LAYOUT == "writer-fs":
        fullscreen(calc)
    plus(office, "calc-plus", calc)
    office.state("end")
    os._exit(0)


if __name__ == "__main__":
    main()
