# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 wizard field-switch latency on macOS with keys posted inside VCL (XToolkitRobot), so OS key delivery on a VM
cannot drop them. Per key: post, wait until the probe's toolkit key handler saw it, then one main-thread call; the time
covers VCL focus handling, the edit's modify, the wizard's refresh() and repaint requests.
  nd30-lag-probe3.py <pid> <out-dir> <variant>"""
import json, os, statistics, subprocess, sys, threading, time
import uno, unohelper
from com.sun.star.awt import XKeyHandler, KeyEvent

KEYS = []
K = lambda name: uno.getConstantByName("com.sun.star.awt.Key." + name)  # noqa: E731
PARA = ("Thực hiện Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư, Ủy ban nhân dân "
        "tỉnh đề nghị các sở, ban, ngành khẩn trương rà soát, báo cáo kết quả trước ngày quy định.")


class Keys(unohelper.Base, XKeyHandler):
    def keyPressed(self, e):
        KEYS.append(time.perf_counter())
        return False

    def keyReleased(self, e):
        return False

    def disposing(self, e):
        pass


def main():
    pid, out, variant = int(sys.argv[1]), sys.argv[2], sys.argv[3]
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
    results = {"variant": variant, "runs": []}

    def press(target, code, char="", mods=0):
        event = KeyEvent()
        event.Source, event.KeyCode, event.Modifiers = target, code, mods
        if char:
            event.KeyChar = char
        tk.keyPress(event)
        tk.keyRelease(event)

    def timed(target, code, char="", mods=0, probe=None):
        """posted keys skip toolkit key handlers: time until the office is idle again (processEventsToIdle)"""
        tk.processEventsToIdle()
        t0 = time.perf_counter()
        press(target, code, char, mods)
        tk.processEventsToIdle()
        return round((time.perf_counter() - t0) * 1000, 1)

    def summary(values):
        return {"n": len(values), "median": statistics.median(values), "p90": sorted(values)[int(len(values) * 0.9) - 1], "max": max(values)} if values else None

    def session(name, execute, title, query=None):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        time.sleep(3)
        subprocess.run(["osascript", "-e", front], check=False)
        th = threading.Thread(target=lambda: execute(doc), daemon=True)
        th.start()
        dlg = None
        for _ in range(150):
            time.sleep(0.2)
            top = tk.getActiveTopWindow()
            if top is not None and getattr(top, "Title", "") == title:
                dlg = top
                break
        if dlg is None:
            results["runs"].append({"name": name, "error": "no dialog"})
            return
        subprocess.run(["osascript", "-e", front], check=False)
        time.sleep(2)
        kids = list(dlg.getWindows())
        run = {"name": name}
        if query:  # real keys: a posted Return skips the type list's key handler and presses the default button
            subprocess.run(["cliclick", "-w", "20", "t:" + query], check=False, timeout=60)
            time.sleep(1)
            subprocess.run(["cliclick", "kp:return"], check=False, timeout=60)
            time.sleep(1.5)
            top = tk.getActiveTopWindow()
            if top is None or getattr(top, "Title", "") != title:
                results["runs"].append({"name": name, "error": "wizard closed on Return"})
                print(name, "wizard closed on Return", flush=True)
                doc.setModified(False)
                doc.close(True)
                return
        run["tab_empty"] = [timed(dlg, K("TAB"), probe=kids[0]) for _ in range(20)]
        for _ in range(20):
            press(dlg, K("TAB"), mods=1)  # Shift+Tab back
        time.sleep(1)
        keys, tabs = [], []
        subprocess.run(["pbcopy"], input="\n".join([PARA] * 40).encode("utf-8"), check=False)
        for field in range(15):
            tabs.append(timed(dlg, K("TAB"), probe=kids[0]))
            if field == 9:
                run["paste_ms"] = timed(dlg, K("V"), "v", mods=2, probe=kids[0])  # Cmd+V (MOD1)
            elif field != 6:
                for ch in "12":
                    keys.append(timed(dlg, K("NUM" + ch), ch, probe=kids[0]))
        run["key_filled"], run["tab_filled"] = keys, tabs
        run["key_after_body"] = [timed(dlg, K("NUM1"), "1", probe=kids[0]) for _ in range(20)]
        subprocess.run(["screencapture", "-x", os.path.join(out, f"probe3-{variant}-{name}.png")], check=False)
        if query:  # Vietnamese text in every one-line field, then a screenshot and the geometry of every control
            subprocess.run(["pbcopy"], input="gỵ ý Quý Ủy".encode("utf-8"), check=False)
            for _ in range(40):
                press(dlg, K("TAB"), mods=1)
            tk.processEventsToIdle()
            for stop in range(21):
                press(dlg, K("TAB"))
                if stop not in (0, 6):  # the arrow button, the date
                    press(dlg, K("A"), "a", mods=2)
                    press(dlg, K("V"), "v", mods=2)
                tk.processEventsToIdle()
            box = dlg.getPosSize()
            run["geometry"] = {"dialog": [box.X, box.Y, box.Width, box.Height],
                               "children": [[c.getPosSize().X, c.getPosSize().Y, c.getPosSize().Width, c.getPosSize().Height] for c in kids]}
            subprocess.run(["screencapture", "-x", os.path.join(out, f"probe3-{variant}-{name}-text.png")], check=False)
        for key in ("tab_empty", "tab_filled", "key_filled", "key_after_body"):
            run[key + "_summary"] = summary(run[key])
        print(json.dumps({k: v for k, v in run.items() if not isinstance(v, list)}), flush=True)
        results["runs"].append(run)
        press(dlg, K("ESCAPE"))
        th.join(10)
        try:
            doc.setModified(False)
            doc.close(True)
        except Exception as error:  # noqa: BLE001
            print("close", error)
        time.sleep(1)
        with open(os.path.join(out, f"probe3-{variant}.json"), "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=1)

    def wizard(doc):
        helper.executeDispatch(doc.getCurrentController().getFrame(), "org.hst.office.vi:Nd30Wizard", "", 0, ())

    def plain(doc):
        model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", remote)
        model.Title, model.Width, model.Height = "Plain probe", 220, 300
        for i in range(16):
            edit = model.createInstance("com.sun.star.awt.UnoControlEditModel")
            edit.PositionX, edit.PositionY, edit.Width, edit.Height = 10, 8 + 18 * i, 200, 12
            model.insertByName("e%d" % i, edit)
        dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", remote)
        dialog.setModel(model)
        dialog.createPeer(tk, doc.getCurrentController().getFrame().getContainerWindow())
        dialog.execute()
        dialog.dispose()

    if variant == "shipped":
        session("plain-dialog", plain, "Plain probe")
    for query in ("cong van", "quyet dinh", "thong tri"):
        session("nd30-" + query.replace(" ", "-"), wizard, "Văn bản hành chính", query)


if __name__ == "__main__":
    main()
