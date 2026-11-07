# SPDX-License-Identifier: AGPL-3.0-only
"""Windows probe of the ND30 wizard's "Loại văn bản" list: real cursor moves over the fields it covers, a screenshot per
step and the screen geometry, for analysis elsewhere. Evidence only. Run with the office's python.exe:
  nd30-type-list-probe.py --install <dir> --out <dir> --label <name>
The wizard is built over the bridge from the installed extension (sys.path), so an overlaid extension is what runs."""
import argparse, ctypes, ctypes.wintypes as wt, importlib.util, json, os, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
COVER = ["parentAgency", "agency", "number", "symbol", "place", "date", "summary", "kinhGui", "body", "signerAuthority"]


def smoke_module():
    spec = importlib.util.spec_from_file_location("winsmoke", os.path.join(ROOT, "tests", "runtime", "check-windows-smoke.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shot(out, name):
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "capture-screenshot.ps1"),
                    "-Path", os.path.join(out, name + ".png")], timeout=60, check=False)


def move(x, y, pause=0.9):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(pause)


def click(x, y):
    move(x, y, 0.3)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(1.2)


def client_origin(title):
    hwnd = user32.FindWindowW(None, title)
    point = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return hwnd, point.x, point.y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--port", type=int, default=2297)
    args = ap.parse_args()
    out = os.path.join(os.path.abspath(args.out), args.label)
    os.makedirs(out, exist_ok=True)
    smoke = smoke_module()
    smoke.SHOT_DIR = None
    program = os.path.join(args.install, "program")
    ext = os.path.join(args.install, "share", "extensions", "hst-vietnamese-tools", "python")
    sys.path.insert(0, ext)
    result = {"label": args.label}
    proc = None
    try:
        profile = "file:///" + os.path.join(out, "profile").replace("\\", "/")
        proc, ctx = smoke.start_office(program, profile, args.port, os.path.join(out, "soffice.err"), dict(os.environ))
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = smoke.open_document(ctx, desktop, "swriter")
        time.sleep(3)
        from hst_office import data_files, wizard_nd30
        wizard = wizard_nd30.Nd30Wizard(ctx, data_files.load_locale("vi"))
        title = wizard.d.model.Title
        parent = doc.getCurrentController().getFrame().getContainerWindow()
        thread = threading.Thread(target=lambda: wizard.run(parent), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(0.5)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        hwnd, ox, oy = client_origin(title)
        user32.SetForegroundWindow(hwnd)
        time.sleep(1)
        names = list(wizard.d.model.ElementNames)
        geo = {}
        for name in names:
            control = wizard.d.dialog.getControl(name)
            peer = control.getPeer() if control is not None else None
            if peer is not None:
                box = peer.getPosSize()
                geo[name] = [ox + box.X, oy + box.Y, box.Width, box.Height]
        result.update(origin=[ox, oy], geometry=geo, order=names, hwnd=int(hwnd or 0))
        away = geo.get("preview", [ox + 900, oy, 0, 0])
        move(away[0] + 40, away[1] + 40)
        shot(out, "0-closed")
        arrow = geo["typeOpen"]
        click(arrow[0] + arrow[2] // 2, arrow[1] + arrow[3] // 2)
        result["open_after_click"] = bool(wizard.picker.open)
        box = wizard.picker.popup.box() if hasattr(wizard.picker, "popup") else None
        if box:
            result["list_box"], result["popup"] = [ox + box[0], oy + box[1], box[2], box[3]], True
        elif "typeList" in geo:
            peer = wizard.d.dialog.getControl("typeList").getPeer().getPosSize()
            result["list_box"] = [ox + peer.X, oy + peer.Y, peer.Width, peer.Height]
        lb = result.get("list_box") or [geo["type"][0], geo["type"][1] + geo["type"][3], geo["type"][2], 300]
        move(lb[0] + lb[2] + 200, lb[1] + 20)
        shot(out, "1-open-pointer-away")
        steps = []
        for name in COVER:
            g = geo.get(name)
            if not g or g[1] + g[3] // 2 > lb[1] + lb[3]:
                continue
            x, y = lb[0] + lb[2] * 2 // 5, g[1] + g[3] // 2
            move(x, y, 1.2)
            shot(out, "2-hover-" + name)
            steps.append({"field": name, "pointer": [x, y], "open": bool(wizard.picker.open)})
        result["hover"] = steps
        # a covered field repaints while the list is open (its text changes): does it paint over the list?
        move(lb[0] + lb[2] + 200, lb[1] + 20)
        wizard.d.model.getByName("agency").Text = "UBND TỈNH QUẢNG NAM"
        time.sleep(1.2)
        shot(out, "3-covered-field-repaints")
        result["open_at_end"] = bool(wizard.picker.open)
        # click the row over "Cơ quan ban hành": it must choose that row and close the list, not focus the field
        before = wizard.picker.current
        g = geo["agency"]
        click(lb[0] + lb[2] * 2 // 5, g[1] + g[3] // 2)
        shot(out, "4-click-row")
        result["click_row"] = {"before": before, "after": wizard.picker.current, "open": bool(wizard.picker.open),
                               "agency_focus": bool(wizard.d.dialog.getControl("agency").getPeer().hasFocus())}
        # real keys: type a query in the type field, Tab
        t = geo["type"]
        click(t[0] + 20, t[1] + t[3] // 2)
        keys = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%s')"
        subprocess.run(["powershell", "-NoProfile", "-Command", keys % "quyet"], timeout=60, check=False)
        time.sleep(1.5)
        typed_open = bool(wizard.picker.open)
        shot(out, "5-typed-quyet")
        subprocess.run(["powershell", "-NoProfile", "-Command", keys % "{TAB}"], timeout=60, check=False)
        time.sleep(1.5)
        shot(out, "6-after-tab")
        result["type_then_tab"] = {"open_after_typing": typed_open, "current": wizard.picker.current, "open": bool(wizard.picker.open),
                                   "focus_parentAgency": bool(wizard.d.dialog.getControl("parentAgency").getPeer().hasFocus())}
        wizard.d.dialog.endExecute()
        thread.join(15)
        doc.setModified(False)
        doc.close(True)
    except Exception:  # noqa: BLE001
        import traceback
        result["error"] = traceback.format_exc()
        shot(out, "9-error")
    finally:
        with open(os.path.join(out, "probe.json"), "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps({k: v for k, v in result.items() if k not in ("geometry", "order")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
