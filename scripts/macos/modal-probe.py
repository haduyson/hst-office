# SPDX-License-Identifier: AGPL-3.0-only
"""Drive HST Office on macOS: from a Sheets tab of the HST Office window run HST > "Văn bản hành chính" (opens a
new Writer tab and the ND 30 wizard) and record whether the modal wizard window is on screen.

  modal-probe.py <office-pid> <out-dir> <mode: windowed|fullscreen> <windows-lister>

Evidence only (events-<mode>.json, windows-*.jsonl, screenshots, sample of the main thread).
"""
import json
import os
import subprocess
import sys
import threading
import time

import uno

PORT = 2002
WIZARD = "Văn bản hành chính"
PROBE_SCRIPT = '''
import uno, unohelper
from com.sun.star.awt import XCallback
class _CB(unohelper.Base, XCallback):
    def __init__(self, ctx, url):
        self.ctx, self.url = ctx, url
    def notify(self, data):
        smgr = self.ctx.ServiceManager
        frame = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx).getCurrentFrame()
        url = uno.createUnoStruct("com.sun.star.util.URL"); url.Complete = self.url
        _, url = smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", self.ctx).parseStrict(url)
        frame.queryDispatch(url, "_self", 0).dispatch(url, ())
def trigger(url):
    ctx = XSCRIPTCONTEXT.getComponentContext()
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(_CB(ctx, url), None)
'''


def osa(script, timeout=15):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "osascript timed out"
    return r.returncode, (r.stdout + r.stderr).strip()


class Probe:
    def __init__(self, pid, out, mode, lister, profile):
        self.pid, self.out, self.mode, self.lister, self.profile = pid, out, mode, lister, profile
        self.events = []
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

    def mark(self, name, **extra):
        self.events.append({"t": int(time.time() * 1000), "event": name, **extra})
        print(json.dumps(self.events[-1], ensure_ascii=False), flush=True)
        with open(f"{self.out}/events-{self.mode}.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=1, ensure_ascii=False)

    def frames(self):
        a = self.desktop.getFrames()
        rows = []
        for i in range(a.getCount()):
            f = a.getByIndex(i)
            w = f.getContainerWindow()
            ps = w.getPosSize()
            rows.append({"title": f.getTitle(), "visible": w.isVisible(), "active": f.isActive(),
                         "pos": [ps.X, ps.Y, ps.Width, ps.Height]})
        return rows

    def top_windows(self):
        tk = self.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        rows = []
        for i in range(tk.getTopWindowCount()):
            w = tk.getTopWindow(i)
            row = {"index": i}
            try:
                ps = w.getPosSize()
                row.update(visible=w.isVisible(), active=w.isActive(), pos=[ps.X, ps.Y, ps.Width, ps.Height])
                row["title"] = w.getTitle() if hasattr(w, "getTitle") else ""
            except Exception as error:  # noqa: BLE001
                row["error"] = repr(error)
            rows.append(row)
        return rows

    def wizard_top_window(self):
        tk = self.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        for i in range(tk.getTopWindowCount()):
            w = tk.getTopWindow(i)
            try:
                if hasattr(w, "getTitle") and w.getTitle() == WIZARD:
                    return w
            except Exception:  # noqa: BLE001
                pass
        return None

    def snapshot(self, label):
        """CG windows of the process (on screen or not), office frames, VCL top windows, a screenshot."""
        rows = subprocess.run([self.lister, str(self.pid)], capture_output=True, text=True, check=False).stdout
        with open(f"{self.out}/windows-{self.mode}-{label}.jsonl", "w", encoding="utf-8") as f:
            f.write(rows)
        cg = [json.loads(r) for r in rows.splitlines() if r.strip()]
        wizard = [w for w in cg if w["name"] == WIZARD]
        subprocess.run(["screencapture", "-x", f"{self.out}/{self.mode}-{label}.png"], check=False)
        try:
            frames, tops = self.frames(), self.top_windows()
        except Exception as error:  # noqa: BLE001
            frames, tops = repr(error), []
        self.mark("snapshot:" + label, wizard_cg=wizard, frames=frames, top_windows=tops,
                  layer0_onscreen=[w for w in cg if w["layer"] == 0 and w["onscreen"] and w["w"] > 150])
        return wizard

    def cg_wizards(self):
        rows = subprocess.run([self.lister, str(self.pid)], capture_output=True, text=True, check=False).stdout
        return [w for w in (json.loads(r) for r in rows.splitlines() if r.strip()) if w["name"] == WIZARD]

    def diag_path(self):
        for root, _dirs, files in os.walk(self.profile):
            for name in files:
                if name.startswith("hst-diag") or name == "hst-office.log":
                    return os.path.join(root, name)
        raise FileNotFoundError("no diagnostics log")

    def trigger_menu(self):
        """The real menu path (MenuBarManager::Select -> AsyncMenuExecute): HST > Văn bản hành chính."""
        script = ('tell application "System Events" to tell (first process whose unix id is %d)\n'
                  'set frontmost to true\n'
                  'delay 0.5\n'
                  'set m to menu 1 of menu bar item "HST" of menu bar 1\n'
                  'click (first menu item of m whose name starts with "%s")\n'
                  'end tell' % (self.pid, WIZARD))
        return osa(script, 20)

    def nswindows(self, label):
        """NSWindows of the office as AppKit sees them (in-process script, main thread): native tab groups, Space."""
        d = os.path.join(self.profile, "user", "Scripts", "python")
        os.makedirs(d, exist_ok=True)
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "modal-probe-nswindows.py"), encoding="utf-8") as src, \
                open(os.path.join(d, "hstnswindows.py"), "w", encoding="utf-8") as dst:
            dst.write(src.read())
        path = os.path.join(self.out, "nswindows-%s-%s.json" % (self.mode, label))
        try:
            factory = self.ctx.getValueByName(
                "/singletons/com.sun.star.script.provider.theMasterScriptProviderFactory")
            script = factory.createScriptProvider("").getScript(
                "vnd.sun.star.script:hstnswindows.py$nswindows?language=Python&location=user")
            script.invoke((path,), (), ())
        except Exception as error:  # noqa: BLE001
            self.mark("nswindows-failed:" + label, error=repr(error))
            return None
        for _ in range(20):
            time.sleep(0.25)
            if os.path.exists(path):
                time.sleep(0.25)
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.mark("nswindows:" + label, **data)
                return data
        self.mark("nswindows-timeout:" + label)
        return None

    def frame_by_title(self, title):
        a = self.desktop.getFrames()
        for i in range(a.getCount()):
            if a.getByIndex(i).getTitle() == title:
                return a.getByIndex(i)
        return None

    def trigger_in_process(self):
        """Fallback: the same dispatch from a main-thread user event (AsyncCallback) inside the office."""
        d = os.path.join(self.profile, "user", "Scripts", "python")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "hstprobe.py"), "w", encoding="utf-8") as f:
            f.write(PROBE_SCRIPT)
        factory = self.ctx.getValueByName("/singletons/com.sun.star.script.provider.theMasterScriptProviderFactory")
        script = factory.createScriptProvider("").getScript(
            "vnd.sun.star.script:hstprobe.py$trigger?language=Python&location=user")
        script.invoke(("org.hst.office.vi:Nd30Wizard",), (), ())


def dismiss_welcome(pid, stop):
    script = ('tell application "System Events" to tell (first process whose unix id is %d)\n'
              'repeat with w in windows\n'
              'try\n'
              'if ((name of w) contains "Chào mừng") or ((name of w) contains "chào đón") then click (first button of w whose subrole is "AXCloseButton")\n'
              'end try\n'
              'end repeat\n'
              'end tell' % pid)
    while not stop.is_set():
        osa(script)
        stop.wait(2)


def main():
    pid, out, mode, lister, profile = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
    stop = threading.Event()
    threading.Thread(target=dismiss_welcome, args=(pid, stop), daemon=True).start()
    p = Probe(pid, out, mode, lister, profile)
    time.sleep(4)
    stop.set()
    # A Sheets document in the HST Office window: the Start Center frame turns into it (the window's first tab).
    start = p.desktop.getCurrentFrame() or p.desktop.getFrames().getByIndex(0)
    helper = p.smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", p.ctx)
    helper.executeDispatch(start, "private:factory/scalc", "_self", 0, ())
    time.sleep(5)
    if mode == "fullscreen":
        rc, msg = osa('tell application "System Events" to tell (first process whose unix id is %d) '
                      'to set value of attribute "AXFullScreen" of window 1 to true' % pid)
        p.mark("enter-fullscreen", rc=rc, msg=msg)
        time.sleep(5)
    p.snapshot("sheets")
    rc, msg = p.trigger_menu()
    p.mark("menu-click", rc=rc, msg=msg)
    shown = []
    for _ in range(40):  # the first Writer document takes a few seconds
        time.sleep(0.5)
        shown = [w for w in p.cg_wizards() if w["onscreen"]]
        if shown:
            break
    if not p.cg_wizards():
        p.mark("menu-click-did-nothing: in-process trigger")
        p.trigger_in_process()
        time.sleep(10)
    p.snapshot("wizard-opened")
    p.nswindows("wizard-opened")
    before = [f["title"] for f in p.frames()]
    owner = next((f["title"] for f in p.frames() if f["active"]), None)
    p.mark("wizard-owner", title=owner)
    # Another tab of the same window while the wizard runs (what "+", File > New, Finder or a launcher do):
    # the tab group parks the Writer tab that owns the modal wizard.
    p.mark("new-tab:start")
    try:
        p.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        p.mark("new-tab:loaded")
    except Exception as error:  # noqa: BLE001
        p.mark("new-tab:failed", error=repr(error))
    time.sleep(5)
    wizard = p.snapshot("after-new-tab")
    p.mark("wizard-on-screen-after-new-tab", value=any(w["onscreen"] for w in wizard), count=len(wizard))
    p.nswindows("after-new-tab")
    new_titles = [f["title"] for f in p.frames() if f["title"] not in before]
    p.mark("new-document", titles=new_titles)
    subprocess.run(["sample", str(pid), "3", "-file", f"{out}/sample-{mode}.txt"], check=False, capture_output=True)
    # Rescue test: bring the VCL dialog to the front over UNO (XTopWindow.toFront = ToTop(RestoreWhenMin)).
    w = p.wizard_top_window()
    if w is not None:
        try:
            w.toFront()
            p.mark("toFront-called")
        except Exception as error:  # noqa: BLE001
            p.mark("toFront-failed", error=repr(error))
        time.sleep(3)
        wizard = p.snapshot("after-toFront")
        p.mark("wizard-on-screen-after-toFront", value=any(x["onscreen"] for x in wizard))
        if not any(x["onscreen"] for x in wizard) and owner:
            # Rescue test 2: the wizard's parent document window to the front (orderFront of its NSWindow).
            try:
                p.frame_by_title(owner).getContainerWindow().toFront()
                p.mark("parent-toFront-called", title=owner)
            except Exception as error:  # noqa: BLE001
                p.mark("parent-toFront-failed", error=repr(error))
            time.sleep(3)
            wizard = p.snapshot("after-parent-toFront")
            p.mark("wizard-on-screen-after-parent-toFront", value=any(x["onscreen"] for x in wizard))
            p.nswindows("after-parent-toFront")
        try:
            w.endExecute()  # XDialog: end the modal loop so the office can quit
            p.mark("endExecute-called")
        except Exception as error:  # noqa: BLE001
            p.mark("endExecute-failed", error=repr(error))
    else:
        p.mark("no-wizard-top-window")
    time.sleep(3)
    p.snapshot("end")
    p.nswindows("end")
    # After the dialog: is the new document on screen, and does typed input reach a document?
    rows = subprocess.run([p.lister, str(pid)], capture_output=True, text=True, check=False).stdout
    cg = [json.loads(r) for r in rows.splitlines() if r.strip()]
    p.mark("new-document-on-screen-after-close",
           value=any(w["name"] in new_titles and w["onscreen"] for w in cg), titles=new_titles)
    rc, msg = osa('tell application "System Events" to tell (first process whose unix id is %d)\n'
                  'set frontmost to true\ndelay 0.5\nkeystroke "hstok"\nend tell' % pid)
    time.sleep(2)
    typed = {}
    try:
        a = p.desktop.getFrames()
        for i in range(a.getCount()):
            f = a.getByIndex(i)
            model = f.getController().getModel() if f.getController() else None
            if model is not None and hasattr(model, "getText"):
                typed[f.getTitle()] = model.getText().getString()[:40]
    except Exception as error:  # noqa: BLE001
        typed["error"] = repr(error)
    p.mark("typed-after-close", rc=rc, msg=msg, texts=typed,
           value=any("hstok" in t for t in typed.values()))
    try:
        p.mark("diag-tail", lines=open(p.diag_path(), encoding="utf-8").read().splitlines()[-15:])
    except Exception as error:  # noqa: BLE001
        p.mark("diag-tail-failed", error=repr(error))

if __name__ == "__main__":
    main()
