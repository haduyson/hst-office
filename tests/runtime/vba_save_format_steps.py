# SPDX-License-Identifier: AGPL-3.0-only
"""Steps of check-vba-save-format.py: saving a Writer document that gained VBA macros."""
import os
import subprocess
import threading
import zipfile

import msoffice_save_steps as steps
from hst_office import vba
from shortcut_keys import check, wait

WARNING_TITLE = "Lưu tài liệu có macro"
EXTENSIONS = (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".odt", ".ods", ".odp")


def add_vba(doc, app):
    vba.prepare_document(doc, app)


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


def saved_as(path):
    return [ext for ext in EXTENSIONS if os.path.exists(path + ext)]


def has_vba_project(path):
    with zipfile.ZipFile(path) as package:
        return any(name.endswith("vbaProject.bin") for name in package.namelist())


def warning_window(keys):
    for wid, name in keys.windows():
        if name == WARNING_TITLE:
            return wid
    return None


def press(keys, wid, *names):
    subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", *names], env=keys.env, check=False, timeout=15)


def type_name(keys, picker, path):
    subprocess.run(["xdotool", "windowfocus", "--sync", picker, "key", "ctrl+a", "type", "--delay", "20", path],
                   env=keys.env, check=False, timeout=60)
    press(keys, picker, "Return")


def open_with_new_macro(office, keys, url):
    doc = office.load(url)
    steps.focus_document(office, keys)
    add_vba(doc, "writer")
    steps._touch(doc)
    office.raise_windows()
    keys.send("ctrl+s")
    return doc, wait(lambda: warning_window(keys) is not None, 10)


def check_open_docx(office, keys, files):
    """A .docx on disk that gains a macro."""
    import uno
    source = os.path.join(files, "co-san.docx")
    url = uno.systemPathToFileUrl(source)
    doc = office.load("private:factory/swriter", hidden=True)
    doc.storeToURL(url, (pv("FilterName", "MS Word 2007 XML"),))
    doc.close(True)
    doc, warned = open_with_new_macro(office, keys, url)
    check("open .docx with a new macro: Ctrl+S warns", warned, str(keys.windows()))
    if warned:
        before = {w for w, _ in keys.windows()}
        press(keys, warning_window(keys), "Escape")
        picker = []
        wait(lambda: picker.extend(w for w, _ in keys.windows() if w not in before) or picker, 10)
        check("open .docx: going back opens Save As", bool(picker), str(keys.windows()))
        if picker:
            path = os.path.join(files, "tu-docx")
            type_name(keys, picker[0], path)
            check("open .docx: Save As proposes .docm", wait(lambda: saved_as(path) == [".docm"], 15), str(saved_as(path)))
    steps.close(doc)
    doc, warned = open_with_new_macro(office, keys, url)
    if warned:
        press(keys, warning_window(keys), "shift+Tab", "Return")  # the button that is not the default
        check("open .docx: Save without Macros saves", wait(lambda: not doc.isModified(), 15), str(keys.windows()))
    check("open .docx: the .docx has no VBA project", not has_vba_project(source))
    steps.close(doc)


def check_named_file(office, keys, files):
    """Save As with the file and format already chosen: there is no dialog to go back to."""
    import uno
    doc = office.load("private:factory/swriter")
    wait(lambda: keys.doc_window() is not None, 20)
    add_vba(doc, "writer")
    path = os.path.join(files, "dich.docx")
    args = (pv("URL", uno.systemPathToFileUrl(path)), pv("FilterName", "MS Word 2007 XML"))
    frame = doc.getCurrentController().getFrame()
    thread = threading.Thread(target=lambda: office.dispatch(frame, ".uno:SaveAs", args), daemon=True)
    thread.start()
    warned = wait(lambda: warning_window(keys) is not None, 15)
    check("named .docx file: warns", warned, str(keys.windows()))
    if warned:
        press(keys, warning_window(keys), "Escape")
    thread.join(15)
    check("named .docx file: going back writes nothing", not os.path.exists(path))
    steps.close(doc)
