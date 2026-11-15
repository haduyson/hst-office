# SPDX-License-Identifier: AGPL-3.0-only
"""Freeze probe, scroll/typing latency and AutoRecovery freeze for large_file_open_client.py (office Python, uno).

Probe: a thread calls getPosSize() on a hidden window of its own every 0.1 s. That call needs the office's main lock
(SolarMutex), which the main loop holds while it works without dispatching input, so the wait of one call is how long
the user interface was frozen at that moment (Windows shows "Not responding" after 5 s of it).
interact(): real key events (XToolkitRobot, as the keyboard would post them) to the document window: Page Down and
Page Up 8 times in turn, and 8 typed characters (Sheets: a digit and Enter); each latency is the time until the
document's view changed.
autosave(): with the "autosave" profile seed (AutoRecovery every minute, large documents too), waits for the timer's
backup in <profile>/user/backup and reports how long it took and the longest freeze around it.
"""
import os
import subprocess
import sys
import threading
import time


class Probe:
    def __init__(self, smgr, ctx):
        import uno
        self.waits, self.stop = [], threading.Event()  # (monotonic start, wait seconds)
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        desc = uno.createUnoStruct("com.sun.star.awt.WindowDescriptor")
        desc.Type = uno.Enum("com.sun.star.awt.WindowClass", "TOP")
        desc.WindowServiceName = "window"
        desc.Bounds = uno.createUnoStruct("com.sun.star.awt.Rectangle", 0, 0, 10, 10)
        self.created = time.monotonic()
        self.window = toolkit.createWindow(desc)  # needs the main lock too: the office may be busy already
        self.waits.append((self.created, time.monotonic() - self.created))
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            t = time.monotonic()
            try:
                self.window.getPosSize()
            except Exception:  # noqa: BLE001 - the office is going away
                return
            self.waits.append((t, time.monotonic() - t))
            time.sleep(0.1)

    def longest(self, t0, t1=None):
        """Longest single freeze that started between t0 and t1 (a call still waiting counts until now)."""
        t1 = t1 or time.monotonic()
        done = [w for s, w in self.waits if t0 <= s <= t1]
        return round(max(done or [0.0]), 2)

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=5)
        try:
            self.window.dispose()
        except Exception:  # noqa: BLE001
            pass


KEY_TARGET = [None]  # the frame's container window: the X window that takes real key events
XKEYS = {"PAGEDOWN": "Next", "PAGEUP": "Prior", "A": "a", "NUM7": "7", "RETURN": "Return"}


def key(robot, window, code_name, char=""):
    """A key press: posted to the window (XToolkitRobot), or with LFO_REAL_KEYS=1 on X11 a real X input event
    (xdotool, XTEST) that the office sees as pending input, as the background layout checks for it."""
    import uno
    if os.environ.get("LFO_REAL_KEYS") == "1" and sys.platform.startswith("linux"):
        from com.sun.star.lang.SystemDependent import SYSTEM_XWINDOW
        xid = KEY_TARGET[0].getWindowHandle(tuple([0] * 16), SYSTEM_XWINDOW).WindowHandle
        subprocess.run(["xdotool", "windowfocus", str(xid), "key", XKEYS[code_name]], check=False, timeout=30)
        return
    ev = uno.createUnoStruct("com.sun.star.awt.KeyEvent")
    ev.Source, ev.KeyCode, ev.Modifiers = window, uno.getConstantByName("com.sun.star.awt.Key." + code_name), 0
    ev.KeyChar = uno.Char(char or "\x00")
    robot.keyPress(ev)
    robot.keyRelease(ev)


def view_state(doc, ctrl):
    """Something visible that changes with every Page Down or typed character, per application."""
    if doc.supportsService("com.sun.star.text.TextDocument"):
        vc = ctrl.getViewCursor()
        pos = vc.getPosition()
        return (vc.getPage(), pos.X, pos.Y)
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        a = ctrl.getSelection().getRangeAddress()
        return (a.Sheet, a.StartRow, a.StartColumn)
    return (ctrl.getCurrentPage().Number,)


def latency(doc, ctrl, press, timeout=30.0):
    before = view_state(doc, ctrl)
    t = time.monotonic()
    press()
    while time.monotonic() - t < timeout:
        if view_state(doc, ctrl) != before:
            return time.monotonic() - t
        time.sleep(0.02)
    return None


def series(doc, ctrl, window, presses, n=8):
    """n latencies, cycling through presses (Page Down / Page Up keep moving whatever the length of the document). A key
    that changed nothing within 30 s is tried once more after focusing the window again (the first start may drop it);
    a second miss ends the series (the office is stuck)."""
    out, retried = [], False
    for i in range(n):
        w = latency(doc, ctrl, presses[i % len(presses)])
        if w is None and not retried:
            retried = True
            window.setFocus()
            time.sleep(1.0)
            w = latency(doc, ctrl, presses[i % len(presses)])
        if w is None:
            out.append(30.0)
            break
        out.append(w)
    return out


def summary(name, waits):
    waits = sorted(waits)
    return {name + "_median": round(waits[len(waits) // 2], 3), name + "_max": round(waits[-1], 3)} if waits else {}


def interact(smgr, ctx, doc, prefix=""):
    robot = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    ctrl = doc.getCurrentController()
    window = ctrl.getFrame().getComponentWindow()
    KEY_TARGET[0] = ctrl.getFrame().getContainerWindow()
    window.setFocus()
    time.sleep(1.0)  # the frame takes the focus asynchronously after it is shown; keys before that are dropped
    res = summary(prefix + "scroll", series(doc, ctrl, window, [lambda: key(robot, window, "PAGEDOWN"),
                                                        lambda: key(robot, window, "PAGEUP")]))
    if doc.supportsService("com.sun.star.text.TextDocument"):
        res.update(summary(prefix + "typing", series(doc, ctrl, window, [lambda: key(robot, window, "A", "a")])))
    elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        def entry():
            key(robot, window, "NUM7", "7")
            key(robot, window, "RETURN")
        res.update(summary(prefix + "typing", series(doc, ctrl, window, [entry])))
    return res


def autosave(doc, probe, timeout=240.0):
    """The AutoRecovery timer's own save of the (modified) document: seconds from the first byte of its backup in
    <profile>/user/backup until the backup stopped growing, and the longest freeze from the modification until then."""
    backup = os.path.join(os.environ.get("LFO_PROFILE", ""), "user", "backup")
    doc.setModified(True)
    t0, wall0, first, last_size, stable = time.monotonic(), time.time() - 1, None, -1, 0
    while time.monotonic() - t0 < timeout:
        files = [os.path.join(backup, n) for n in os.listdir(backup)] if os.path.isdir(backup) else []
        def stat(f):  # AutoRecovery writes through temporary files that may vanish meanwhile
            try:
                return os.stat(f)
            except OSError:
                return None
        stats = [(f, stat(f)) for f in files]
        files = [f for f, st in stats if st and st.st_mtime >= wall0]
        size = sum(st.st_size for f, st in stats if st and st.st_mtime >= wall0)
        if size > 4096 and first is None:
            first = time.monotonic()
        stable = stable + 1 if first and size == last_size else 0
        last_size = size
        if stable >= 6:  # 3 s without growth: written
            return {"autosave_s": round(time.monotonic() - 3 - first, 1), "autosave_mb": round(size / 1e6, 1),
                    "autosave_files": sorted(os.path.basename(f) for f in files)[:3],
                    "autosave_freeze": probe.longest(t0)}
        time.sleep(0.5)
    return {"autosave_s": None, "autosave_freeze": probe.longest(t0)}
