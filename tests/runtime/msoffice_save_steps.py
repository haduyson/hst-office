# SPDX-License-Identifier: AGPL-3.0-only
"""Steps of check-msoffice-save-format.py: configuration, first save, later saves, helpers."""
import os
import re
import subprocess
import sys
import time
import zipfile

import hst_gui
from shortcut_keys import check, wait

EXT_DIR = "share/extensions/hst-vietnamese-tools"
FACTORIES = {
    "com.sun.star.text.TextDocument": "MS Word 2007 XML",
    "com.sun.star.sheet.SpreadsheetDocument": "Calc MS Excel 2007 XML",
    "com.sun.star.presentation.PresentationDocument": "Impress MS PowerPoint 2007 XML",
}
ND30_FIELDS = {"agency": "[Cơ quan thử nghiệm]", "number": "5", "symbol": "qđ-ubnd", "place": "[Địa danh]",
               "date": "2026-02-05", "summary": "Về việc ban hành quy chế", "body": "Điều 1. Nội dung một.",
               "signerAuthority": "TM. [Cơ quan]", "signerName": "[Họ và tên]", "recipients": "- Lưu: VT."}


def config_checks(office):
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")

    def read(node, key):
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", node
        return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,)).getByName(key)

    for factory, expected in FACTORIES.items():
        value = read(f"/org.openoffice.Setup/Office/Factories/{factory}", "ooSetupFactoryDefaultFilter")
        check(f"default filter of {factory.rsplit('.', 1)[1]} is {expected}", value == expected, value)
    check("Keep-format warning stays on for legacy formats",
          read("/org.openoffice.Office.Common/Save/Document", "WarnAlienFormat") is True)


def insert_nd30(office, doc, instdir):
    """Run the bundled extension's ND 30 layout code (as the wizard does) into `doc`."""
    sys.path.insert(0, os.path.join(instdir, EXT_DIR, "python"))
    from hst_office import nd30_layout, nd30_writer
    layout = nd30_layout.build_layout("quyet-dinh", ND30_FIELDS)
    cursor = doc.getCurrentController().getViewCursor()
    return nd30_writer.insert_layout(doc, cursor, layout, apply_page=True, page_numbers=True)


def first_save(office, keys, doc, path, ext, name):
    """Ctrl+S on a new document: the file dialog, then nothing else; the file is OOXML."""
    before = {w for w, _ in keys.windows()}
    picker = keys.dialog_after("ctrl+s")
    check(f"{name}: Ctrl+S opens the file dialog", picker is not None, f"windows={keys.windows()} doc={keys.doc_window()}")
    if not picker:
        office.screenshot(os.path.join(office.workdir, "no-dialog.png"))
        return False
    subprocess.run(["xdotool", "windowfocus", "--sync", picker[0], "key", "ctrl+a", "type", "--delay", "20", path],
                   env=keys.env, check=False, timeout=60)
    subprocess.run(["xdotool", "windowfocus", "--sync", picker[0], "key", "Return"], env=keys.env, check=False, timeout=15)
    saved = wait(lambda: doc.hasLocation() and not doc.isModified(), 20)
    extra = [n for w, n in keys.windows() if w not in before]
    url = doc.getURL() if doc.hasLocation() else ""
    check(f"{name}: saved as {ext} with no other question", saved and url.endswith(ext) and not extra, f"{url} {extra}")
    for wid, _n in [(w, n) for w, n in keys.windows() if w not in before]:
        keys.close_dialog(wid)
    target = path + ext
    try:
        with zipfile.ZipFile(target) as package:
            ok = "[Content_Types].xml" in package.namelist()
    except (OSError, zipfile.BadZipFile):
        ok = False
    check(f"{name}: {os.path.basename(target)} is an Office Open XML package", ok)
    return saved


def _untitled_dialogs(keys):
    """The keep-format question has no window title and opens behind the document window here
    (no window manager): hst_gui.toplevels skips it. Its id, as listed by xwininfo."""
    out = subprocess.run(["xwininfo", "-display", keys.office.display, "-root", "-children"],
                         capture_output=True, text=True).stdout
    return [m.group(1) for m in re.finditer(r'(0x[0-9a-f]+) \(has no name\): \("soffice"', out)
            if hst_gui.window_pid(m.group(1), keys.office.display) == keys.office.pid]


def resave(office, keys, doc, name, expect_question):
    """Edit, Ctrl+S: OOXML saves silently, legacy formats ask whether to keep the format."""
    _touch(doc)
    office.raise_windows()
    if expect_question:
        known = set(_untitled_dialogs(keys))
        keys.send("ctrl+s")
        found = []
        wait(lambda: found.extend(w for w in _untitled_dialogs(keys) if w not in known) or found, 10)
        check(f"{name}: Ctrl+S asks to keep the legacy format", bool(found))
        before = {w for w, _ in keys.windows()}
        for wid in found:
            subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Escape"], env=keys.env, check=False, timeout=15)
        # Escape on the question leads to the Save As dialog: close that too
        extra = lambda: [w for w, _n in keys.windows() if w not in before]  # noqa: E731
        wait(extra, 15)
        for wid in extra():
            keys.close_dialog(wid)
        doc.setModified(False)
        return
    found = keys.dialog_after("ctrl+s", timeout=8)
    check(f"{name}: Ctrl+S saves again with no dialog", found is None and wait(lambda: not doc.isModified(), 10),
          f"dialog={found}")
    if found:
        keys.close_dialog(found[0])


def _touch(doc):
    if doc.supportsService("com.sun.star.text.TextDocument"):
        doc.getText().getEnd().setString(" (sửa)")
    elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        doc.getSheets().getByIndex(0).getCellByPosition(20, 0).setString("sửa")
    else:
        doc.getDrawPages().getByIndex(0).Name = "sua"
    doc.setModified(True)


def focus_document(office, keys):
    """A document opened from a URL over UNO has no input focus in its edit window until clicked."""
    time.sleep(4)
    office.raise_windows()
    subprocess.run(["xdotool", "mousemove", "700", "500", "click", "1"], env=keys.env, check=False, timeout=15)
    time.sleep(1)


def close(doc):
    """Close, retrying while the document is busy (the close veto of hst-sw-clipboard-close-race.patch)."""
    last = None
    for _ in range(40):
        try:
            doc.setModified(False)
            doc.close(True)
            return
        except Exception as error:  # noqa: BLE001 - UNO exceptions: a veto hands over ownership
            if "Disposed" in type(error).__name__:  # closed by the store that vetoed the close
                return
            last = error
            time.sleep(1)
    raise RuntimeError(f"document stays busy: {last!r}")


def store_legacy(doc, path, filter_name):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", filter_name
    doc.storeAsURL("file://" + path, (arg,))


def _ooxml_page(path):
    """(width, height, top, bottom, left, right) in mm of the last section of a .docx."""
    with zipfile.ZipFile(path) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    size = re.findall(r'<w:pgSz [^>]*w:w="(\d+)"[^>]*w:h="(\d+)"', xml)[-1]
    margin = re.findall(r'<w:pgMar ([^>]*)/>', xml)[-1]
    side = lambda name: int(re.search(rf'w:{name}="(\d+)"', margin).group(1))  # noqa: E731
    twips = [int(size[0]), int(size[1]), side("top"), side("bottom"), side("left"), side("right")]
    return tuple(round(v * 25.4 / 1440) for v in twips)


def template(instdir, rel):
    return "file://" + os.path.join(os.path.abspath(instdir), EXT_DIR, "template", rel)


def load_template(office, url):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "AsTemplate", True
    return office.desktop().loadComponentFromURL(url, "_blank", 0, (arg,))
