# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Drive HST Office on macOS in native full screen: a dialog is open and another document opens. Evidence only.

  fsdialog-probe.py <office-pid> <out-dir> <scenario: citation|lo-dialog> <windows-lister> <profile> <inproc.py>

citation: the citation source form for an existing source; a value is typed into "authors" (model), then a new
  document opens: does the form keep the typed value after it moved onto the new document?
lo-dialog: Format > Character (a dialog of the office itself) is open, then a new document opens: is the dialog on
  screen, and does moving its NSWindow under the key window (candidate rescue) bring it back and close cleanly?
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import uno

PORT = 2002
SCRIPT = "vnd.sun.star.script:hstfsprobe.py$%s?language=Python&location=user"


def osa(script, timeout=15):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "osascript timed out"
    return r.returncode, (r.stdout + r.stderr).strip()


class Probe:
    def __init__(self, pid, out, scenario, lister, profile, inproc):
        self.pid, self.out, self.scenario, self.lister, self.profile = pid, out, scenario, lister, profile
        self.events = []
        d = os.path.join(profile, "user", "Scripts", "python")
        os.makedirs(d, exist_ok=True)
        shutil.copy(inproc, os.path.join(d, "hstfsprobe.py"))
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
        factory = self.ctx.getValueByName("/singletons/com.sun.star.script.provider.theMasterScriptProviderFactory")
        self.provider = factory.createScriptProvider("")

    def mark(self, name, **extra):
        self.events.append({"t": int(time.time() * 1000), "event": name, **extra})
        print(json.dumps(self.events[-1], ensure_ascii=False), flush=True)
        with open(f"{self.out}/events-{self.scenario}.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=1, ensure_ascii=False)

    def call(self, name, *args):
        self.provider.getScript(SCRIPT % name).invoke(args, (), ())

    def result(self, name, *args):
        """In-process function that writes a JSON file: its content (or None after 5 s)."""
        path = os.path.join(self.out, "%s-%s-%d.json" % (self.scenario, name, len(self.events)))
        try:
            self.call(name, *(args + (path,)))
        except Exception as error:  # noqa: BLE001
            return {"call-error": repr(error)}
        for _ in range(20):
            time.sleep(0.25)
            if os.path.exists(path):
                time.sleep(0.2)
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        return None

    def cg(self, label):
        rows = subprocess.run([self.lister, str(self.pid)], capture_output=True, text=True, check=False).stdout
        subprocess.run(["screencapture", "-x", f"{self.out}/{self.scenario}-{label}.png"], check=False)
        return [json.loads(r) for r in rows.splitlines() if r.strip()]

    def state(self, label, dialog_title=None):
        """NSWindows and CG windows; the dialog: a titled child window (or the window called dialog_title)."""
        ns = self.result("nswindows") or {}
        windows = ns.get("windows", [])
        cg = self.cg(label)
        children = [w for w in windows if w.get("parent") and w.get("titled")]
        names = {w["title"] for w in children} | ({dialog_title} if dialog_title else set())
        dialog_cg = [w for w in cg if w["name"] in names]
        self.mark("state:" + label, dialogs=children, dialog_onscreen=any(w["onscreen"] for w in dialog_cg),
                  dialog_cg=dialog_cg, windows=windows)
        return any(w["onscreen"] for w in dialog_cg)

    def writer_full_screen(self):
        start = self.desktop.getCurrentFrame() or self.desktop.getFrames().getByIndex(0)
        helper = self.smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)
        helper.executeDispatch(start, "private:factory/swriter", "_self", 0, ())
        time.sleep(5)
        rc, msg = osa('tell application "System Events" to tell (first process whose unix id is %d) '
                      'to set value of attribute "AXFullScreen" of window 1 to true' % self.pid)
        self.mark("enter-fullscreen", rc=rc, msg=msg)
        time.sleep(5)

    def new_document(self):
        self.mark("new-document:start")
        try:
            self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
            self.mark("new-document:loaded")
        except Exception as error:  # noqa: BLE001
            self.mark("new-document:failed", error=repr(error))
        time.sleep(6)

    def typed_after_close(self):
        rc, msg = osa('tell application "System Events" to tell (first process whose unix id is %d)\n'
                      'set frontmost to true\ndelay 0.5\nkeystroke "hstok"\nend tell' % self.pid)
        time.sleep(2)
        texts = {}
        try:
            frames = self.desktop.getFrames()
            for i in range(frames.getCount()):
                f = frames.getByIndex(i)
                model = f.getController().getModel() if f.getController() else None
                if model is not None and hasattr(model, "getText"):
                    texts[f.getTitle()] = model.getText().getString()[:40]
        except Exception as error:  # noqa: BLE001
            texts["error"] = repr(error)
        self.mark("typed-after-close", rc=rc, msg=msg, texts=texts, value=any("hstok" in t for t in texts.values()))


def citation(p):
    p.writer_full_screen()
    p.call("entry_edit")
    time.sleep(5)
    p.mark("typed", **(p.result("set_field", "authors", "Typed Author") or {}))
    before = p.result("read_field", "authors") or {}
    p.mark("field-before-new-document", **before)
    p.state("citation-open", before.get("title"))
    p.new_document()
    after = p.result("read_field", "authors") or {}
    p.mark("field-after-new-document", **after)
    p.mark("citation-kept-typing", value=after.get("value") == "Typed Author", value_now=after.get("value"))
    p.state("citation-after-new-document", before.get("title"))
    osa('tell application "System Events" to key code 53')  # Esc: Cancel
    time.sleep(2)
    p.mark("open-after-esc", **(p.result("read_field", "authors") or {}))
    p.typed_after_close()


def lo_dialog(p, rescue):
    p.writer_full_screen()
    p.mark("watcher", **(p.result("watcher") or {}))
    p.call("trigger", ".uno:FontDialog")
    time.sleep(5)
    p.mark("lo-dialog-on-screen-at-open", value=p.state("lo-open"))
    p.new_document()
    p.mark("lo-dialog-on-screen-after-new-document", value=p.state("lo-after-new-document"))
    if rescue:
        p.mark("reparent", **(p.result("reparent") or {}))
        time.sleep(3)
        p.mark("lo-dialog-on-screen-after-reparent", value=p.state("lo-after-reparent"))
    osa('tell application "System Events" to key code 53')  # Esc: Cancel
    time.sleep(3)
    p.mark("lo-dialog-on-screen-after-esc", value=p.state("lo-after-esc"))
    p.typed_after_close()


def main():
    pid, out, scenario, lister, profile, inproc = sys.argv[1:7]
    rescue = len(sys.argv) > 7 and sys.argv[7] == "rescue"
    stop = threading.Event()

    def dismiss():
        script = ('tell application "System Events" to tell (first process whose unix id is %s)\n'
                  'repeat with w in windows\ntry\n'
                  'if ((name of w) contains "Chào mừng") or ((name of w) contains "chào đón") then '
                  'click (first button of w whose subrole is "AXCloseButton")\n'
                  'end try\nend repeat\nend tell' % pid)
        while not stop.is_set():
            osa(script)
            stop.wait(2)
    threading.Thread(target=dismiss, daemon=True).start()
    p = Probe(int(pid), out, scenario, lister, profile, inproc)
    time.sleep(4)
    stop.set()
    if scenario == "citation":
        citation(p)
    else:
        lo_dialog(p, rescue)


if __name__ == "__main__":
    main()
