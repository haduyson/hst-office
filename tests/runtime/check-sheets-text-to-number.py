# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of "Chuyển thành số" (hst-sheets-text-to-number*.patch) against an installed HST Office.

Usage (run with the office's own Python, the Xvfb display must already run; it is never started or stopped here):
    <instdir>/program/python tests/runtime/check-sheets-text-to-number.py --instdir <instdir> --out <dir>
        [--display :95] [--rows 100000]

Checks: green triangles drawn (pixels), warning button shown left of the cell cursor and its menu (click, screenshot,
"Bỏ qua lỗi" by its access key), the command on a selection (values, kept text, formats) in one undo step, the
option turning the marks off, "Bỏ qua lỗi" surviving .xlsx and .ods round trips (and <ignoredErrors> in the xlsx), and
the time to paint and convert --rows cells. Pixel counts use the system python3 with PIL (screenshots by ImageMagick).
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

ROWS = []
GREEN, YELLOW = (0x00, 0x80, 0x00), (0xFF, 0xC8, 0x3D)
TEXTS = ["1.234.567", "15%", "1.000.000 đ", "(1.000)", "1.234,5", "0905123456", "abc", "1,234,567.89"]


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def pixels(path, colour):
    """(count, first x, first y) of exact `colour` pixels in a screenshot, via the system python3 with PIL."""
    code = ("import sys;from PIL import Image;im=Image.open(sys.argv[1]).convert('RGB');c=tuple(map(int,sys.argv[2:]));"
            "w,h=im.size;d=im.load();p=[(x,y) for y in range(h) for x in range(w) if d[x,y]==c];"
            "print(len(p),*(p[0] if p else (-1,-1)))")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}  # not the office's own Python
    out = subprocess.run(["/usr/bin/python3", "-I", "-c", code, path, *map(str, colour)], capture_output=True, text=True,
                         env=env).stdout.split()
    return tuple(int(v) for v in out) if len(out) == 3 else (0, -1, -1)


def shot(office, args, name, wait=1.5):
    time.sleep(wait)
    path = os.path.join(args.out, name)
    hst_gui.screenshot(path, args.display)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--display", default=":95")
    ap.add_argument("--rows", type=int, default=100000)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work"), 22195, display=args.display).start()
    try:
        run(office, args)
    finally:
        office.stop()
    failed = [n for n, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    sys.exit(1 if failed else 0)


def run(office, args):
    import uno
    doc = office.load("private:factory/scalc")
    frame = doc.getCurrentController().getFrame()
    frame.getContainerWindow().setPosSize(0, 0, 1600, 1000, 15)
    sheet = doc.Sheets.getByIndex(0)
    for row, text in enumerate(TEXTS):
        sheet.getCellByPosition(2, row + 1).setString(text)  # C2:C9, strings
    # UNO setString also formats a number-like string as Text (ScSetStringParam::setTextInput); a typed '123 or an
    # imported text keeps General. C2:C9 get General back; C11 stays Text formatted "on purpose" and is left alone.
    sheet.getCellRangeByName("C2:C9").NumberFormat = 0
    sheet.getCellByPosition(2, 10).setString("3.000")
    controller = doc.getCurrentController()
    controller.select(sheet.getCellRangeByName("C10"))
    time.sleep(1)
    subprocess.run(["xdotool", "type", "--delay", "60", "'2.500\n"], env=dict(os.environ, DISPLAY=args.display))
    sheet.getCellByPosition(3, 1).setFormula("=SUM(C2:C9)")  # C10 is outside on purpose
    controller.select(sheet.getCellRangeByName("E12"))
    path = shot(office, args, "01-triangles.png", 3)
    typed = sheet.getCellByPosition(2, 9)
    record("typed '2.500 is a General text cell", typed.getType().value == "TEXT" and typed.NumberFormat % 10000 == 0,
           (typed.getString(), typed.NumberFormat))
    count = pixels(path, GREEN)[0]
    record("green triangles drawn on the 6 numbers stored as text", count >= 6 * 10, "%d green pixels" % count)

    controller.select(sheet.getCellRangeByName("C3"))
    path = shot(office, args, "02-button.png")
    found, bx, by = pixels(path, YELLOW)
    record("warning button shown next to the cell cursor", found > 20, (found, bx, by))
    if found:
        subprocess.run(["xdotool", "mousemove", str(bx), str(by), "click", "1"], env=dict(os.environ, DISPLAY=args.display))
        shot(office, args, "03-button-menu.png")
        subprocess.run(["xdotool", "key", "b"], env=dict(os.environ, DISPLAY=args.display))  # _Bỏ qua lỗi
        time.sleep(1.5)
    settings = doc.createInstance("com.sun.star.sheet.DocumentSettings")
    ignored = settings.getPropertyValue("HstIgnoredTextNumbers")
    record("Bỏ qua lỗi from the button menu", ignored == "0!C3:C3", ignored)
    shot(office, args, "04-ignored.png")

    controller.select(sheet.getCellRangeByName("C2:C11"))
    office.dispatch(frame, ".uno:HstConvertTextToNumber")
    time.sleep(1)
    cells = [sheet.getCellByPosition(2, r + 1) for r in range(len(TEXTS))]
    values = [c.getValue() if c.getType().value == "VALUE" else c.getString() for c in cells]
    want = [1234567.0, 0.15, 1000000.0, -1000.0, 1234.5, "0905123456", "abc", "1,234,567.89"]
    record("command converts the selection (vi-VN), codes and other-locale text stay", values == want, values)
    formats = doc.getNumberFormats()
    codes = [formats.getByKey(c.NumberFormat).FormatString for c in cells[:5]]
    record("typed '2.500 converted, Text-formatted C11 kept", typed.getValue() == 2500.0
           and sheet.getCellByPosition(2, 10).getType().value == "TEXT", sheet.getCellByPosition(2, 10).getString())
    record("General cells get the written format", "%" in codes[1] and "₫" in codes[2] and "#" in codes[0], codes)
    record("SUM sees the numbers", abs(sheet.getCellByPosition(3, 1).getValue() - 2234801.65) < 1e-6,
           sheet.getCellByPosition(3, 1).getValue())
    shot(office, args, "05-converted.png")
    manager = doc.getUndoManager()
    record("one undo step", manager.getCurrentUndoActionTitle() == "Chuyển thành số", manager.getCurrentUndoActionTitle())
    manager.undo()
    record("undo brings the texts back", [c.getString() for c in cells] == TEXTS and cells[0].getType().value == "TEXT")

    office.set_config("/org.openoffice.Office.Calc/Content/Display", "HstNumberStoredAsText", False)
    controller.select(sheet.getCellRangeByName("E12"))
    path = shot(office, args, "06-option-off.png", 2)
    record("option off hides the triangles", pixels(path, GREEN)[0] == 0)
    office.set_config("/org.openoffice.Office.Calc/Content/Display", "HstNumberStoredAsText", True)
    round_trips(office, args, doc, uno)
    big(office, args, uno)


def round_trips(office, args, doc, uno):
    from com.sun.star.beans import PropertyValue
    for ext, flt in (("xlsx", "Calc Office Open XML"), ("ods", "calc8")):
        url = uno.systemPathToFileUrl(os.path.join(office.workdir, "ignored." + ext))  # soffice runs as the build user
        prop = PropertyValue()
        prop.Name, prop.Value = "FilterName", flt
        doc.storeToURL(url, (prop,))
        again = office.load(url)
        value = again.createInstance("com.sun.star.sheet.DocumentSettings").getPropertyValue("HstIgnoredTextNumbers")
        record("Bỏ qua lỗi kept in ." + ext, value == "0!C3:C3", value)
        again.close(True)
    with zipfile.ZipFile(os.path.join(office.workdir, "ignored.xlsx")) as package:
        xml = package.read("xl/worksheets/sheet1.xml").decode()
    record("xlsx has <ignoredErrors>", '<ignoredError sqref="C3" numberStoredAsText="1"/>' in xml)


def big(office, args, uno):
    doc = office.load("private:factory/scalc")
    frame = doc.getCurrentController().getFrame()
    frame.getContainerWindow().setPosSize(0, 0, 1600, 1000, 15)
    sheet = doc.Sheets.getByIndex(0)
    sheet.getCellRangeByPosition(0, 0, 0, args.rows - 1).setDataArray(tuple(("%d.%03d" % (r // 1000 + 1, r % 1000),)
                                                                            for r in range(args.rows)))
    sheet.getCellRangeByPosition(0, 0, 0, args.rows - 1).NumberFormat = 0  # setDataArray marks them Text
    controller = doc.getCurrentController()
    start = time.time()
    for row in range(0, args.rows, args.rows // 20):
        controller.select(sheet.getCellByPosition(0, row))
    record("20 jumps through %d rows" % args.rows, time.time() - start < 20, "%.2f s" % (time.time() - start))
    shot(office, args, "07-big-sheet.png")
    controller.select(sheet.getCellRangeByPosition(0, 0, 0, args.rows - 1))
    start = time.time()
    office.dispatch(frame, ".uno:HstConvertTextToNumber")
    spent = time.time() - start
    last = sheet.getCellByPosition(0, args.rows - 1)
    record("convert %d rows" % args.rows, last.getType().value == "VALUE" and spent < 60, "%.2f s, last %s" % (
        spent, last.getValue()))
    start = time.time()
    doc.getUndoManager().undo()
    record("undo %d rows" % args.rows, last.getType().value == "TEXT", "%.2f s" % (time.time() - start))
    doc.close(True)


if __name__ == "__main__":
    main()
