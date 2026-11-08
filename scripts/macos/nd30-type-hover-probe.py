# SPDX-License-Identifier: AGPL-3.0-only
"""macOS probe: does the highlight of the ND30 "Loại văn bản" list follow the pointer (bundled Python, UNO on 2002)?
Opens the wizard, opens the list, moves the pointer over rows with cliclick, records the highlighted row after each
move, then clicks. Evidence only.  nd30-type-hover-probe.py <out-dir> <label> <extension python dir>"""
import json
import os
import subprocess
import sys
import threading
import time
import traceback

import uno


def main():
    out, label, extpy = sys.argv[1], sys.argv[2], sys.argv[3]
    out = os.path.join(out, label)
    os.makedirs(out, exist_ok=True)
    sys.path.insert(0, extpy)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(120):
        try:
            ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    result = {"label": label}
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        time.sleep(3)
        from hst_office import data_files, wizard_nd30
        wizard = wizard_nd30.Nd30Wizard(ctx, data_files.load_locale("vi"))
        parent = doc.getCurrentController().getFrame().getContainerWindow()
        thread = threading.Thread(target=lambda: wizard.run(parent), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(0.5)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        frame = wizard.d.dialog.getPeer().getPosSize()
        wizard.picker.toggle()
        time.sleep(1.5)
        bx, by, bw, bh = wizard.picker.popup.box()
        x, y = frame.X + bx, frame.Y + by
        result.update(dialog=[frame.X, frame.Y], popup=[bx, by, bw, bh], start_index=wizard.picker.index)
        moves = []
        for dy in range(12, bh - 8, 24):
            subprocess.run(["cliclick", "-w", "20", "m:%d,%d" % (x + bw // 3, y + dy)], check=False, timeout=30)
            time.sleep(1.5)
            index = wizard.picker.index
            moves.append([dy, index, wizard.picker.table[index][0].strip() if index >= 0 else None])
        result["moves"] = moves
        subprocess.run(["screencapture", "-x", os.path.join(out, "hover.png")], check=False)
        hovered = wizard.picker.index
        subprocess.run(["cliclick", "-w", "20", "c:."], check=False, timeout=30)
        time.sleep(1.5)
        result["click"] = {"hovered_id": wizard.picker.table[hovered][1] if hovered >= 0 else None,
                           "chosen": wizard.picker.current, "open": bool(wizard.picker.open)}
        wizard.d.dialog.endExecute()
        thread.join(15)
        doc.setModified(False)
        doc.close(True)
    except Exception:  # noqa: BLE001
        result["error"] = traceback.format_exc()
        subprocess.run(["screencapture", "-x", os.path.join(out, "error.png")], check=False)
    with open(os.path.join(out, "probe.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
