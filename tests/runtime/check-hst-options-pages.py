#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Mở tài liệu and ▸ Giao diện on the real build: the pages load from the extension with
their handlers, "Kiểu biểu tượng" reads and writes SymbolStyle, and the Options tree lists both pages.

Usage: python3 tests/runtime/check-hst-options-pages.py --display :131 [--instdir upstream/libreoffice/instdir] [--out DIR]
                                                        [--port 2197]
The display must already run; it is never started or stopped here. Screenshot: options-tree.png. Exit 1 on failure.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402

ROWS = []
EXTENSION = "vnd.sun.star.expand:$BUNDLED_EXTENSIONS/hst-vietnamese-tools/dialogs/"


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:200]), flush=True)


def page_checks(service, parent, check):
    """Both pages built from the installed extension with their handlers, outside the Options dialog: controls,
    labels, and "Kiểu biểu tượng" reading and writing SymbolStyle. `service(name)` makes an office service; shared with
    check-windows-options-pages.py."""
    provider = service("com.sun.star.awt.ContainerWindowProvider")
    apps = provider.createContainerWindow(EXTENSION + "DefaultApps.xdl", "", parent, service("org.hst.office.vi.OptionsPage"))
    check("Mở tài liệu page loads with its button", apps is not None and apps.getControl("defaultApps") is not None)
    check("its button says what it does", apps.getControl("defaultApps").getModel().Label == "Dùng HST Office để mở tài liệu văn phòng")
    handler = service("org.hst.office.vi.OptionsAppearance")
    check("the Giao diện handler service exists (without it the Options dialog builds no page)", handler is not None)
    look = provider.createContainerWindow(EXTENSION + "Appearance.xdl", "", parent, handler)
    check("Giao diện page loads", look is not None and look.getControl("modern") is not None)
    handler.callHandlerMethod(look, "initialize", "external_event")
    check("the default is Cổ điển", look.getControl("classic").getState() and not look.getControl("modern").getState())
    look.getControl("modern").setState(True)
    handler.callHandlerMethod(look, "ok", "external_event")
    misc = "/org.openoffice.Office.Common/Misc"

    def symbol_style():
        import uno
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", misc
        node = service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,))
        return node.getPropertyValue("SymbolStyle")
    # the base style in any UI mode: the office picks the dark variant itself while the UI is dark
    check("Hiện đại writes the modern base style", symbol_style() == "hst_modern", symbol_style())
    handler.callHandlerMethod(look, "initialize", "external_event")
    check("the page reads Hiện đại back", look.getControl("modern").getState())
    look.getControl("classic").setState(True)
    handler.callHandlerMethod(look, "ok", "external_event")
    check("Cổ điển writes auto", symbol_style() == "auto", symbol_style())
    look.dispose()
    apps.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/hst-options-pages"))
    parser.add_argument("--port", type=int, default=2197)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    try:
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        page_checks(office.service, frame.getContainerWindow(), check)
        # the Options dialog itself: HST Office group with both pages (screenshot for review)
        runner = threading.Thread(target=lambda: office.dispatch(frame, ".uno:OptionsTreeDialog"), daemon=True)
        runner.start()
        title = None
        for _ in range(30):
            time.sleep(1)
            title = next((name for _wid, name in hst_gui.toplevels(args.display, office.pid) if name.startswith("Tùy chọn")), None)
            if title:
                break
        check("Công cụ ▸ Tùy chọn opens", title is not None, title)
        time.sleep(2)
        hst_gui.screenshot(os.path.join(out, "options-tree.png"), args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=args.display), check=False, timeout=10)
        runner.join(10)
        doc.close(True)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
