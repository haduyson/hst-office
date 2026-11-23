# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Drive "open another tab" in HST Office on macOS with real input and time it (bundled Python).

  new-tab-hang-probe.py <pid> <out-dir> <scenario: writer|calc-from-start-center> <pipe-name> <app>

Input goes through System Events (keystrokes, menu bar clicks) and cliclick (the tab strip "+"), so the
office handles it on its main thread like a user's action. UNO is only read (frame count, titles) from a
poller thread, never waited on by the steps. A step is done when the frame count reached its target and
the app answers an accessibility query; after 5 s it is sampled with `sample <pid> 10`. Lines starting
with RESULT go to the summary.
"""
import os
import subprocess
import sys
import threading
import time

import uno

PID, OUT, SCENARIO, PIPE, APP = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
T0 = time.time()


def log(*args):
    print(f"[{time.time() - T0:7.2f}]", *args, flush=True)


def run(cmd, timeout):
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip(), time.time() - t
    except subprocess.TimeoutExpired:
        return 124, "timeout", time.time() - t


def osa(script, timeout=15):
    return run(["osascript", "-e", script], timeout)


PROC = f'(first process whose unix id is {PID})'


def ax_alive(timeout=4.0):
    """The office's main thread answers accessibility queries only while it runs its event loop."""
    rc, out, took = osa(f'tell application "System Events" to get name of windows of {PROC}', timeout)
    return rc == 0, took, out


def front():
    osa(f'tell application "System Events" to set frontmost of {PROC} to true', 8)
    time.sleep(0.6)


def shot(name):
    subprocess.run(["screencapture", "-x", f"{OUT}/{SCENARIO}-{name}.png"], check=False)


class Poller(threading.Thread):
    """Reads the desktop's frames over UNO; a call that blocks only delays this thread."""

    def __init__(self):
        super().__init__(daemon=True)
        ctx = uno.getComponentContext()
        resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
        for _ in range(90):
            try:
                self.ctx = resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            raise SystemExit("cannot connect to soffice")
        self.desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        self.count, self.titles, self.stamp = -1, [], 0.0

    def read(self):
        frames = self.desktop.getFrames()
        titles = []
        for i in range(frames.getCount()):
            f = frames.getByIndex(i)
            c = f.getController()
            model = c.getModel() if c is not None else None
            kind = "start" if model is None else model.getIdentifier()
            titles.append(f"{f.getTitle()}|{kind}|{'v' if f.getContainerWindow().isVisible() else 'h'}")
        return frames.getCount(), titles

    def run(self):
        while True:
            try:
                self.count, self.titles = self.read()
                self.stamp = time.time()
            except Exception as error:  # noqa: BLE001
                log("poll error", repr(error))
            time.sleep(0.25)


def plus_point(name):
    """Centre of the tab strip "+" of the front window (dark cross on a light box), from a screenshot."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("tabprobe", os.path.join(os.path.dirname(__file__), "tab-probe.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    path = f"{OUT}/{SCENARIO}-{name}-locate.png"
    subprocess.run(["screencapture", "-x", path], check=False)
    rc, out, _ = osa(f'tell application "System Events" to get {{position, size}} of window 1 of {PROC}', 8)
    log("front window geometry", out)
    nums = [int(float(x)) for x in out.replace(" ", "").split(",")] if rc == 0 else [0, 25, 1024, 700]
    wx, wy = nums[0], nums[1]
    # strip sits under the title bar; search from the window's left edge
    x, y, score = mod.find_plus(path, wx + 140, lo=wy + 20, hi=wy + 90)
    return x, y, score


def step(poller, label, action, target, limit=150):
    """Run action, then wait until frames >= target and the app answers accessibility again."""
    shot(f"{label}-before")
    before = poller.count
    log(f"step {label}: start frames={before} target={'document replaces Start Center' if callable(target) else target}")
    t = time.time()
    action()
    sampled = None
    ax_series = []
    done = None
    while time.time() - t < limit:
        alive, took, _ = ax_alive(4.0)
        ax_series.append((round(time.time() - t, 1), alive, round(took, 2)))
        fresh = poller.stamp > t
        reached = target(poller) if callable(target) else poller.count >= target
        if fresh and reached and alive:
            done = time.time() - t
            break
        if sampled is None and time.time() - t > 5:
            sampled = f"{OUT}/{SCENARIO}-{label}-sample.txt"
            shot(f"{label}-stuck")
            subprocess.Popen(["sample", str(PID), "10", "-file", sampled],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
    shot(f"{label}-after")
    slow_ax = [s for s in ax_series if not s[1] or s[2] > 1.0]
    log(f"step {label}: done={None if done is None else round(done, 2)} frames={poller.count} "
        f"titles={poller.titles} unresponsive={slow_ax[:40]}")
    verdict = "OK" if done is not None and done < 5 else "SLOW" if done is not None else "HANG"
    print(f"RESULT {SCENARIO} {label}: {verdict} "
          f"{'%.1f s' % done if done is not None else f'>{limit} s'} frames {before}->{poller.count}"
          f"{' (sampled)' if sampled else ''}", flush=True)
    time.sleep(2)
    return done


def key_cmd(ch):
    return lambda: (front(), osa(f'tell application "System Events" to keystroke "{ch}" using command down'))


def menu_new(index):
    """File > New > item <index> (1 Text Document, 2 Spreadsheet) of the native menu bar."""
    def act():
        front()
        rc, out, took = osa(f'tell application "System Events" to tell {PROC} to click menu item {index} of menu 1 '
                            f'of menu item 1 of menu 1 of menu bar item 2 of menu bar 1', 30)
        log("menu click", rc, out, round(took, 2))
    return act


def plus_new(name):
    """Click the tab strip "+", then take the first entry (New <this app's> document) with Down, Return."""
    def act():
        front()
        x, y, score = plus_point(name)
        log("plus at", x, y, score)
        if x is None:
            return
        subprocess.run(["cliclick", f"m:{x},{y}", "w:300", f"c:{x},{y}"], check=False, timeout=20)
        time.sleep(1.0)
        shot(f"{name}-popup")
        osa('tell application "System Events" to key code 125')
        time.sleep(0.3)
        osa('tell application "System Events" to key code 36')
    return act


def open_file(path):
    return lambda: run(["open", "-a", APP, path], 30)


def make_files(poller):
    """Test documents of our own, made headlessly over UNO before the GUI steps (hidden frames)."""
    from com.sun.star.beans import PropertyValue
    hidden = PropertyValue()
    hidden.Name, hidden.Value = "Hidden", True
    files = {}
    for kind, factory, ext in (("odt", "swriter", "odt"), ("ods", "scalc", "ods")):
        doc = poller.desktop.loadComponentFromURL(f"private:factory/{factory}", "_blank", 0, (hidden,))
        if ext == "odt":
            doc.getText().setString("Tài liệu thử mở thêm tab")
        else:
            doc.getSheets().getByIndex(0).getCellByPosition(0, 0).setString("thử")
        path = f"{OUT}/probe-{SCENARIO}.{ext}"
        doc.storeToURL("file://" + path, ())
        doc.close(True)
        files[kind] = path
    return files


def no_start(poller):
    return poller.count >= 1 and not any("|start|" in t for t in poller.titles)


def main():
    poller = Poller()
    poller.start()
    time.sleep(2)
    log("frames at start", poller.count, poller.titles)
    rc, out, _ = osa(f'tell application "System Events" to get name of every menu item of menu 1 of menu item 1 '
                     f'of menu 1 of menu bar item 2 of menu bar 1 of {PROC}', 20)
    log("File > New menu:", rc, out)
    files = make_files(poller)
    time.sleep(1.5)
    log("frames after files", poller.count, poller.titles)
    n = poller.count  # the Start Center frame
    if SCENARIO == "writer":
        step(poller, "w1-cmdn-on-start-center", key_cmd("n"), no_start)  # replaces the Start Center
        time.sleep(3)
        n = poller.count
        step(poller, "w2-cmdn-second-writer", key_cmd("n"), n + 1)
        step(poller, "w3-cmdn-third-writer", key_cmd("n"), n + 2)
        step(poller, "w4-file-new-text", menu_new(1), n + 3)
        step(poller, "w5-plus-new-writer", plus_new("w5"), n + 4)
        step(poller, "w6-open-odt", open_file(files["odt"]), n + 5)
        m = poller.count
        step(poller, "c1-file-new-spreadsheet-from-writer", menu_new(2), m + 1)
        step(poller, "c2-cmdn-second-calc", key_cmd("n"), m + 2)
        step(poller, "c3-cmdn-third-calc", key_cmd("n"), m + 3)
        step(poller, "c4-plus-new-calc", plus_new("c4"), m + 4)
        step(poller, "c5-open-ods", open_file(files["ods"]), m + 5)
    else:
        step(poller, "s1-file-new-spreadsheet-on-start-center", menu_new(2), no_start)
        time.sleep(3)
        n = poller.count
        step(poller, "s2-cmdn-second-calc", key_cmd("n"), n + 1)
        step(poller, "s3-cmdn-third-calc", key_cmd("n"), n + 2)
        step(poller, "s4-plus-new-calc", plus_new("s4"), n + 3)
        step(poller, "s5-file-new-text-from-calc", menu_new(1), n + 4)
        step(poller, "s6-cmdn-writer-after-calc", key_cmd("n"), n + 5)
    log("end frames", poller.count, poller.titles)
    os._exit(0)


if __name__ == "__main__":
    main()
