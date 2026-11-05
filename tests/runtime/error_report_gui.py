# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-error-report.py: test instdir, windows of the report dialogs, clicks in AppFont units, menus."""
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import hst_gui

ROOT = hst_gui.ROOT
EXT = "hst-vietnamese-tools"
COMMAND = "org.hst.office.vi:ReportError"
LABEL = "Báo lỗi cho HASON TECH…"
TITLE = "Báo lỗi cho HASON TECH"
PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-error-report-menu.patch")
POPUPS = {"swriter": "sw/uiconfig/swriter", "scalc": "sc/uiconfig/scalc", "simpress": "sd/uiconfig/simpress"}
MODULES = {"swriter": "com.sun.star.text.TextDocument", "scalc": "com.sun.star.sheet.SpreadsheetDocument",
           "simpress": "com.sun.star.presentation.PresentationDocument"}


def prepare_instdir(instdir, out):
    """Hard-linked instdir copy with the freshly built test package (--update-test-mode) as the bundled extension.

    An instdir built before hst-error-report-menu.patch lacks the ribbon entry: the patch is then applied to fresh
    copies of the three menu files of this copy (never through the links), and a note says so."""
    copy = os.path.join(out, "instdir")
    if not os.path.isdir(copy):
        subprocess.run(["cp", "-al", os.path.abspath(instdir), copy], check=True)
    pkg = os.path.join(out, "ext")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build-extensions.py"), "--output", pkg,
                    "--update-test-mode"], check=True, stdout=subprocess.DEVNULL)
    target = os.path.join(copy, "share", "extensions", EXT)
    shutil.rmtree(target, ignore_errors=True)  # removes only this copy's links
    subprocess.run(["unzip", "-q", os.path.join(pkg, EXT + ".oxt"), "-d", target], check=True)
    cfg = os.path.join(copy, "share", "config", "soffice.cfg", "modules")
    tree = os.path.join(out, "menu-src")
    for module, src in POPUPS.items():
        path = os.path.join(cfg, module, "popupmenu", "notebookbar.xml")
        if COMMAND in open(path, encoding="utf-8").read():
            continue
        print("note: %s lacks the ribbon entry, applying hst-error-report-menu.patch to the test copy" % module)
        os.makedirs(os.path.join(tree, src, "popupmenu"), exist_ok=True)
        shutil.copyfile(path, os.path.join(tree, src, "popupmenu", "notebookbar.xml"))
    if os.path.isdir(tree):
        subprocess.run(["patch", "-d", tree, "-p1", "-s", "-f", "--no-backup-if-mismatch", "-i", PATCH], check=True)
        for module, src in POPUPS.items():
            fixed = os.path.join(tree, src, "popupmenu", "notebookbar.xml")
            if os.path.exists(fixed):
                path = os.path.join(cfg, module, "popupmenu", "notebookbar.xml")
                os.unlink(path)  # break the hard link before writing
                shutil.copyfile(fixed, path)
        shutil.rmtree(tree)
    return copy


def wait(predicate, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.5)
    return None


def windows(office, pattern):
    return [w for w in hst_gui.toplevels(office.display, office.pid) if re.search(pattern, w[1])]


def size(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    return tuple(int(re.search(r"%s: (-?\d+)" % key, info).group(1)) for key in ("Width", "Height"))


def click(office, wid, x, y, units):
    """Click the point (x, y) given in the dialog's AppFont `units` = (width, height)."""
    width, height = size(office.display, wid)
    env = dict(os.environ, DISPLAY=office.display)
    subprocess.run(["xdotool", "windowraise", wid], env=env, check=False, timeout=10)
    subprocess.run(["xdotool", "mousemove", "--window", wid, str(int(width * x / units[0])),
                    str(int(height * y / units[1])), "click", "1"], env=env, check=False, timeout=10)
    time.sleep(0.6)


def xdo(office, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=office.display), check=False, timeout=30)


def dispatch_async(office, frame, command=COMMAND):
    """The dialog is modal: the dispatch returns only when it closes, so it runs on its own thread."""
    thread = threading.Thread(target=lambda: office.dispatch(frame, command), daemon=True)
    thread.start()
    return thread


def help_addon(office):
    """(title, contexts) of the entry as this office merged it into the classic Help menus (Addons OfficeHelp)."""
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    arg = PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Addons/AddonUI/OfficeHelp")
    node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
    for name in node.getElementNames():
        item = node.getByName(name)
        if item.getPropertyValue("URL") == COMMAND:
            return item.getPropertyValue("Title"), set(item.getPropertyValue("Context").split(","))
    return None, set()


def open_start_center_help(office, wid, shot):
    """Open the Start Center's Trợ giúp menu (4th menubar label), screenshot, close it."""
    xdo(office, "windowraise", wid)
    xdo(office, "mousemove", "--window", wid, "193", "14", "click", "1")
    time.sleep(1.5)
    hst_gui.screenshot(shot, office.display)
    xdo(office, "key", "Escape")
    time.sleep(0.5)


def ribbon_menu_items(office, module):
    """(command, label) of the ribbon's ≡ menu as this office loaded it (popupmenu/notebookbar)."""
    supplier = office.service("com.sun.star.ui.ModuleUIConfigurationManagerSupplier")
    settings = supplier.getUIConfigurationManager(MODULES[module]).getSettings("private:resource/popupmenu/notebookbar",
                                                                             False)
    items = []
    for index in range(settings.getCount()):
        props = {p.Name: p.Value for p in settings.getByIndex(index)}
        items.append((props.get("CommandURL", ""), props.get("Label", "")))
    return items


def open_ribbon_menu(office, wid, shot):
    """Click the ≡ button at the right end of the ribbon tab row, screenshot, close with Escape."""
    width, _height = size(office.display, wid)
    xdo(office, "windowraise", wid)
    xdo(office, "mousemove", "--window", wid, str(width - 27), "23", "click", "1")
    time.sleep(1.5)
    hst_gui.screenshot(shot, office.display)
    xdo(office, "key", "Escape")
    time.sleep(0.5)


def dialog(office, small=False):
    """Window id of the report dialog (or, small=True, of the message box on top of it, 260 units wide)."""
    def find():
        found = sorted(windows(office, "^" + TITLE + "$"), key=lambda w: size(office.display, w[0])[0])
        if small:
            return found[0][0] if len(found) > 1 or (found and size(office.display, found[0][0])[1] < 300) else None
        return found[-1][0] if found else None
    return wait(find, 20)


def click_message_button(office, wid):
    """The right-hand button of an HST message box (Đồng ý / Đóng)."""
    width, height = size(office.display, wid)
    scale = width / 260
    click(office, wid, 217, height / scale - 15, (260, height / scale))


def shot(office, wid, path):
    """Screenshot with `wid` on top (the welcome dialog of a fresh profile may be up as well)."""
    if wid:  # raising every window would put the welcome dialog of the test profile on top
        xdo(office, "windowraise", wid)
        time.sleep(0.4)
    else:
        office.raise_windows()
    hst_gui.screenshot(path, office.display)
