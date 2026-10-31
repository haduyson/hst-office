# SPDX-License-Identifier: AGPL-3.0-only
"""Drive HST Office on macOS over UNO and time document-tab actions (run with the bundled Python).

  tab-probe.py <office-pid> <out-dir> <mode: windowed|fullscreen>

Events are appended to <out-dir>/events-<mode>.csv as `t_ms,event` using the same clock origin the
sampler uses (epoch ms in column 0 is added by the shell wrapper: this file writes absolute epoch ms).
Each action is timed from the call until the new top-level window is on screen and the app is frontmost.
"""
import json
import subprocess
import sys
import threading
import time

import uno
from com.sun.star.beans import PropertyValue

PORT = 2002


def now_ms():
    return int(time.time() * 1000)


def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        return 124, "osascript timed out (automation permission prompt?)"
    return r.returncode, (r.stdout + r.stderr).strip()


def front_pid():
    rc, out = osa('tell application "System Events" to unix id of first process whose frontmost is true')
    return int(out) if rc == 0 and out.isdigit() else -1


class Probe:
    def __init__(self, pid, out, mode):
        self.pid, self.mode, self.events, self.out = pid, mode, [], out
        ctx = uno.getComponentContext()
        resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
        for _ in range(120):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            raise SystemExit("cannot connect to soffice")
        self.smgr = self.ctx.ServiceManager
        self.desktop = self.smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        self.helper = self.smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)

    def mark(self, name, **extra):
        self.events.append({"t": now_ms(), "event": name, **extra})
        print(self.events[-1], flush=True)
        self.save()

    def frames(self):
        a = self.desktop.getFrames()
        return [a.getByIndex(i) for i in range(a.getCount())]

    def shown(self):
        return [f for f in self.frames() if f.getContainerWindow().isVisible()]

    def dispatch(self, cmd, target="_self"):
        frame = self.desktop.getCurrentFrame() or (self.shown() or self.frames())[0]
        self.helper.executeDispatch(frame, cmd, target, 0, ())

    def timed(self, label, action, settle=0.0):
        """Run action, then wait until a visible frame is active and the app is frontmost."""
        self.mark(label + ":start")
        t0 = time.time()
        action()
        call = time.time() - t0
        usable = None
        while time.time() - t0 < 30:
            try:
                f = self.shown()
                if f and f[0].isActive() and front_pid() == self.pid:
                    usable = time.time() - t0
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.02)
        self.mark(label + ":end", call=round(call, 3), usable=None if usable is None else round(usable, 3),
                  frontmost=front_pid() == self.pid)
        time.sleep(settle)

    def load(self, url, target="_blank"):
        return self.desktop.loadComponentFromURL(url, target, 0, ())

    def save(self):
        with open(f"{self.out}/events-{self.mode}.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=1)


def dismiss_welcome(pid):
    """The welcome dialog opens modally with the first window and blocks UNO: close it when seen."""
    script = ('tell application "System Events" to tell (first process whose unix id is %d)\n'
              'repeat with w in windows\n'
              'try\n'
              'if (name of w) contains "Chào mừng" then click (first button of w whose subrole is "AXCloseButton")\n'
              'end try\n'
              'end repeat\n'
              'end tell' % pid)
    while True:
        osa(script)
        time.sleep(2)


def main():
    pid, out, mode = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    threading.Thread(target=dismiss_welcome, args=(pid,), daemon=True).start()
    p = Probe(pid, out, mode)
    time.sleep(3)
    p.timed("first-writer", lambda: p.load("private:factory/swriter", "_default"), 1)
    p.timed("plus-new-writer", lambda: p.load("private:factory/swriter"), 1)  # what the "+" menu dispatches
    p.timed("new-calc", lambda: p.load("private:factory/scalc"), 1)
    p.timed("new-impress", lambda: p.load("private:factory/simpress"), 1)
    sample = f"{out}/sample.odt"
    doc = p.load("private:factory/swriter", "_blank")
    doc.getText().setString("probe")
    doc.storeToURL("file://" + sample, ())
    doc.close(True)
    p.timed("open-file", lambda: p.load("file://" + sample), 1)
    if mode == "fullscreen":
        rc, msg = osa('tell application "System Events" to tell (first process whose unix id is %d) '
                      'to set value of attribute "AXFullScreen" of window 1 to true' % pid)
        p.mark("enter-fullscreen", rc=rc, msg=msg)
        time.sleep(4)
    for i in range(6):
        p.timed(f"switch-{i + 1}", lambda: p.dispatch(".uno:NextDocumentTab"), 1.5)
    if mode == "fullscreen":
        p.timed("plus-new-writer-fullscreen", lambda: p.load("private:factory/swriter"), 3)
        # Leave native full screen with several tabs open (green button / Ctrl+Cmd+F do the same).
        setfs = ('tell application "System Events" to tell (first process whose unix id is %d) '
                 'to set value of attribute "AXFullScreen" of window 1 to %s')
        p.timed("exit-fullscreen", lambda: p.mark("exit-rc", rc=osa(setfs % (pid, "false"))[0]), 4)
        p.timed("switch-after-exit-1", lambda: p.dispatch(".uno:NextDocumentTab"), 1.5)
        p.timed("switch-after-exit-2", lambda: p.dispatch(".uno:NextDocumentTab"), 1.5)
        p.mark("reenter-rc", rc=osa(setfs % (pid, "true"))[0])
        time.sleep(4)
    # Close the shown tab twice: once by the command, once by Cmd+W like the owner.
    p.timed("close-command", lambda: p.dispatch(".uno:CloseWin"), 2)
    p.mark("cmdw:start")
    osa('tell application "System Events" to keystroke "w" using command down')
    time.sleep(3)
    p.mark("cmdw:end", frontmost=front_pid() == pid, frames=len(p.frames()))
    p.save()
    # discard the remaining documents so soffice can be terminated without prompts
    for c in list(p.desktop.getComponents()):
        try:
            c.setModified(False)
        except Exception:  # noqa: BLE001
            pass
    try:
        p.desktop.terminate()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
