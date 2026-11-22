# SPDX-License-Identifier: AGPL-3.0-only
"""Drive the HST Office Start Center on macOS over UNO (run with the bundled Python).

  start-center-probe.py seed <out-dir>        store the sample documents and make them the recent ones
  start-center-probe.py shoot <out-dir> <WxH,...>
                                              size the Start Center window to each WxH (points), screenshot
                                              the screen, and record the window, the display's DPI and the
                                              boxes of the Start Center's accessible items

Evidence only: writes <out-dir>/start-center.json; the screenshots are start-center-<W>x<H>.png. An item box
outside the Start Center window is listed as "outside" (it would be cut).
"""
import json
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

PORT = 2002
SAMPLES = [("Báo cáo", "Báo cáo tổng kết quý 3.docx", "swriter", "MS Word 2007 XML"),
           ("Tài chính", "Kế hoạch ngân sách 2027.xlsx", "scalc", "Calc MS Excel 2007 XML"),
           ("Dự án", "Hồ sơ dự án chuyển đổi số.docx", "swriter", "MS Word 2007 XML"),
           ("Marketing", "Bài thuyết trình giới thiệu sản phẩm.pptx", "simpress", "Impress MS PowerPoint 2007 XML"),
           ("Công việc", "Danh sách công việc tháng 11.xlsx", "scalc", "Calc MS Excel 2007 XML")]
PINNED = ("Hồ sơ dự án chuyển đổi số.docx", "Kế hoạch ngân sách 2027.xlsx")


def prop(name, value):
    result = PropertyValue()
    result.Name, result.Value = name, value
    return result


def connect():
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            return resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001 - the office is still starting
            time.sleep(1)
    raise SystemExit("cannot connect to soffice")


def seed(ctx, out):
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    root = os.path.join(out, "samples")
    urls = []
    for folder, name, factory, filter_name in SAMPLES:
        os.makedirs(os.path.join(root, folder), exist_ok=True)
        path = os.path.join(root, folder, name)
        doc = desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0,
                                           (prop("Hidden", True), prop("OnMainThread", True)))
        doc.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", filter_name),))
        doc.close(True)
        urls.append((name, uno.systemPathToFileUrl(path)))
    provider = smgr.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    access = provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess",
        (prop("nodepath", "/org.openoffice.Office.Histories/Histories/PickList"),))
    items, order = access.getByName("ItemList"), access.getByName("OrderList")
    for index, (name, url) in enumerate(urls):
        item = items.createInstance()
        item.setPropertyValue("Title", name)
        item.setPropertyValue("Pinned", name in PINNED)
        items.insertByName(url, item)
        entry = order.createInstance()
        entry.setPropertyValue("HistoryItemRef", url)
        order.insertByName(str(index), entry)
    access.commitChanges()
    print("seeded", len(urls), "recent documents", flush=True)
    # a clean exit writes the history to the profile (a killed office keeps none of it and asks to
    # report the crash at the next start)
    try:
        desktop.terminate()
    except Exception:  # noqa: BLE001 - the bridge goes away with the office
        pass


def start_center_frame(desktop):
    for _ in range(60):
        frames = desktop.getFrames()
        for index in range(frames.getCount()):
            frame = frames.getByIndex(index)
            controller = frame.getController()
            if controller is not None and controller.getImplementationName() == "com.sun.star.comp.sfx2.BackingComp":
                return frame
        time.sleep(1)
    return None


def accessible_items(window):
    """[(role, name, [x, y, w, h])] of the showing buttons and list items under the window (screen points)."""
    showing = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SHOWING")
    roles = {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name): name
             for name in ("PUSH_BUTTON", "LIST_ITEM", "PANEL", "SCROLL_BAR")}
    found = []

    def walk(context, depth):
        if depth > 12:
            return
        try:
            role = context.getAccessibleRole()
            if role in roles and context.getAccessibleStateSet() & showing:
                where, size = context.getLocationOnScreen(), context.getSize()
                found.append((roles[role], context.getAccessibleName(), [where.X, where.Y, size.Width, size.Height]))
            for index in range(min(context.getAccessibleChildCount(), 200)):
                walk(context.getAccessibleChild(index).getAccessibleContext(), depth + 1)
        except Exception:  # noqa: BLE001 - nodes come and go
            return

    try:
        walk(window.getAccessibleContext(), 0)
    except AttributeError:  # toolkit windows hand their XAccessible out as a property
        walk(window.getProperty("XAccessible").getAccessibleContext(), 0)
    return found


def inside(box, outer, slack=1):
    x, y, w, h = box
    ox, oy, ow, oh = outer
    return x >= ox - slack and y >= oy - slack and x + w <= ox + ow + slack and y + h <= oy + oh + slack


def shoot(ctx, out, sizes):
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = start_center_frame(desktop)
    if frame is None:
        raise SystemExit("no Start Center frame")
    container, component = frame.getContainerWindow(), frame.getComponentWindow()
    try:
        info = component.getInfo()
        dpi = [round(info.PixelPerMeterX * 0.0254, 1), round(info.PixelPerMeterY * 0.0254, 1)]
    except Exception as error:  # noqa: BLE001 - evidence only
        dpi = repr(error)
    result = {"dpi": dpi, "cases": []}
    print("display DPI as the office sees it:", result["dpi"], flush=True)
    for case in sizes:
        if case == "maximized":
            container.IsMaximized = True
        else:
            width, height = (int(v) for v in case.split("x"))
            container.IsMaximized = False
            time.sleep(1)
            container.setPosSize(0, 30, width, height, 15)  # PosSize.POSSIZE
        time.sleep(4)
        subprocess.run(["osascript", "-e", 'tell application "System Events" to tell (first process whose name '
                        'contains "soffice" or name contains "HST") to set frontmost to true'],
                       capture_output=True, check=False, timeout=15)
        time.sleep(2)
        shot = os.path.join(out, f"start-center-{case}.png")
        subprocess.run(["screencapture", "-x", shot], check=False)
        outer = container.getPosSize()
        accessible = component.getAccessibleContext() if hasattr(component, "getAccessibleContext") else None
        canvas = component
        try:
            where = accessible.getLocationOnScreen() if accessible else None
            size = accessible.getSize() if accessible else None
            box = [where.X, where.Y, size.Width, size.Height] if where else None
        except Exception:  # noqa: BLE001
            box = None
        items = accessible_items(canvas)
        items_box = box or next((b for r, _n, b in items if r == "PANEL"), None)
        outside = [(n, b) for r, n, b in items if r in ("PUSH_BUTTON", "LIST_ITEM") and items_box
                   and b[2] > 0 and b[3] > 0 and not inside(b, items_box)]
        bars = [b for r, _n, b in items if r == "SCROLL_BAR"]
        entry = {"case": case, "shot": os.path.basename(shot),
                 "window": [outer.X, outer.Y, outer.Width, outer.Height], "start_center": items_box,
                 "items": len(items), "outside": outside, "scroll_bars": bars}
        result["cases"].append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        with open(os.path.join(out, "start-center.json"), "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("seed", "shoot"):
        raise SystemExit(__doc__)
    ctx = connect()
    if sys.argv[1] == "seed":
        seed(ctx, sys.argv[2])
    else:
        shoot(ctx, sys.argv[2], sys.argv[3].split(","))


if __name__ == "__main__":
    main()
