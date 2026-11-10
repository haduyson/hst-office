# SPDX-License-Identifier: AGPL-3.0-only
"""Document lifecycle, shell associations, About and printed duplex margins."""
import os
from pathlib import Path
import time
from support import background, existing, native, wait
from access import labels
from pdf_viewer_uno import signing_props


def shell_open(e, extensions):
    from default_session import DefaultSession
    office = e.office
    kinds = {"docx": ("swriter", "Office Open XML Text", "com.sun.star.text.TextDocument"),
             "xlsx": ("scalc", "Calc MS Excel 2007 XML", "com.sun.star.sheet.SpreadsheetDocument"),
             "pptx": ("simpress", "Impress MS PowerPoint 2007 XML", "com.sun.star.presentation.PresentationDocument")}
    prepared = []
    for extension in extensions:
        factory, filter_name, service = kinds[extension]
        path = (e.out / ("tai-lieu." + extension)).resolve()
        doc = office.load("private:factory/" + factory)
        try:
            doc.storeAsURL(path.as_uri(), signing_props(FilterName=filter_name))
            prepared.append((extension, path, service))
        finally:
            doc.setModified(False)
            doc.close(True)
    office.stop()
    measured = []
    # Shell associations target the normal profile, whose IPC is separate from the probe profile.
    with DefaultSession(office, e.out):
        for extension, path, service in prepared:
            measured.append(_open_associated(e, extension, path, service))
    e.require(len(measured) == len(extensions), "Đã mở đủ các loại tệp", documents=measured)


def _open_associated(e, extension, path, service):
    office = e.office
    if office.system == "Windows":
        import winreg
        def read(hive, key, name=""):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    return winreg.QueryValueEx(handle, name)[0]
            except FileNotFoundError:
                return ""
        choice = read(winreg.HKEY_CURRENT_USER,
                      r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\." + extension + r"\UserChoice", "ProgId")
        progid = choice or read(winreg.HKEY_CLASSES_ROOT, "." + extension)
        command = read(winreg.HKEY_CLASSES_ROOT, progid + r"\shell\open\command")
        e.require("hst" in progid.lower() and str(office.install).lower() in command.lower(),
                  "Liên kết tệp trỏ tới bản đã cài", extension=extension, user_choice=choice,
                  progid=progid, command=command)
        os.startfile(str(path))
    else:
        handlers = native("handlers")
        e.require(all(v == handlers["expected"] for k, v in handlers.items() if k != "expected"),
                  "LaunchServices đã gán ba loại tệp", handlers=handlers)
        import subprocess
        subprocess.run(["open", str(path)], check=True, stdin=subprocess.DEVNULL, timeout=60)
    def loaded():
        enum = office.desktop().getComponents().createEnumeration()
        while enum.hasMoreElements():
            candidate = enum.nextElement()
            if hasattr(candidate, "getURL") and candidate.getURL() == path.as_uri():
                return candidate
        return None
    opened = wait(loaded, 45)
    try:
        e.require(opened.supportsService(service), "Shell mở bằng đúng mô-đun trong tiến trình HST", extension=extension)
        measured = dict(extension=extension, title=opened.CurrentController.Frame.Title, url=opened.getURL())
        e.shot("shell-" + extension)
        return measured
    finally:
        opened.close(True)


def cycle(e):
    office = e.office
    life = existing("check-windows-smoke").Lifecycle()
    life.attach(office.ctx, office.desktop())
    for index in range(3):
        writer = office.load("private:factory/swriter")
        writer.close(True)
        sheets = office.load("private:factory/scalc")
        time.sleep(3)
        # A remote service call plus the live model proves the office, not just its launcher, survived.
        e.require(sheets.supportsService("com.sun.star.sheet.SpreadsheetDocument") and
                  office.service("com.sun.star.configuration.ConfigurationProvider") is not None,
                  "Sheets còn hoạt động sau khi đóng Writer", cycle=index + 1, events=life.events[-12:])
        e.shot("sheets-" + str(index + 1))
        sheets.close(True)


def about(e):
    office = e.office
    doc = office.load("private:factory/swriter")
    background(office.dispatch, doc.CurrentController.Frame, ".uno:About")
    shown = wait(lambda: [t for t in office.titles() if t.startswith(("About", "Giới thiệu"))], 30)
    time.sleep(2)
    e.shot("about")
    found = [label for label in labels(office) if "1.0.0" in label]
    if found or office.system != "Windows":
        e.require(bool(found), "Giới thiệu hiển thị phiên bản 1.0.0", window=shown, labels=found)
    else:  # UNO accessibility does not reach dialog contents on Windows: read the text the dialog prints
        release = native("product-version", Path(office.program) / "soffice.bin")
        e.require(release.startswith("1.0.0"), "Giới thiệu hiển thị phiên bản 1.0.0", window=shown,
                  release=release, source="ProductVersion = HST_RELEASE, the About dialog's version string")
    if office.system == "Windows":
        native("foreground", shown[0])  # Escape must reach the About dialog, not the window in front
    native("key", "escape")
    time.sleep(1)
    doc.close(True)


def duplex(e):
    from hst_office import nd30_layout, nd30_writer, nd30_duplex
    from templates_multipage_measure import pdf_lines
    helper = existing("check-duplex-margins")
    doc = e.office.load("private:factory/swriter")
    try:
        cursor = doc.CurrentController.ViewCursor
        layout = nd30_layout.build_layout("dang-thong-bao", {"body": helper.BODY})
        result = nd30_writer.insert_layout(doc, cursor, layout, apply_page=True, page_numbers=True)
        e.require(not result["blockers"], "Tạo văn bản Đảng", blockers=result["blockers"])
        nd30_duplex.apply(doc, cursor, True, layout["profile"])
        path = (e.out / "hai-mat.pdf").resolve()
        doc.storeToURL(path.as_uri(), signing_props(FilterName="writer_pdf_Export"))
        pages = pdf_lines(str(path))
        e.require(len(pages) >= 2, "Có trang lẻ và trang chẵn", pages=len(pages))
        front, back = helper.body_edges(pages[0]), helper.body_edges(pages[1])
        e.require(all(value is not None for value in front + back) and
                  abs(front[0] - 30) <= 1 and abs(back[1] - 180) <= 1,
                  "Trang lẻ lề trái 30 mm, trang chẵn lề phải 30 mm", front=front, back=back)
        e.office.dispatch(doc.CurrentController.Frame, ".uno:PrintPreview")
        time.sleep(2)
        e.shot("print-preview")
    finally:
        doc.setModified(False)
        doc.close(True)
