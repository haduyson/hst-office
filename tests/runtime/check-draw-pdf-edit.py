#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Edit a PDF in HST Draw with the HST ribbon (gtk3, vi_VN), the way users do from HST PDF.

Usage: python3 tests/runtime/check-draw-pdf-edit.py [--instdir DIR] [--display :71] [--out DIR]

A two-page PDF made by HST Office itself (pdf_samples) opens in HST PDF; "Chỉnh sửa bằng HST Draw"
(.uno:HSTPdfEditInDraw) hands it to HST Draw. Then, with the Draw window 1485 x 900:
  - the HST ribbon shows, with Draw's tabs in order (Tệp tin, Trang đầu, Chèn, Sắp xếp, Trang, Xem,
    Xuất/PDF, Xem lại, Trợ giúp, Phần mở rộng), and nothing of Trang đầu is folded into "»";
  - a text box of the PDF is edited by keyboard (selected, F2, End, typed);
  - the drawing is exported to PDF and saved as .odg, and the exported PDF holds the edit (pdftotext);
  - Xuất/PDF ▸ "Mở trong HST PDF" (org.hst.office.vi:OpenInHstPdf) shows the edited drawing in HST PDF.
The display must already run. Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json
and draw-1485.png. Exit 1 on a failed check.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import pdf_samples  # noqa: E402
import pdf_viewer_uno  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

_spec = importlib.util.spec_from_file_location("home_fit", os.path.join(HERE, "check-ribbon-home-fit.py"))
home_fit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(home_fit)

PORT = 7436
WIDTH, HEIGHT = 1485, 900
TABS = ["Tệp tin", "Trang đầu", "Chèn", "Sắp xếp", "Trang", "Xem", "Xuất/PDF", "Xem lại", "Trợ giúp", "Phần mở rộng"]
MARK, EDIT = "HSTPDF-1", " SUA-OK"
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:240]}", flush=True)
    return ok


def components(office, service):
    found, enum = [], office.desktop().getComponents().createEnumeration()
    while enum.hasMoreElements():
        item = enum.nextElement()
        if hasattr(item, "supportsService") and item.supportsService(service):
            found.append(item)
    return found


def wait(predicate, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(1)
    return None


def viewer_frames(office):
    frames = office.desktop().getFrames()
    return [frames.getByIndex(i) for i in range(frames.getCount())
            if getattr(frames.getByIndex(i).getController(), "ImplementationName", "") == pdf_viewer_uno.VIEWER]


def open_in_draw(office, sample):
    """HST PDF, then Chỉnh sửa bằng HST Draw: the Draw document of the PDF."""
    frame, _ = pdf_viewer_uno.open_viewer(office, sample)
    threading.Thread(target=office.dispatch, args=(frame, ".uno:HSTPdfEditInDraw"), daemon=True).start()
    return wait(lambda: next(iter(components(office, "com.sun.star.drawing.DrawingDocument")), None), 120)


def text_shape(draw, mark):
    page = draw.getDrawPages().getByIndex(0)
    for i in range(page.getCount()):
        shape = page.getByIndex(i)
        if hasattr(shape, "getString") and mark in shape.getString():
            return shape
    return None


def edit_by_keyboard(args, draw, shape):
    controller = draw.getCurrentController()
    controller.select(shape)
    time.sleep(1)
    for key in ("F2", "End"):
        gui.xdo(args.display, "key", key)
        time.sleep(0.5)
    gui.xdo(args.display, "type", "--delay", "60", EDIT)
    time.sleep(1)
    gui.xdo(args.display, "key", "Escape")
    time.sleep(1)
    return shape.getString()


def store(draw, path, filter_name):
    import uno
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = "FilterName", filter_name
    draw.storeToURL(uno.systemPathToFileUrl(path), (prop,))
    return os.path.isfile(path) and os.path.getsize(path) > 0


def pdf_text(path):
    run = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=60)
    return run.stdout if run.returncode == 0 else ""


def check(args, office, sample):
    draw = open_in_draw(office, sample)
    if not record("Chỉnh sửa bằng HST Draw opens the PDF in HST Draw", draw is not None):
        return
    frame = draw.getCurrentController().getFrame()
    window = wait(lambda: next((w for w, name in hst_gui.toplevels(args.display, office.pid) if "HST Draw" in name), None), 60)
    record("the window title names HST Draw", window is not None, [n for _w, n in hst_gui.toplevels(args.display, office.pid)])
    if window is None:
        return
    gui.xdo(args.display, "windowmove", window, "0", "0")
    gui.xdo(args.display, "windowsize", window, str(WIDTH), str(HEIGHT))
    time.sleep(5)

    names = wait(lambda: gui.visible_names() or None, 30) or []
    record(f"[{WIDTH}] the HST ribbon shows Draw's tabs in order", [n for n in names if n in TABS] == TABS, names)
    home = next((t for t in gui.ribbon_tabs() if t[0] == "Trang đầu"), None)
    if home and not home[2]:
        gui.click(args.display, home[1])
        time.sleep(2)
    chevron = home_fit.overflow_shown()
    record(f"[{WIDTH}] nothing of Trang đầu is folded into »", chevron is None, chevron)
    office.screenshot(os.path.join(args.out, f"draw-{WIDTH}.png"))

    shape = text_shape(draw, MARK)
    if not record("the PDF's text is in text boxes", shape is not None, MARK):
        return
    text = edit_by_keyboard(args, draw, shape)
    record("a text box is edited by keyboard", EDIT.strip() in text and draw.isModified(), text[:120])

    exported, saved = os.path.join(args.out, "edited.pdf"), os.path.join(args.out, "edited.odg")
    record("the drawing exports to PDF", store(draw, exported, "draw_pdf_Export"), exported)
    record("the exported PDF holds the edit", EDIT.strip() in pdf_text(exported), exported)
    record("the drawing saves as .odg", store(draw, saved, "draw8"), saved)

    before = len(viewer_frames(office))
    threading.Thread(target=office.dispatch, args=(frame, "org.hst.office.vi:OpenInHstPdf"), daemon=True).start()
    viewer = wait(lambda: len(viewer_frames(office)) > before, 60)
    record("Mở trong HST PDF shows the edited drawing in HST PDF", bool(viewer))
    for viewer_frame in viewer_frames(office):
        viewer_frame.close(True)
    draw.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/draw-pdf-edit"))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    sample = pdf_samples.make(args.instdir, os.path.join(args.out, "sample.pdf"), 2)  # made as the build user
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False, stderr=subprocess.DEVNULL)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "office"), PORT, display=args.display).start()
    try:
        check(args, office, sample)
    except Exception as error:  # noqa: BLE001 - a crash is a failed check, with its reason
        record("the check ran to the end", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"checks": ROWS}, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
