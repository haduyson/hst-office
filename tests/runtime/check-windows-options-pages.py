#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Every Tùy chọn ▸ HST Office page of an INSTALLED HST Office on Windows, inside the real Options dialog.

The page checks of check-hst-options-pages.py (Linux) run first: both pages built with their handlers, "Kiểu biểu tượng"
reads and writes SymbolStyle. Those build a page outside the dialog, which never shows what the user sees: the Options
dialog builds an extension page only when its handler service can be created (cui treeopt.cxx
ExtensionsTabPage::CreateDialogWithHandler) and leaves the page blank otherwise. So, for every leaf registered under
the HST Office node (OptionsDialog.xcu, read back from the office): open Công cụ ▸ Tùy chọn on that page
(.uno:OptionsTreeDialog with OptionsPageURL) and require each label of its .xdl to be shown in the dialog, with a size.

--profile/--carried: use a profile an older version left behind instead of a new one (the owner's case: uninstall,
install, start). Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-options-pages.py --install DIR
--out DIR [--profile DIR] [--carried] [--port 2117]. Screenshots: <out>/page-<label>.png. Exit 1 on any FAIL.
"""
import argparse
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402

LINUX = wg.load_check("check-hst-options-pages")
GROUP = "/org.openoffice.Office.OptionsDialog/Nodes/vn.hasontech.hstoffice.Options"
DLG = "{http://openoffice.org/2000/dialog}"
SHOWN_KINDS = ("radio", "button", "checkbox", "fixedline", "text", "titledbox")


def leaves(office):
    """[(node name, label, page url with %origin%, handler)] of the HST Office group, as the office reads them."""
    node = office.config(GROUP + "/Leaves", None)
    out = []
    for name in node.getElementNames():
        leaf = node.getByName(name)
        out.append((name, leaf.getPropertyValue("Label"), leaf.getPropertyValue("OptionsPage"),
                    leaf.getPropertyValue("EventHandlerService")))
    return out


def expected_labels(xdl_path):
    """The labels of a page's controls: what the user must see on it."""
    root = ET.parse(xdl_path).getroot()
    labels = []
    for element in root.iter():
        kind = element.tag.replace(DLG, "")
        value = element.get(DLG + "value")
        if kind in SHOWN_KINDS and value:
            labels.append(value.replace("~", ""))
    return labels


def options_dialog(office, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for window, title in wg.dialogs(office):
            if title.startswith("Tùy chọn") or title.startswith("Options"):
                return window, title
        time.sleep(0.5)
    return None, None


def shown_with_size(dialog, label):
    """(shown, bounds) of the first control named `label` in the dialog's accessibility tree."""
    for context, _depth in wg.walk(dialog):
        try:
            if context.getAccessibleName() != label:
                continue
            box = context.getBounds()
            return wg.showing(context) and box.Width > 2 and box.Height > 2, (box.X, box.Y, box.Width, box.Height)
        except Exception:  # noqa: BLE001
            continue
    return False, None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--carried", action="store_true")
    parser.add_argument("--port", type=int, default=2117)
    args = parser.parse_args()
    out, install = os.path.abspath(args.out), os.path.abspath(args.install)
    check = wg.Results(out, "options-pages" + ("-carried" if args.carried else ""))
    office = wg.WinOffice(install, os.path.abspath(args.profile or os.path.join(out, "profile")), args.port,
                          os.path.join(out, "logs"))
    try:
        office.start(fresh=not args.carried)
        check.note("start-up dialog closed first", wg.dismiss_startup(office, os.path.join(out, "startup-dialog.png")))
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        try:
            LINUX.page_checks(office.service, frame.getContainerWindow(), check)
        except Exception:  # noqa: BLE001 - a failing service lookup must not stop the dialog checks
            import traceback
            check("page checks outside the dialog", False, traceback.format_exc())
        found = leaves(office)
        check("Tùy chọn lists HST Office pages", len(found) >= 2, found)
        for name, label, page, handler in found:
            try:
                made = office.service(handler) is not None if handler else True
            except Exception as error:  # noqa: BLE001
                made = "%s: %s" % (type(error).__name__, error)
            check("%s: its handler %s can be created" % (label, handler), made is True, made)
            import uno
            url = office.expand(page.replace("%origin%", "$BUNDLED_EXTENSIONS/hst-vietnamese-tools"))
            labels = expected_labels(uno.fileUrlToSystemPath(url))
            thread = office.dispatch_async(frame, ".uno:OptionsTreeDialog", OptionsPageURL=url)
            dialog, title = options_dialog(office)
            check("%s: Công cụ ▸ Tùy chọn opens" % label, dialog is not None, title)
            if dialog is None:
                continue
            time.sleep(3)  # the page is built when it is first shown
            shot = os.path.join(out, "page-%s.png" % re.sub(r"\W+", "_", name))
            wg.screenshot(shot)
            selected = wg.find_named(dialog, label)
            check.note("%s: tree entry" % label, selected is not None and wg.showing(selected))
            results = {text: shown_with_size(dialog, text) for text in labels}
            missing = [text for text, (ok, _box) in results.items() if not ok]
            check("%s: the page is not blank, every label is shown (%d)" % (label, len(labels)), labels and not missing,
                  {"missing": missing, "shown": {t: b for t, (ok, b) in results.items() if ok}, "screenshot": shot})
            wg.close_dialog(dialog)
            thread.join(20)
            if thread.is_alive():  # endExecute is not offered by the Options dialog: Escape it with real keys
                hwnd = wg.hwnd_of(title)
                if hwnd:
                    wg.foreground(hwnd)
                wg.keys("escape")
                thread.join(20)
            check.note("%s: dialog closed" % label, not thread.is_alive())
        doc.close(True)
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
