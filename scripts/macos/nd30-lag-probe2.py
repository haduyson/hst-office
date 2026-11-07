# SPDX-License-Identifier: AGPL-3.0-only
"""Control experiment for lost Tab keys on macOS: count Tab key presses that reach the office (toolkit key handler)
and that move the focus, in a Writer document, a plain UNO dialog, the ND30 wizard (in the office and over the bridge),
with keys from cliclick and from System Events.   nd30-lag-probe2.py <pid> <out-dir> <ext-python-dir>"""
import json, os, subprocess, sys, threading, time
import uno, unohelper
from com.sun.star.awt import XKeyHandler

KEYS = []


class Keys(unohelper.Base, XKeyHandler):
    def keyPressed(self, e):
        KEYS.append((time.perf_counter(), e.KeyCode))
        return False

    def keyReleased(self, e):
        return False

    def disposing(self, e):
        pass


def cli(*a):
    subprocess.run(["cliclick", "-w", "5", *a], check=False, timeout=60)


def osa_tab():
    subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 48'], check=False, timeout=20)


def main():
    pid, out, extpy = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    sys.path.insert(0, extpy)
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            remote = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    smgr = remote.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", remote)
    helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", remote)
    tk = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", remote)
    tk.addKeyHandler(Keys())
    front = f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true'
    result = {}

    def tabs(name, peers, send, count=20):
        """send `count` Tabs; per Tab: delivered (key handler saw it within 3 s), ms, which peer has the focus after."""
        rows = []
        for _ in range(count):
            n, t0 = len(KEYS), time.perf_counter()
            send()
            while len(KEYS) <= n and time.perf_counter() - t0 < 3:
                time.sleep(0.0005)
            delivered = len(KEYS) > n
            if peers:
                peers[0].getPosSize()
            ms = round((time.perf_counter() - t0) * 1000, 1)
            focus = next((i for i, p in enumerate(peers) if p.hasFocus()), -1)
            rows.append([int(delivered), ms, focus])
        lost = sum(1 for r in rows if not r[0])
        result[name] = {"lost": lost, "of": count, "rows": rows}
        print(name, "lost", lost, "of", count, [r[1] for r in rows], [r[2] for r in rows], flush=True)
        subprocess.run(["screencapture", "-x", os.path.join(out, f"probe2-{name}.png")], check=False)

    # W: Writer document
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    time.sleep(3)
    subprocess.run(["osascript", "-e", front], check=False)
    time.sleep(1)
    tabs("writer-cliclick", [], lambda: cli("kp:tab"))
    doc.close(True)

    def wait_dialog(title):
        for _ in range(150):
            time.sleep(0.2)
            top = tk.getActiveTopWindow()
            if top is not None and getattr(top, "Title", "") == title:
                return top
        return None

    def run_modal(dialog_execute, title, name, send):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        time.sleep(3)
        subprocess.run(["osascript", "-e", front], check=False)
        th = threading.Thread(target=lambda: dialog_execute(doc), daemon=True)
        th.start()
        dlg = wait_dialog(title)
        if dlg is None:
            result[name] = {"error": "no dialog"}
            print(name, "no dialog", flush=True)
            return
        time.sleep(2)
        tabs(name, list(dlg.getWindows()), send)
        cli("kp:esc")
        th.join(10)
        if th.is_alive():
            try:
                dlg.setVisible(False)
            except Exception:  # noqa: BLE001
                pass
        try:
            doc.close(True)
        except Exception as error:  # noqa: BLE001
            print("close", error)
        time.sleep(1)

    # P: plain UNO dialog with ten single-line edits, built over the bridge
    def plain(doc):
        model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", remote)
        model.Title, model.Width, model.Height = "Plain probe", 220, 200
        for i in range(10):
            edit = model.createInstance("com.sun.star.awt.UnoControlEditModel")
            edit.PositionX, edit.PositionY, edit.Width, edit.Height = 10, 8 + 18 * i, 200, 12
            model.insertByName("e%d" % i, edit)
        dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", remote)
        dialog.setModel(model)
        dialog.createPeer(tk, doc.getCurrentController().getFrame().getContainerWindow())
        dialog.execute()
        dialog.dispose()
    run_modal(plain, "Plain probe", "plain-dialog-cliclick", lambda: cli("kp:tab"))

    # N: ND30 wizard in the office (extension dispatch)
    def inproc(doc):
        helper.executeDispatch(doc.getCurrentController().getFrame(), "org.hst.office.vi:Nd30Wizard", "", 0, ())
    run_modal(inproc, "Văn bản hành chính", "nd30-inprocess-cliclick", lambda: cli("kp:tab"))
    run_modal(inproc, "Văn bản hành chính", "nd30-inprocess-osascript", osa_tab)

    # R: ND30 wizard built over the bridge
    def bridged(doc):
        from hst_office import data_files, wizard_nd30
        wizard_nd30.Nd30Wizard(remote, data_files.load_locale("vi")).run(doc.getCurrentController().getFrame().getContainerWindow())
    run_modal(bridged, "Văn bản hành chính", "nd30-bridge-cliclick", lambda: cli("kp:tab"))
    run_modal(plain, "Plain probe", "plain-dialog-osascript", osa_tab)
    with open(os.path.join(out, "probe2.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)


if __name__ == "__main__":
    main()
