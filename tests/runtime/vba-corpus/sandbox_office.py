# SPDX-License-Identifier: AGPL-3.0-only
"""Inside the disposable container: Xvfb, one HST office over a pipe, and a watcher for modal dialogs.

The office uses the gen VCL plugin, whose message boxes are real VCL dialogs that the UNO toolkit can
read and close: MsgBox and InputBox text is recorded and the default button pressed, so nothing hangs.
"""
import json
import os
import shutil
import signal
import subprocess
import threading
import time

OPT = "/opt/hst/program"
PROFILE = "/tmp/profile"
PIPE = "hstvba"
PREFERRED_BUTTONS = ("ok", "yes", "close")  # UITest widget ids of the default answer


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


def hierarchy_texts(node, out):
    """Texts of a UITest window hierarchy (JSON tree of widgets)."""
    for key in ("DisplayText", "Text", "Label", "PrimaryMessage", "SecondaryMessage"):
        value = node.get(key)
        if value and value not in out:
            out.append(value)
    for child in node.get("children", []):
        hierarchy_texts(child, out)


class Watcher(threading.Thread):
    """Records and answers every dialog that opens while a macro runs."""

    def __init__(self, toolkit, ui):
        super().__init__(daemon=True)
        self.toolkit, self.ui, self.seen, self.stopped = toolkit, ui, [], False
        self.grace = 0.2  # seconds a dialog stays open before it is answered

    def run(self):
        while not self.stopped:
            try:
                for index in range(self.toolkit.getTopWindowCount()):
                    window = self.toolkit.getTopWindow(index)
                    if hasattr(window, "endDialog") and window.isVisible():
                        self.answer(window)
            except Exception:  # noqa: BLE001 - windows vanish, the office may be going down
                pass
            time.sleep(0.15)

    def answer(self, window):
        time.sleep(self.grace)
        top = self.ui.getTopFocusWindow()
        texts, buttons = [], []
        try:
            hierarchy_texts(json.loads(top.getHierarchy(), strict=False), texts)
            buttons = list(top.getChildren())
        except Exception:  # noqa: BLE001 - a malformed tree only loses the text
            pass
        self.seen.append({"title": window.getTitle(), "text": [t[:400] for t in texts[:12]], "buttons": buttons[:12]})
        for button in PREFERRED_BUTTONS:
            if button in buttons:
                top.getChild(button).executeAction("CLICK", ())
                time.sleep(0.1)
                if not window.isVisible():
                    return
        window.endDialog(0)

    def take(self):
        seen, self.seen = self.seen, []
        return seen


class Office:
    def __init__(self):
        self.proc = self.xvfb = self.watcher = self.desktop = None
        self.env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
        self.env.update(HOME="/tmp/home", LANG="C.UTF-8", LC_ALL="C.UTF-8", DISPLAY=":77", SAL_USE_VCLPLUGIN="gen",
                        SAL_LOG="-", TMPDIR="/tmp/work")
        os.makedirs("/tmp/home", exist_ok=True)
        os.makedirs("/tmp/work", exist_ok=True)

    def start(self):
        if self.xvfb is None or self.xvfb.poll() is not None:
            self.xvfb = subprocess.Popen(["Xvfb", ":77", "-screen", "0", "1400x900x24", "-nolisten", "tcp"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        args = [f"-env:UserInstallation=file://{PROFILE}", "--norestore", "--nologo"]
        if not os.path.exists(os.path.join(PROFILE, "user")):
            for _ in range(3):  # exit 81 = restart requested while the fresh profile is created
                done = subprocess.run([f"{OPT}/soffice.bin", "--terminate_after_init"] + args, env=self.env, timeout=180,
                                      check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if done.returncode == 0:
                    break
        self.launch(args)
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        deadline = time.time() + 90
        while True:
            try:
                self.ctx = resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - not listening yet
                if self.proc.poll() == 81:  # the office asks for a restart right after a fresh profile
                    self.launch(args)
                elif time.time() > deadline or self.proc.poll() is not None:
                    raise RuntimeError(f"office did not start, exit {self.proc.poll()}")
                time.sleep(0.5)
        smgr = self.ctx.ServiceManager
        self.desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        self.watcher = Watcher(smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx),
                               smgr.createInstanceWithContext("org.libreoffice.uitest.UITest", self.ctx))
        self.watcher.start()

    def launch(self, args):
        self.proc = subprocess.Popen([f"{OPT}/soffice.bin"] + args + [f"--accept=pipe,name={PIPE};urp;"], env=self.env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def kill(self):
        if self.watcher:
            self.watcher.stopped = True
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)
        shutil.rmtree("/tmp/work", ignore_errors=True)
        os.makedirs("/tmp/work", exist_ok=True)

    def restart(self):
        self.kill()
        self.start()

    def shutdown(self):
        self.kill()
        if self.xvfb:
            self.xvfb.terminate()


def call_with_timeout(func, timeout):
    """(state, value): state is done, raised or timeout. func runs on a thread: UNO calls cannot be interrupted."""
    box = {}

    def work():
        try:
            box["value"] = func()
        except BaseException as error:  # noqa: BLE001 - reported to the caller
            box["error"] = error

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return "timeout", None
    if "error" in box:
        return "raised", box["error"]
    return "done", box.get("value")
