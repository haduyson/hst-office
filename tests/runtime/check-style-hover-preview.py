# SPDX-License-Identifier: AGPL-3.0-only
"""Gate G1: the Styles gallery hover preview never changes the document's state (gtk3, vi_VN).

Usage: python3 tests/runtime/check-style-hover-preview.py [--instdir DIR] [--display :97] [--out DIR]

A Writer document with one undoable edit and one undone edit (so both the undo and the redo stacks
hold an entry) is saved unmodified. The pointer rests on the second style of the ribbon gallery and
then leaves it. Checked:
  1. the preview works: during the hover the paragraph shows the hovered style, afterwards its own;
  2. modified flag: false during and after the hover;
  3. undo and redo stacks: the same titles before, during and after;
  4. track changes on: the number of tracked changes is the same during and after; recording stays on;
  5. autorecovery: storeToRecoveryFile during a hover ends the preview before writing (the paragraph
     has its own style again) and the document stays unmodified;
  6. read-only: a copy opened read-only gets no preview;
  7. direct formatting: a paragraph with direct alignment, indent, spacing, line spacing, background,
     numbering and bold is exactly as before after a hover (the flat ODF of its automatic styles and
     body is byte-identical, and so are its direct property values).
Writes evidence.json; exit 1 when a check fails.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
PORT = 7441
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:200]}", flush=True)


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def state(doc):
    """(paragraph style at the cursor, modified, undo titles, redo titles, tracked changes)."""
    cursor = doc.getCurrentController().getViewCursor()
    undo = doc.getUndoManager()
    return (cursor.getPropertyValue("ParaStyleName"), doc.isModified(), tuple(undo.getAllUndoActionTitles()),
            tuple(undo.getAllRedoActionTitles()), sum(1 for _ in iter_enum(doc.getRedlines().createEnumeration())))


def iter_enum(enumeration):
    while enumeration.hasMoreElements():
        yield enumeration.nextElement()


def window_of(office, title_part):
    for wid, name in hst_gui.toplevels(office.display, office.pid):
        if title_part in name:
            return wid
    return None


def gallery_item(office, wid, out, name):
    """Screen point of the gallery's second style (the first is the current style)."""
    xdo(office.display, "windowmove", wid, "0", "0")
    xdo(office.display, "windowsize", wid, "2400", "900")  # room for two style tiles beside the 1.0.0 content and Tools
    time.sleep(3)
    shot = office.screenshot(os.path.join(out, name))
    from PIL import Image
    img = Image.open(shot).convert("RGB")
    # the current style's tile has the blue selection box (a contiguous blue edge of 80+ px; a
    # checked button's border is much shorter); the next style sits right of it
    edges = []
    for y in range(45, 170):
        run = 0
        for x in range(150, 2000):
            r, g, b = img.getpixel((x, y))
            run = run + 1 if (b > 150 and r < 90 and 70 < g < 170) else 0
            if run == 80:
                edges.append((x - 79, y))
    if len(edges) < 2:
        return None
    left, top = min(edges)
    bottom = max(y for _x, y in edges)

    def blue(x, y):
        r, g, b = img.getpixel((x, y))
        return b > 150 and r < 90 and 70 < g < 170

    right = left
    while right + 1 < img.width and blue(right + 1, top):
        right += 1
    return right + (right - left) // 2 + 4, (top + bottom) // 2


def hover(office, point, rest=1.2):
    xdo(office.display, "mousemove", str(point[0]), str(point[1]))
    time.sleep(rest)


def leave(office):
    xdo(office.display, "mousemove", "700", "600")  # the document area
    time.sleep(0.8)


FLAT = "OpenDocument Text Flat XML"
DIRECT = {"ParaAdjust": 3, "ParaLeftMargin": 1000, "ParaFirstLineIndent": -500, "ParaTopMargin": 300,
          "ParaBottomMargin": 400, "ParaBackColor": 0xFFF2CC, "CharWeight": 150.0}


def flat_body(doc, path):
    """The automatic styles and the body of the document as flat ODF (what the paragraph is made of)."""
    doc.storeToURL("file://" + path, (prop("FilterName", FLAT),))
    with open(path, encoding="utf-8") as handle:
        xml = handle.read()
    start = xml.index("<office:automatic-styles")
    return xml[start:xml.index("</office:body>")]


def direct_values(paragraph):
    names = [p.Name for p in paragraph.getPropertySetInfo().getProperties()]
    values = {}
    for name in names:
        try:
            if paragraph.getPropertyState(name).value == "DIRECT_VALUE":
                value = repr(paragraph.getPropertyValue(name))
                # object references (NumberingRules, grab bags) differ by address only; the flat
                # ODF comparison covers what they hold
                if "pyuno object" not in value:
                    values[name] = value
        except Exception:  # noqa: BLE001 - properties without a state or value
            pass
    return values


def check_direct_formatting(office, doc, point, out):
    paragraph = doc.getText().createEnumeration().nextElement()
    for name, value in DIRECT.items():
        if name == "ParaAdjust":
            import uno
            value = uno.Enum("com.sun.star.style.ParagraphAdjust", "CENTER")
        paragraph.setPropertyValue(name, value)
    lists = doc.getStyleFamilies().getByName("NumberingStyles").getElementNames()
    paragraph.setPropertyValue("NumberingStyleName", lists[0])
    spacing = paragraph.getPropertyValue("ParaLineSpacing")
    spacing.Height = 150
    paragraph.setPropertyValue("ParaLineSpacing", spacing)
    doc.setModified(False)
    before_xml = flat_body(doc, os.path.join(out, "direct-before.fodt"))
    before = direct_values(paragraph)
    hover(office, point)
    during = paragraph.getPropertyValue("ParaStyleName")
    leave(office)
    after_xml = flat_body(doc, os.path.join(out, "direct-after.fodt"))
    after = direct_values(paragraph)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    record("7. direct formatting (alignment, indents, spacing, background, list, bold) survives a hover",
           before_xml == after_xml and not changed and during != paragraph.getPropertyValue("ParaStyleName")
           and not doc.isModified(), changed or (len(before), during))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/style-hover-preview"))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display).start()
    try:
        doc = office.load("private:factory/swriter")
        time.sleep(6)
        text = doc.getText()
        text.insertString(text.getEnd(), "Đoạn văn thử cho xem trước kiểu.", False)
        text.insertString(text.getEnd(), " Thêm.", False)
        doc.getUndoManager().undo()  # one entry on each stack
        saved = "file://" + os.path.join(args.out, "hover-preview.odt")
        doc.storeToURL(saved, (prop("FilterName", "writer8"),))
        doc.setModified(False)
        wid = window_of(office, "HST Writer")
        point = gallery_item(office, wid, args.out, "01-gallery.png") if wid else None
        record("gallery found on the ribbon", point is not None, point)
        if point is None:
            return 1
        before = state(doc)
        hover(office, point)
        during = state(doc)
        office.screenshot(os.path.join(args.out, "02-hover.png"))
        leave(office)
        after = state(doc)
        record("1. the preview shows the hovered style, then the paragraph's own",
               during[0] != before[0] and after[0] == before[0], (before[0], during[0], after[0]))
        record("2. modified flag stays false during and after", not during[1] and not after[1], (during[1], after[1]))
        record("3. undo and redo stacks unchanged", during[2:4] == before[2:4] == after[2:4], (before[2:4], during[2:4], after[2:4]))

        doc.setPropertyValue("RecordChanges", True)
        tracked = state(doc)
        hover(office, point)
        during = state(doc)
        leave(office)
        after = state(doc)
        record("4. track changes: no tracked change from the preview, recording still on",
               during[4] == tracked[4] == after[4] and doc.getPropertyValue("RecordChanges")
               and during[0] != tracked[0] and after[0] == tracked[0], (tracked[4], during[4], after[4]))
        doc.setPropertyValue("RecordChanges", False)
        doc.setModified(False)

        hover(office, point)
        previewing = state(doc)[0]
        doc.storeToRecoveryFile("file://" + os.path.join(args.out, "recovery.odt"), ())
        stored = state(doc)
        leave(office)
        record("5. autorecovery store ends the preview first; document unmodified",
               previewing != before[0] and stored[0] == before[0] and not stored[1], (previewing, stored[0], stored[1]))

        check_direct_formatting(office, doc, point, args.out)

        readonly = office.desktop().loadComponentFromURL(saved, "_blank", 0, (prop("ReadOnly", True),))
        time.sleep(5)
        ro_wid = window_of(office, "hover-preview")
        ro_point = gallery_item(office, ro_wid, args.out, "03-readonly.png") if ro_wid else None
        ro_before = state(readonly)[0]
        if ro_point:
            hover(office, ro_point)
        ro_during = state(readonly)[0]
        leave(office)
        record("6. read-only document: no preview", ro_point is not None and ro_during == ro_before and not readonly.isModified(),
               (ro_point, ro_before, ro_during))
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
