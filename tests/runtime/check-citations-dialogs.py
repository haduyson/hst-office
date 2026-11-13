# SPDX-License-Identifier: AGPL-3.0-only
"""Open every citation dialog in a real HST Writer window, keep a screenshot, cancel it, and check the document did
not change (Linux, X display such as Xvfb; needs xdotool and ImageMagick's import).

Usage: python3 tests/runtime/check-citations-dialogs.py --instdir DIR --display :N [--out DIR]

Dialogs: Chèn trích dẫn, Nguồn tài liệu mới (from Quản lý tài liệu tham khảo ▸ Thêm…), Chèn lại trích dẫn,
Kiểu trích dẫn, Quản lý tài liệu tham khảo, and the message of Cập nhật trích dẫn. Each is found by its title in the
UI language, must fit a 1366×768 screen, and Esc (Enter for the message) must leave the citations as they were.
"""
import argparse
import os
import subprocess
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


def xdotool(display, *args):
    return subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), capture_output=True,
                          text=True, timeout=60)


def wait_window(display, title, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = xdotool(display, "search", "--onlyvisible", "--name", "^%s$" % title).stdout.split()
        if found:
            return found[-1]
        time.sleep(0.5)
    return None


def geometry(display, window):
    values = dict(line.split("=", 1) for line in
                  xdotool(display, "getwindowgeometry", "--shell", window).stdout.split() if "=" in line)
    return int(values.get("WIDTH", 0)), int(values.get("HEIGHT", 0))


def snapshot(doc, document):
    return [(f["code"], f["result"]) for f in document.scan(doc)]


def open_dialog(rec, ctx, doc, display, out, command, title, steps=(), close="Escape"):
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
            xdotool(display, "windowfocus", "--sync", opened[-1])
            xdotool(display, "key", "--delay", "120", *keys)
        window = wait_window(display, name)
        rec.check("opens-%s" % name, window is not None, name)
        if window is None:
            break
        time.sleep(1.0)
        size = geometry(display, window)
        rec.check("fits-1366x768-%s" % name, 0 < size[0] <= 1366 and 0 < size[1] <= 740, size)
        shot = command + ("-%d" % (len(opened) + 1) if opened else "") + ".png"
        subprocess.run(["import", "-window", window, os.path.join(out, shot)],
                       env=dict(os.environ, DISPLAY=display), check=False, timeout=60)
        opened.append(window)
    for window in reversed(opened):
        xdotool(display, "windowfocus", "--sync", window)
        xdotool(display, "key", close)
        time.sleep(1.0)
    worker.join(30)
    rec.check("closes-%s" % title, not worker.is_alive(), title)


def run_checks(ctx, out, instdir, display):
    sys.path.insert(0, os.path.join(os.path.abspath(instdir), EXTENSION))
    from hst_office import citation_codes, citation_document as document, citation_refresh, citation_settings
    from hst_office import citation_texts
    rec = Recorder()
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    texts = citation_texts.load(ctx)
    try:
        citation_settings.write(doc, {"style": "vn-so", "preset": None, "opts": {}})
        doc.getText().setString("Theo nghiên cứu ")
        view = doc.getCurrentController().getViewCursor()
        view.gotoEnd(False)
        code = citation_codes.encode_citation({"citationID": "", "items": [{"id": "a"}]}, {"a": A})
        document.insert_field(ctx, doc, code, "[?]")
        citation_refresh.refresh(ctx, doc, "test", "—")
        view.gotoEnd(False)
        before = snapshot(doc, document)
        rec.info("ui-language", texts["language"])
        open_dialog(rec, ctx, doc, display, out, "CitationInsert", texts["insert"]["title"])
        open_dialog(rec, ctx, doc, display, out, "CitationReinsert", texts["reinsert"]["title"])
        open_dialog(rec, ctx, doc, display, out, "CitationStyle", texts["style"]["title"])
        open_dialog(rec, ctx, doc, display, out, "CitationLibrary", texts["library"]["title"],
                    steps=((("Tab", "Tab", "Tab", "space"), texts["entry"]["titleNew"]),))
        open_dialog(rec, ctx, doc, display, out, "CitationUpdate", texts["common"]["title"], close="Return")
        after = snapshot(doc, document)
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
    parser.add_argument("--display", required=True, help="X display with no other windows, e.g. :99 (Xvfb)")
    args = parser.parse_args()
    return run_office(args.instdir, args.out, lambda ctx, out: run_checks(ctx, out, args.instdir, args.display),
                      display=args.display)


if __name__ == "__main__":
    sys.exit(main())
