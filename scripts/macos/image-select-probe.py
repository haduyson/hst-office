# SPDX-License-Identifier: AGPL-3.0-only
"""Click an as-character picture in Writer with the real mouse on macOS and report what got selected.

  image-select-probe.py <office-pid> <docx> <out-dir> <label>

Run with the bundled Python while soffice listens on pipe "hstimgsel". Loads the document over UNO, brings the
office to the front, finds the pale yellow square of the first picture in a screen capture, left-clicks it with
cliclick, reads the controller's selection, then right-clicks it for the context menu. Evidence only.
"""
import importlib.util
import json
import os
import threading
import subprocess
import sys
import time

import uno

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tab_probe", os.path.join(HERE, "tab-probe.py"))
tab_probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tab_probe)


def shot(out, name):
    path = f"{out}/{name}.png"
    subprocess.run(["screencapture", "-x", path], check=False)
    return path


def screen_points():
    rc, text = tab_probe.osa('tell application "Finder" to get bounds of window of desktop')
    parts = [int(p) for p in text.replace(" ", "").split(",")] if rc == 0 else []
    return (parts[2], parts[3]) if len(parts) == 4 else (None, None)


def find_yellow(path):
    width, height, rows, bpp = tab_probe.png_pixels(path)
    xs, ys = [], []
    for y in range(0, height, 2):
        line = rows[y]
        for x in range(0, width, 2):
            i = x * bpp
            r, g, b = line[i], line[i + 1], line[i + 2]
            if 238 <= r and 215 <= g <= 245 and 130 <= b <= 180:
                xs.append(x)
                ys.append(y)
    if len(xs) < 40:
        return None
    xs.sort()
    ys.sort()
    return xs[len(xs) // 2], ys[len(ys) // 2], len(xs), width, height


def selection(doc):
    sel = doc.CurrentController.getSelection()
    return sel.ImplementationName if sel is not None else None


def main(pid, docx, out, label):
    result = {"label": label}
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            rctx = resolver.resolve("uno:pipe,name=hstimgsel;urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        raise SystemExit("cannot connect to soffice")
    desktop = rctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", rctx)
    threading.Thread(target=tab_probe.dismiss_welcome, args=(pid,), daemon=True).start()
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(docx), "_blank", 0, ())
    shapes = []
    for i in range(doc.DrawPage.Count):
        s = doc.DrawPage.getByIndex(i)
        shapes.append({"impl": s.ImplementationName, "anchor": s.AnchorType.value,
                       "protected": [s.ContentProtected, s.PositionProtected], "opaque": s.Opaque})
    result["shapes"] = shapes
    result["readonly"] = doc.isReadonly()
    # Maximise the frame so the picture is on screen, then bring the app to the front.
    win = doc.CurrentController.Frame.ContainerWindow
    try:
        w, h = (int(v) for v in os.environ.get("PROBE_WIN", "1400x850").split("x"))
        win.setPosSize(0, 30, w, h, 15)
        result["window"] = [w, h]
    except Exception as exc:  # noqa: BLE001
        result["possize_error"] = str(exc)
    time.sleep(3)
    tab_probe.osa('tell application "System Events" to set frontmost of (first process whose unix id is %d) to true' % pid)
    time.sleep(2)
    result["front_pid"] = tab_probe.front_pid()
    result["screen_points"] = screen_points()
    before = shot(out, f"{label}-before")
    found = find_yellow(before)
    result["square"] = found
    result["before"] = selection(doc)
    if found:
        x, y, _n, pw, _ph = found
        scale = float(os.environ.get("PROBE_SCALE", "0")) or pw / (result["screen_points"][0] or pw)
        cx, cy = int(x / scale), int(y / scale)
        result["click_points"] = [cx, cy]
        r = tab_probe.click_keys(f"m:{cx},{cy}", "w:300", f"c:{cx},{cy}")
        result["cliclick"] = r.returncode
        time.sleep(2)
        result["after_click"] = selection(doc)
        shot(out, f"{label}-after-click")
        tab_probe.click_keys(f"rc:{cx},{cy}")
        time.sleep(2)
        shot(out, f"{label}-context-menu")
        tab_probe.click_keys("kp:esc")
        time.sleep(1)
        result["after_menu"] = selection(doc)
    with open(f"{out}/{label}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result), flush=True)
    doc.close(True)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4])
