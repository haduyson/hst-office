# SPDX-License-Identifier: AGPL-3.0-only
"""Open every citation dialog in a real HST Writer window, keep a screenshot, cancel it, and check the document did
not change; then type "[1, tr. 5" and press Alt+Shift+I in the document window.

Usage: python3 tests/runtime/check-citations-dialogs.py --instdir DIR --display :N [--out DIR]   (Linux: an X
         display such as Xvfb, with xdotool and ImageMagick's import; citations_dialogs_x11.py)
       python.exe tests/runtime/check-citations-dialogs.py --instdir DIR --windows [--out DIR]   (Windows: in the
         tester's own session, e.g. through citations-dialogs-own-session.ps1; citations_dialogs_win32.py)

Dialogs: Chèn trích dẫn, Nguồn tài liệu mới (from Quản lý tài liệu tham khảo ▸ Thêm…), Chèn lại trích dẫn,
Kiểu trích dẫn, Quản lý tài liệu tham khảo, and the message of Cập nhật trích dẫn. Each is found by its title in the
UI language, must fit a 1366×768 screen, and Esc (Enter for the message) must leave the citations as they were.
"""
import argparse
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from citations_runtime_office import Recorder, run_office  # noqa: E402

EXTENSION = os.path.join("share", "extensions", "hst-vietnamese-tools", "python")
A = {"id": "a", "type": "book", "title": "Giáo trình kinh tế", "language": "vi", "publisher": "Giáo dục",
     "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}], "issued": {"date-parts": [[2010]]}}


def snapshot(doc, document):
    return [(f["code"], f["result"]) for f in document.scan(doc)]


def open_dialog(rec, ctx, doc, driver, out, command, title, steps=(), close="Escape"):
    """Dispatch ``command`` in a thread, find the dialog titled ``title``, screenshot it, run the extra key
    ``steps`` (each (keys, title of the next dialog)), then close every opened dialog."""
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    frame = doc.getCurrentController().getFrame()
    worker = threading.Thread(target=lambda: helper.executeDispatch(frame, "org.hst.office.vi:" + command, "", 0, ()),
                              daemon=True)
    worker.start()
    opened = []
    for keys, name in ((None, title),) + tuple(steps):
        if keys:
            driver.keys(opened[-1], *keys)
        window = driver.wait_window(name)
        rec.check("opens-%s" % name, window is not None, name)
        if window is None:
            break
        time.sleep(1.0)
        size = driver.size(window)
        rec.check("fits-1366x768-%s" % name, 0 < size[0] <= 1366 and 0 < size[1] <= 740, size)
        shot = command + ("-%d" % (len(opened) + 1) if opened else "") + ".png"
        driver.screenshot(window, os.path.join(out, shot))
        opened.append(window)
    for window in reversed(opened):
        driver.keys(window, close)
        time.sleep(1.0)
    worker.join(30)
    rec.check("closes-%s" % title, not worker.is_alive(), title)


def shortcut(rec, ctx, doc, driver, document):
    """Type "[1, tr. 5" in the document window and press Alt+Shift+I: a citation of source 1 replaces it."""
    view = doc.getCurrentController().getViewCursor()
    view.gotoEnd(False)
    doc.getText().insertString(view, " và [1, tr. 5", False)
    view.gotoEnd(False)
    driver.keys(driver.document_window(), "alt+shift+i")
    time.sleep(3)
    results = [f["result"] for f in document.scan(doc) if f["kind"] == "citation"]
    rec.check("alt-shift-i-cites-typed-number", results == ["[1]", "[1, tr. 5]"] and "[1, tr. 5" not in
              doc.getText().getString().replace("[1, tr. 5]", ""), results)
    doc.getUndoManager().undo()


def run_checks(ctx, out, instdir, driver):
    sys.path.insert(0, os.path.join(os.path.abspath(instdir), EXTENSION))
    from hst_office import citation_codes, citation_document as document, citation_refresh, citation_settings
    from hst_office import citation_texts
    rec = Recorder()
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    texts = citation_texts.load(ctx)
    try:
        citation_settings.write(doc, {"style": "vn-so", "preset": None, "opts": {}})
        import uno
        locale = uno.createUnoStruct("com.sun.star.lang.Locale")
        locale.Language, locale.Country = "vi", "VN"  # a Vietnamese thesis
        doc.getStyleFamilies().getByName("ParagraphStyles").getByName("Standard").CharLocale = locale
        doc.getText().setString("Theo nghiên cứu ")
        view = doc.getCurrentController().getViewCursor()
        view.gotoEnd(False)
        code = citation_codes.encode_citation({"citationID": "", "items": [{"id": "a"}]}, {"a": A})
        document.insert_field(ctx, doc, code, "[?]")
        citation_refresh.refresh(ctx, doc, "test", "—")
        view.gotoEnd(False)
        before = snapshot(doc, document)
        rec.info("ui-language", texts["language"])
        open_dialog(rec, ctx, doc, driver, out, "CitationInsert", texts["insert"]["title"])
        open_dialog(rec, ctx, doc, driver, out, "CitationReinsert", texts["reinsert"]["title"])
        open_dialog(rec, ctx, doc, driver, out, "CitationStyle", texts["style"]["title"])
        open_dialog(rec, ctx, doc, driver, out, "CitationLibrary", texts["library"]["title"],
                    steps=((("Tab", "Tab", "Tab", "space"), texts["entry"]["titleNew"]),))
        open_dialog(rec, ctx, doc, driver, out, "CitationUpdate", texts["common"]["title"], close="Return")
        after = snapshot(doc, document)
        shortcut(rec, ctx, doc, driver, document)
        rec.check("cancel-changes-nothing", [r for _c, r in after] == [r for _c, r in before]
                  and len(after) == len(before), {"before": before[:1], "after": after[:1]})
    finally:
        doc.setModified(False)
        doc.close(True)
    return rec.results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/citations-dialogs"))
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--display", help="X display with no other windows, e.g. :99 (Xvfb)")
    where.add_argument("--windows", action="store_true", help="this Windows session (the tester's own)")
    args = parser.parse_args()
    if args.windows:
        from citations_dialogs_win32 import Win32Driver
        driver = Win32Driver()
    else:
        from citations_dialogs_x11 import X11Driver
        driver = X11Driver(args.display)
    return run_office(args.instdir, args.out, lambda ctx, out: run_checks(ctx, out, args.instdir, driver),
                      display=args.display, windowed=args.windows)


if __name__ == "__main__":
    sys.exit(main())
