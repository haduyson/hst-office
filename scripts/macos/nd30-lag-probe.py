# SPDX-License-Identifier: AGPL-3.0-only
"""Time field switching in the ND30 wizard on macOS (bundled Python, UNO socket on port 2002). Evidence only.

  nd30-lag-probe.py <office-pid> <out-dir> <variant>

The wizard runs in the office (extension dispatch). Keys and clicks come from cliclick. For each key the probe waits until
its own toolkit key handler has seen the key, then makes one call that needs the office's main thread (peer.getPosSize):
it returns only when the office has finished handling the key (Edit modify, wizard refresh, repaint requests).
"""
import json
import os
import statistics
import subprocess
import sys
import threading
import time

import uno
import unohelper
from com.sun.star.awt import XKeyHandler

PORT = 2002
PARA = ("Thực hiện Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư, Ủy ban nhân dân "
        "tỉnh đề nghị các sở, ban, ngành khẩn trương rà soát, báo cáo kết quả trước ngày quy định.")
KEYS = []


class Keys(unohelper.Base, XKeyHandler):
    def keyPressed(self, event):
        KEYS.append(time.perf_counter())
        return False

    def keyReleased(self, event):
        return False

    def disposing(self, event):
        pass


def cli(*args):
    subprocess.run(["cliclick", "-w", "5", *args], check=False, timeout=60)


def osa(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=20)


def main():
    pid, out, variant = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            remote = resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        raise SystemExit("cannot connect")
    smgr = remote.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", remote)
    helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", remote)
    tk = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", remote)
    tk.addKeyHandler(Keys())
    results = {"variant": variant, "runs": []}

    def one(send, keys=1, focus_peer=None):
        n, t0 = len(KEYS), time.perf_counter()
        send()
        while time.perf_counter() - t0 < (5 if focus_peer is not None else 60):
            if focus_peer is not None:
                if focus_peer.hasFocus():
                    break
            elif len(KEYS) >= n + keys:
                break
            time.sleep(0.0005)
        kids[0].getPosSize()
        return round((time.perf_counter() - t0) * 1000, 1)

    for query in ("cong van", "quyet dinh", "thong tri"):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        time.sleep(2)
        frame = doc.getCurrentController().getFrame()
        osa(f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true')
        threading.Thread(target=lambda: helper.executeDispatch(frame, "org.hst.office.vi:Nd30Wizard", "", 0, ()), daemon=True).start()
        dlg = None
        for _ in range(150):
            time.sleep(0.2)
            top = tk.getActiveTopWindow()
            if top is not None and getattr(top, "Title", "") == "Văn bản hành chính":
                dlg = top
                break
        if dlg is None:
            results["runs"].append({"query": query, "error": "no dialog"})
            subprocess.run(["screencapture", "-x", os.path.join(out, f"{variant}-{query}-nodialog.png")], check=False)
            continue
        time.sleep(2)
        global kids
        kids = list(dlg.getWindows())
        cli("kd:cmd", "t:a", "ku:cmd")
        cli("t:" + query)
        time.sleep(1)
        cli("kp:return")
        time.sleep(1)
        run = {"query": query, "tab_empty": [], "key": [], "tab_after_typing": [], "burst_then_tab": [], "click": []}
        # 1. Tab through every field of the empty form.
        for _ in range(16):
            run["tab_empty"].append(one(lambda: cli("kp:tab")))
        subprocess.run(["screencapture", "-x", os.path.join(out, f"{variant}-{query}-1-empty.png")], check=False)
        # back to the type field (Shift+Tab 16 times), then fill: Tab, type "12" key by key, except the date
        for _ in range(16):
            cli("kd:shift", "kp:tab", "ku:shift")
        time.sleep(0.5)
        subprocess.run(["pbcopy"], input="\n".join([PARA] * 40).encode("utf-8"), check=False)
        for field in range(15):
            run["tab_after_typing"].append(one(lambda: cli("kp:tab")))
            if field == 9:
                run["paste_ms"] = one(lambda: cli("kd:cmd", "t:v", "ku:cmd"))
            elif field != 6:
                for ch in "12":
                    run["key"].append(one(lambda ch=ch: cli("t:" + ch)))
        subprocess.run(["screencapture", "-x", os.path.join(out, f"{variant}-{query}-2-filled.png")], check=False)
        # 2. Typing burst then Tab (the user types a word and moves on): until the Tab has been handled and the UI is idle.
        for _ in range(5):
            cli("kd:shift", "kp:tab", "ku:shift")
        time.sleep(0.5)
        for _ in range(4):
            run["burst_then_tab"].append(one(lambda: cli("t:abcdefghij", "kp:tab"), keys=11))
        # 3. Mouse click from field to field (single-line fields; dialog origin + control position).
        box = dlg.getPosSize()
        run["dialog_box"] = [box.X, box.Y, box.Width, box.Height]
        for index in (7, 9, 11, 13, 15, 27, 29, 7):  # parentAgency, agency, number, symbol, place, signerTitle, signerName, back
            peer = kids[index]
            p = peer.getPosSize()
            x, y = box.X + p.X + p.Width // 2, box.Y + p.Y + p.Height // 2
            run["click"].append(one(lambda: cli(f"c:{x},{y}"), focus_peer=peer))
        for key in ("tab_empty", "key", "tab_after_typing", "burst_then_tab", "click"):
            values = run[key]
            run[key + "_summary"] = {"median": statistics.median(values), "max": max(values)} if values else None
        print(json.dumps({k: v for k, v in run.items() if not isinstance(v, list)}, ensure_ascii=False), flush=True)
        results["runs"].append(run)
        cli("kp:esc")
        time.sleep(1)
        try:
            doc.close(True)
        except Exception as error:  # noqa: BLE001
            print("close:", error)
        with open(os.path.join(out, f"latency-{variant}.json"), "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
