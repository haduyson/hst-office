#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Old-profile scenario, UNO half (bundled Python): every Tùy chọn ▸ HST Office page of the RUNNING office.

The same checks as check-windows-options-pages.py: the pages built with their handlers outside the dialog
(check-hst-options-pages.page_checks), every registered leaf's handler can be created, and the real Options dialog
opened on each page carries its labels (dark pixels in the page area; a page whose handler is unknown stays blank).
Usage: <bundled python> mac_options_pages.py <pipe name> <out dir>. Rows go to <out>/pages.json as they come."""
import json
from pathlib import Path
import re
import sys
import threading
import time
import traceback
from support import RUNTIME, existing, native, wait
import uno

sys.path.insert(0, str(RUNTIME))
import png_luma  # noqa: E402

GROUP = "/org.openoffice.Office.OptionsDialog/Nodes/vn.hasontech.hstoffice.Options/Leaves"
INK = 0.003  # check-windows-options-pages.py: about 0.01 with a page's labels, 0.0 when blank


def connect(pipe, timeout=120):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    end = time.monotonic() + timeout
    while True:
        try:
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:
            if time.monotonic() > end:
                raise
            time.sleep(1)


def props(**values):
    out = []
    for name, value in values.items():
        prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        prop.Name, prop.Value = name, value
        out.append(prop)
    return tuple(out)


def page_ink(shot, rect, points_wide):
    """Dark-pixel share right of the page tree and above the buttons, in screenshot pixels."""
    width, _height, luma = png_luma.read(Path(shot).read_bytes())
    scale = width / points_wide
    left, top, right, bottom = (int(v * scale) for v in rect)
    rows = luma[top + int((bottom - top) * 0.08):top + int((bottom - top) * 0.80)]
    values = [v for row in rows for v in row[left + int((right - left) * 0.30):right - int((right - left) * 0.02)]]
    return sum(v < 140 for v in values) / len(values) if values else 0.0


def main():
    pipe, out = sys.argv[1], Path(sys.argv[2])
    rows = []

    def check(name, ok, detail=""):
        rows.append(dict(check=name, status="PASS" if ok else "FAIL", detail=str(detail)[:500]))
        (out / "pages.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    ctx = connect(pipe)
    service = lambda name: ctx.ServiceManager.createInstanceWithContext(name, ctx)  # noqa: E731
    toolkit = service("com.sun.star.awt.Toolkit")
    desktop = service("com.sun.star.frame.Desktop")
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    frame = doc.CurrentController.Frame
    try:
        existing("check-hst-options-pages").page_checks(service, frame.ContainerWindow, check)
    except Exception:
        check("page checks outside the dialog", False, traceback.format_exc())
    leaves = service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationAccess", props(nodepath=GROUP))
    names = leaves.getElementNames()
    check("Tùy chọn lists HST Office pages", len(names) >= 2, names)
    expander = ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander")
    dispatcher = service("com.sun.star.frame.DispatchHelper")
    for name in names:
        leaf = leaves.getByName(name)
        label, page, handler = (leaf.getPropertyValue(key) for key in ("Label", "OptionsPage", "EventHandlerService"))
        try:
            made = service(handler) is not None if handler else True
        except Exception as error:
            made = f"{type(error).__name__}: {error}"
        check(f"{label}: its handler {handler} can be created", made is True, made)
        url = page.replace("%origin%", "$BUNDLED_EXTENSIONS/hst-vietnamese-tools")
        url = expander.expandMacros(url.replace("vnd.sun.star.expand:", "", 1))
        task = threading.Thread(target=dispatcher.executeDispatch, daemon=True,
                                args=(frame, ".uno:OptionsTreeDialog", "", 0, props(OptionsPageURL=url)))
        task.start()
        def dialog():
            for i in range(toolkit.getTopWindowCount()):
                window = toolkit.getTopWindow(i)
                title = getattr(window, "Title", "") or ""
                if window.isVisible() and (title.startswith("Tùy chọn") or title.startswith("Options")):
                    return window
            return None
        try:
            window = wait(dialog, 40)
        except TimeoutError:
            check(f"{label}: Công cụ ▸ Tùy chọn opens", False, "no Options window in 40 s")
            continue
        time.sleep(3)  # the page is built when it is first shown
        window.toFront()
        shot = out / ("page-%s.png" % re.sub(r"\W+", "_", name))
        native("shot", shot)
        box = window.getPosSize()
        ink = page_ink(shot, (box.X, box.Y, box.X + box.Width, box.Y + box.Height), toolkit.getWorkArea().Width)
        check(f"{label}: the page is not blank (dark-pixel share {ink:.4f} > {INK})", ink > INK,
              dict(window=(box.X, box.Y, box.Width, box.Height), screenshot=shot.name))
        native("key", "escape")
        task.join(20)
        check(f"{label}: dialog closed", not task.is_alive())
    doc.close(True)
    return int(any(row["status"] == "FAIL" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
