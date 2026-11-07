# SPDX-License-Identifier: AGPL-3.0-only
"""macOS probe of the ND30 wizard's "Loại văn bản" list (bundled Python, UNO on port 2002): open the list, move the
pointer over the fields it covers, make a covered field repaint, click a row. Screenshots and JSON; evidence only.
  nd30-type-list-probe.py <out-dir> <label> <extension python dir>"""
import json, os, subprocess, sys, threading, time
import uno

COVER = ["parentAgency", "agency", "number", "symbol", "place", "date", "summary", "kinhGui", "body", "signerAuthority"]


def shot(out, name):
    subprocess.run(["screencapture", "-x", os.path.join(out, name + ".png")], check=False)


def cli(*args):
    subprocess.run(["cliclick", "-w", "20", *args], check=False, timeout=60)


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
        thread = threading.Thread(target=lambda: wizard.run(doc.getCurrentController().getFrame().getContainerWindow()), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(0.5)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        frame = wizard.d.dialog.getPeer().getPosSize()
        ox, oy = frame.X, frame.Y
        geo = {}
        for name in wizard.d.model.ElementNames:
            control = wizard.d.dialog.getControl(name)
            if control is not None and control.getPeer() is not None:
                b = control.getPeer().getPosSize()
                geo[name] = [ox + b.X, oy + b.Y, b.Width, b.Height]
        result.update(origin=[ox, oy], geometry=geo)
        shot(out, "0-closed")
        wizard.picker.toggle()
        time.sleep(1.5)
        result["open"] = bool(wizard.picker.open)
        result["type_focus_after_open"] = bool(wizard.d.dialog.getControl("type").getPeer().hasFocus())
        if hasattr(wizard.picker, "popup") and wizard.picker.popup.box():
            b = wizard.picker.popup.box()
            lb = [ox + b[0], oy + b[1], b[2], b[3]]
        else:
            b = wizard.d.dialog.getControl("typeList").getPeer().getPosSize()
            lb = [ox + b.X, oy + b.Y, b.Width, b.Height]
        result["list_box"] = lb
        cli("m:%d,%d" % (lb[0] + lb[2] + 150, lb[1] + 10))
        time.sleep(1)
        shot(out, "1-open-pointer-away")
        hover = []
        for name in COVER:
            g = geo.get(name)
            if not g or g[1] + g[3] // 2 > lb[1] + lb[3]:
                continue
            cli("m:%d,%d" % (lb[0] + lb[2] * 2 // 5, g[1] + g[3] // 2))
            time.sleep(1.2)
            shot(out, "2-hover-" + name)
            hover.append(name)
        result["hover"] = hover
        cli("m:%d,%d" % (lb[0] + lb[2] + 150, lb[1] + 10))
        wizard.d.model.getByName("agency").Text = "UBND TỈNH QUẢNG NAM"
        wizard.d.model.getByName("place").Text = "Tam Kỳ"
        time.sleep(1.5)
        shot(out, "3-covered-field-repaints")
        before = wizard.picker.current
        g = geo["agency"]
        cli("c:%d,%d" % (lb[0] + lb[2] * 2 // 5, g[1] + g[3] // 2))
        time.sleep(1.5)
        shot(out, "4-click-row")
        result["click"] = {"before": before, "after": wizard.picker.current, "open": bool(wizard.picker.open),
                           "agency_focus": bool(wizard.d.dialog.getControl("agency").getPeer().hasFocus())}
        wizard.d.dialog.endExecute()
        thread.join(15)
        doc.setModified(False)
        doc.close(True)
    except Exception:  # noqa: BLE001
        import traceback
        result["error"] = traceback.format_exc()
        shot(out, "9-error")
    with open(os.path.join(out, "probe.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != "geometry"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
