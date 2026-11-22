#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Runtime layout check of the HST coat's tier-3 dialogs: opens each dialog, reads the accessible bounds of every
control on every tab and reports what the rulebook forbids
(plans/261120-0850-hst-ui-coat-tier2-3/reports/layout-rulebook.md):

- gap: two controls with a border closer than MinGap (4 px at every scale), across or down;
- clipped: the text of a label, check/radio button or button reaching outside its control (cut or hidden), or a
  line box shorter than its text when the text has letters with two marks (Ẩ, ặ, ế);
- fit: the dialog with its window frame larger than the work area of a hard target (D2: 1366x768 at 100 %,
  1920x1080 at 125 %; 1366x768 at 125 % is reported only);
and, as warnings, two bordered controls stacked closer than RowGap (6 px) (row-gap) and a line box 1-2 px shorter
than a text without two-mark letters (tight).

Linux (an Xvfb of your own; this script never starts or stops it), run with the image's bundled python:
    <instdir>/program/python hst_dialog_layout_check.py --instdir <instdir> --out DIR --display :1NN
        [--plugin gen|gtk3] [--lang vi_VN.UTF-8|en_US.UTF-8] [--scale 100|125] [--all] [--strict] [id ...]
  gen (VCL-drawn, as on Windows) reads the office's UNO accessibility tree; gtk3 reads AT-SPI through the system
  python3 (pyatspi) on a private D-Bus session: as root the script re-runs itself as the build user under
  dbus-run-session. 125 % on Linux is GDK_DPI_SCALE=1.25 (gtk3) / SAL_FORCEDPI=120 (gen).
Windows (console session, the image's python.exe): --plugin win; the display scale is set outside this script and
named with --scale.
Self-test: --selftest (geometry on built-in windows; with --instdir also a live VCL window with two entries 3 px
apart and two 6 px apart, which must come out red and green).

Output: <out>/<id>.json (per tab: controls, findings), <out>/<id>-<tab>.png, <out>/summary.json. Exit 1 when a
listed dialog has a gap, clipped text or a hard fit failure (--strict: also a row-gap warning), 2 on a setup error.
Default dialogs: the ranked list (hst_dialog_layout_cases.listed()); --all: every candidate and every case a batch
adds in tests/runtime/data/dialog-layout-<batch>.json.
"""
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_dialog_layout_cases as cases  # noqa: E402

MIN_GAP = 4  # hst::design::layout::MinGap, px (the toolkits do not scale .ui spacing)
ROW_GAP = 6  # hst::design::layout::RowGap (D3)
CLIP_TOLERANCE = 1  # device px a glyph box may stick out (anti-aliasing, rounding)
# name: (scale, work area width, height, hard). Work area = screen minus a 40 px (100 %) / 48 px taskbar.
TARGETS = {"1366x768@100": (100, 1366, 728, True), "1920x1080@125": (125, 1920, 1032, True),
           "1366x768@125": (125, 1366, 720, False)}
FRAME = (16, 39)  # window frame around the client area at 100 % (Windows 11: 8 px borders, 31 px title bar)
# plugins whose dialog box is already the outer window rect (frame included): win reads the top-level window's
# bounding rect, which holds the title bar and borders (its shot shows them), so no frame is added there
OUTER_RECT_PLUGINS = {"win"}
BORDERED = {"push button", "toggle button", "text", "entry", "password text", "spin box", "spin button",
            "combo box", "list", "list box", "tree", "tree table", "table", "button menu", "button dropdown",
            "menu button", "push button menu", "date editor"}
LISTS = {"list", "list box", "tree", "tree table", "table", "text", "document text", "paragraph", "icon view"}
TEXTUAL = {"label", "check box", "radio button", "push button", "toggle button"}
SAMPLE = "Ẩn Ỗ Ữ Ặ ậ ỷ"  # stacked Vietnamese marks every label must show in full


# ---- geometry (pure) ---------------------------------------------------------------------------------------------
def min_gap_px(_scale):
    """Gaps are compared in device px at every scale: neither VCL nor GTK scales the spacing of a .ui file with the
    text (measured: gen with SAL_FORCEDPI=120 keeps Paragraph's 3 px and 6 px gaps at 125 %), so the rulebook's
    "never below 4 px at any scale" is 4 device px."""
    return MIN_GAP


def row_gap_px(_scale):
    return ROW_GAP


def neighbours(boxes, vertical):
    """(a, b, gap) for each bordered box `a` and every box `b` after it, down (vertical) or across, that overlaps it on
    the other axis with no third box between the two in that overlap; gap < 0 when they overlap. Boxes are dicts with
    x, y, w, h."""
    def span(n):  # (start, end) along the axis, then across it
        return ((n["y"], n["y"] + n["h"]), (n["x"], n["x"] + n["w"])) if vertical else \
            ((n["x"], n["x"] + n["w"]), (n["y"], n["y"] + n["h"]))

    def cross(p, q):
        return min(p[1], q[1]) - max(p[0], q[0])

    out = []
    for a in boxes:
        (a0, a1), across_a = span(a)
        for b in boxes:
            if b is a:
                continue
            (b0, b1), across_b = span(b)
            if b0 < a0 or (b0 == a0 and id(b) < id(a)) or cross(across_a, across_b) <= 0 or b0 >= a1 + 60:
                continue
            if b0 < a1 and b1 <= a1:
                continue  # b lies within a's extent on this axis: not after it
            overlap = (min(across_a[1], across_b[1]), max(across_a[0], across_b[0]))
            blocked = any(c is not a and c is not b and span(c)[0][0] >= a1 and span(c)[0][1] <= b0 and
                          cross(span(c)[1], (overlap[1], overlap[0])) > 0 for c in boxes)
            if not blocked:
                out.append((a, b, b0 - a1))
    return out


def inside(node, outer):
    """The node lies within `outer` (toolbar buttons are flat items of one bar, not neighbouring controls)."""
    return outer["x"] <= node["x"] and outer["y"] <= node["y"] and \
        node["x"] + node["w"] <= outer["x"] + outer["w"] and node["y"] + node["h"] <= outer["y"] + outer["h"]


def joined(a, b):
    """A list's header bar on top of its rows: a short table/list box over a list box of the same column, touching."""
    return a["role"] in LISTS and b["role"] in LISTS and a["x"] == b["x"] and a["w"] == b["w"] and a["h"] <= 30


def clipped(node):
    """(across, down): how far the node's text sticks out of the node, in device px. Across: its ends against the
    node's; down: its height against the node's only (VCL reports the character boxes of a label 2 px
    lower than it draws them while the glyphs fit; measured on Paragraph, gen, 26.8.3)."""
    text = node.get("text_box")
    if not text or not node.get("text"):
        return 0, 0
    x, _y, w, h = text
    return max(0, -x, x + w - node["w"]), max(0, h - node["h"])


def clip_finding(node):
    """A clipped text (error): across by more than 1 px, or down by more than 2 px. A line box 1-2 px shorter than
    its text is a `tight` warning: on gen, VCL reports the character boxes of labels with two-mark letters 2 px taller
    than the label ("Tùy chọn sắp xếp" on Sort, "Thay thế bằng:" on Find and Replace) while it draws them whole, so
    such a box alone does not prove a cut mark; screenshots decide."""
    across, down = clipped(node)
    if across <= CLIP_TOLERANCE and down == 0:
        return None
    hard = across > CLIP_TOLERANCE or down > 2
    return {"kind": "clipped" if hard else "tight", "px": max(across, down), "text": node.get("text", "")[:80],
            "role": node["role"], "box": [node["x"], node["y"], node["w"], node["h"]], "warning": not hard}


def analyse(dialog, nodes, scale, plugin=None):
    """Findings of one shown page: dialog = {w, h} (the client area, or the outer window rect for the plugins in
    OUTER_RECT_PLUGINS); nodes = [{role, name, x, y, w, h, text, text_box}] relative to
    the dialog's client area (text_box relative to the node)."""
    findings = []
    bars = [n for n in nodes if n["role"] == "tool bar"]
    boxes = [n for n in nodes
             if n.get("bordered") and n["w"] > 0 and n["h"] > 0 and not any(inside(n, bar) for bar in bars)]
    hard, warn = min_gap_px(scale), row_gap_px(scale)
    for vertical in (True, False):
        for a, b, gap in neighbours(boxes, vertical):
            if vertical and gap == 0 and joined(a, b):
                continue
            if gap < 0 and (inside(a, b) or inside(b, a)):
                continue  # one control drawn inside another (a field inside its list), not two neighbours
            pair = [a.get("name") or a["role"], b.get("name") or b["role"]]
            if gap < hard:
                findings.append({"kind": "gap", "px": gap, "axis": "down" if vertical else "across", "between": pair,
                                 "boxes": [[a["x"], a["y"], a["w"], a["h"]], [b["x"], b["y"], b["w"], b["h"]]]})
            elif vertical and gap < warn:
                findings.append({"kind": "row-gap", "px": gap, "axis": "down", "between": pair, "warning": True})
    for node in nodes:
        found = clip_finding(node)
        if found:
            findings.append(found)
    for name, (target_scale, width, height, is_hard) in TARGETS.items():
        if target_scale != scale:
            continue
        frame = (0, 0) if plugin in OUTER_RECT_PLUGINS else FRAME
        outer_w = dialog["w"] + round(frame[0] * scale / 100)
        outer_h = dialog["h"] + round(frame[1] * scale / 100)
        if outer_w > width or outer_h > height:
            findings.append({"kind": "fit", "target": name, "size": [outer_w, outer_h], "warning": not is_hard})
    return findings


# Titles of VCL/GTK message boxes (vi and en): a window with one of these is a message, not the dialog under test
MESSAGE_TITLES = {"Thông tin", "Information", "Xác nhận", "Confirmation", "Cảnh báo", "Warning", "Lỗi", "Error",
                  "Câu hỏi", "Question"}


def message_box(title):
    return (title or "").strip() in MESSAGE_TITLES


def unverified(nodes):
    """Texts whose character boxes the accessibility layer did not give: their clipping is not checked."""
    return sum(1 for n in nodes if n["role"] in TEXTUAL and n.get("text") and not n.get("text_box"))


def failing(findings, strict=False):
    """The findings that fail a run: errors, and with --strict the row-gap and tight-line warnings too (never the
    report-only fit target)."""
    return [f for f in findings if not f.get("warning") or (strict and f["kind"] != "fit")]


# ---- collectors ---------------------------------------------------------------------------------------------------
def role_names():
    """{AccessibleRole value: 'push button'} from the UNO constants group."""
    import uno
    names = {}
    for name in ("PUSH_BUTTON", "TOGGLE_BUTTON", "TEXT", "PASSWORD_TEXT", "SPIN_BOX", "COMBO_BOX", "LIST", "TREE",
                 "TREE_TABLE", "TABLE", "SCROLL_PANE", "LABEL", "CHECK_BOX", "RADIO_BUTTON", "PAGE_TAB_LIST",
                 "PAGE_TAB", "PANEL", "FILLER", "DIALOG", "BUTTON_MENU", "BUTTON_DROPDOWN", "PARAGRAPH",
                 "DOCUMENT_TEXT", "DATE_EDITOR", "LIST_ITEM", "MENU_BUTTON", "TOOL_BAR"):
        try:
            names[uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)] = \
                name.lower().replace("_", " ")
        except Exception:  # noqa: BLE001 - a constant this version does not have
            continue
    return names


def uno_showing(context):
    import uno
    showing = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SHOWING")
    try:
        states = context.getAccessibleStateSet()
        return bool(states & showing) if isinstance(states, int) else states.contains(showing)
    except Exception:  # noqa: BLE001 - disposed while walking
        return False


def uno_text_box(context):
    """Union of the character boxes of the context's text, relative to it, or None."""
    try:
        count = context.getCharacterCount()
    except Exception:  # noqa: BLE001 - no XAccessibleText
        return None
    boxes = []
    for index in (range(count) if count <= 400 else list(range(200)) + list(range(count - 200, count))):
        try:
            rect = context.getCharacterBounds(index)
        except Exception:  # noqa: BLE001
            continue
        if rect.Width > 0 and rect.Height > 0:
            boxes.append((rect.X, rect.Y, rect.X + rect.Width, rect.Y + rect.Height))
    if not boxes:
        return None
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    return [left, top, max(b[2] for b in boxes) - left, max(b[3] for b in boxes) - top]


def uno_nodes(dialog_context, roles):
    """Walk a VCL dialog's accessible tree (gen, win): the shown controls relative to the dialog."""
    origin = dialog_context.getLocationOnScreen()
    out, tablists, lists = [], [], []

    def walk(context, depth):
        if depth > 40 or not uno_showing(context):
            return
        role = roles.get(context.getAccessibleRole(), "other")
        if role == "page tab list":
            tablists.append(context)
        try:
            where, size = context.getLocationOnScreen(), context.getSize()
        except Exception:  # noqa: BLE001
            return
        children = [context.getAccessibleChild(i).getAccessibleContext()
                    for i in range(min(context.getAccessibleChildCount(), 500))]
        lists_inside = role == "scroll pane" and any(roles.get(c.getAccessibleRole()) in LISTS for c in children)
        node = {"role": role, "name": context.getAccessibleName() or "", "x": where.X - origin.X,
                "y": where.Y - origin.Y, "w": size.Width, "h": size.Height,
                "bordered": role in BORDERED or lists_inside}
        if role in TEXTUAL:
            try:
                node["text"] = context.getText()
            except Exception:  # noqa: BLE001
                node["text"] = node["name"]
            node["text_box"] = uno_text_box(context)
        out.append(node)
        if role == "list":
            lists.append((node, context))
        if node["bordered"] and role != "scroll pane" or lists_inside or role == "tool bar":
            return
        for child in children:
            walk(child, depth + 1)

    walk(dialog_context, 0)
    size = dialog_context.getSize()
    # HST's tab dialogs put their tabs in a list down the left side (VerticalTabControl): the pages are its items, and
    # a page may hold tabs of its own (Page Setup: Lề, Giấy, Bố trí). Outer list first, then the inner tab lists.
    tablists = [context for node, context in lists if node["x"] <= 16 and node["h"] >= size.Height // 2][:1] + \
        tablists
    return {"w": size.Width, "h": size.Height, "title": dialog_context.getAccessibleName()}, out[1:], tablists


def uno_select_tab(tablist, index):
    tablist.selectAccessibleChild(index)


ATSPI = r'''
import json, sys
import pyatspi
pid = int(sys.argv[1])
level, tab = (int(x) for x in sys.argv[2].split(":"))
BORDERED, LISTS, TEXTUAL = set(json.loads(sys.argv[3])), set(json.loads(sys.argv[4])), set(json.loads(sys.argv[5]))
D = pyatspi.DESKTOP_COORDS
def showing(n):
    try:
        return n.getState().contains(pyatspi.STATE_SHOWING)
    except Exception:
        return False
def dialogs():
    desk = pyatspi.Registry.getDesktop(0)
    for i in range(desk.childCount):
        app = desk.getChildAtIndex(i)
        try:
            if app is None or app.get_process_id() != pid:
                continue
        except Exception:
            continue
        for j in range(app.childCount):
            win = app.getChildAtIndex(j)
            if win is not None and win.getRoleName() in ("dialog", "alert", "file chooser") and showing(win):
                yield win
found = list(dialogs())
if not found:
    print(json.dumps({"error": "no showing dialog"})); sys.exit(0)
dlg = found[-1]
ext = dlg.queryComponent().getExtents(D)
out, tabs = [], []
def walk(n, depth):
    if depth > 40 or not showing(n):
        return
    role = n.getRoleName()
    try:
        e = n.queryComponent().getExtents(D)
    except Exception:
        return
    kids = [n.getChildAtIndex(i) for i in range(min(n.childCount, 500))]
    if role == "page tab list":
        tabs.append(n)
    inside = role == "scroll pane" and any(k is not None and k.getRoleName() in LISTS for k in kids)
    node = {"role": role, "name": n.name or "", "x": e.x - ext.x, "y": e.y - ext.y, "w": e.width, "h": e.height,
            "bordered": role in BORDERED or inside}
    if role in TEXTUAL:
        try:
            t = n.queryText()
            node["text"] = t.getText(0, -1)
            boxes = []
            for i in range(t.characterCount if t.characterCount <= 400 else 400):
                x, y, w, h = t.getCharacterExtents(i, D)
                if w > 0 and h > 0:
                    boxes.append((x - e.x, y - e.y, x - e.x + w, y - e.y + h))
            if boxes:
                l, tp = min(b[0] for b in boxes), min(b[1] for b in boxes)
                node["text_box"] = [l, tp, max(b[2] for b in boxes) - l, max(b[3] for b in boxes) - tp]
        except Exception:
            node["text"] = node["name"]
    out.append(node)
    if (node["bordered"] and role != "scroll pane") or inside or role == "tool bar":
        return
    for k in kids:
        if k is not None:
            walk(k, depth + 1)
walk(dlg, 0)
levels = [[t.getChildAtIndex(i).name for i in range(t.childCount)] for t in tabs[:2]]
if tab >= 0:
    tabs[level].querySelection().selectChild(tab)
    print(json.dumps({"selected": tab})); sys.exit(0)
print(json.dumps({"dialog": {"w": ext.width, "h": ext.height, "title": dlg.name}, "nodes": out[1:], "tabs": levels},
                 ensure_ascii=False))
'''


def atspi(pid, level=0, tab=-1):
    result = subprocess.run(["/usr/bin/python3", "-I", "-c", ATSPI, str(pid), f"{level}:{tab}",
                             json.dumps(sorted(BORDERED)),
                             json.dumps(sorted(LISTS)), json.dumps(sorted(TEXTUAL))],
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError("AT-SPI walk failed: " + result.stderr[-600:])
    return json.loads(result.stdout.strip().splitlines()[-1])


# ---- driver -------------------------------------------------------------------------------------------------------
def uno_url(path):
    return "file:///" + path.replace("\\", "/").lstrip("/")


def setup_document(office, ui, instdir, factory, recipe):
    """A new document of `factory` prepared so that the dialog's command is enabled. Its commands (Copy, Insert
    Table, Insert Image) go through UITest on the office's main thread, to this document's frame: a dispatch
    from the bridge's thread can hang the office (Slides' Insert Table on Windows)."""
    from com.sun.star.beans import PropertyValue

    def props(**values):
        out = []
        for name, value in values.items():
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            out.append(prop)
        return tuple(out)

    doc = office.desktop().loadComponentFromURL(f"private:factory/{factory}", "_blank", 0,
                                                props(Hidden=False, OnMainThread=True))
    time.sleep(2)
    frame = doc.getCurrentController().getFrame()

    def dispatch(command, args=()):
        activate(office, frame)
        ui.executeCommandWithParameters(command, tuple(args))

    if recipe in ("writer-word", "writer-saved"):
        doc.getText().setString("house of words")
        if recipe == "writer-word":  # HST ships an English thesaurus only (dict-en); Vietnamese has none
            from com.sun.star.lang import Locale
            whole = doc.getText().createTextCursor()
            whole.gotoEnd(True)
            whole.CharLocale = Locale("en", "US", "")
        cursor = doc.getCurrentController().getViewCursor()
        cursor.gotoStart(False)
        cursor.goRight(2, False)  # inside the first word, nothing selected (Thesaurus looks the word up)
        if recipe == "writer-saved":  # signing needs a stored document
            path = os.path.join(tempfile.gettempdir(), f"hst-layout-sign-{os.getpid()}.odt")
            doc.storeAsURL(uno_url(path), ())
    elif recipe in ("writer-text", "writer-misspelt", "writer-modified", "writer-copy"):
        text = "Thử nghiệm bố cục HST: chữ saii chính tả.\nHàng thứ hai; cột ba\nHàng thứ ba; cột bốn"
        doc.getText().setString(text)
        cursor = doc.getCurrentController().getViewCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        if recipe == "writer-copy":
            dispatch(".uno:Copy")
            cursor.gotoEnd(False)
    elif recipe == "writer-table":
        dispatch(".uno:InsertTable", props(Columns=3, Rows=3))
    elif recipe == "writer-image":
        image = os.path.join(os.path.abspath(instdir), "program", "intro.png")
        dispatch(".uno:InsertGraphic", props(FileName=uno_url(image)))
    elif recipe == "calc-hidden-sheet":
        doc.getSheets().insertNewByName("Ẩn", 1)
        doc.getSheets().getByName("Ẩn").IsVisible = False
    elif recipe in ("calc-data", "calc-text", "calc-copy"):
        sheet = doc.getSheets().getByIndex(0)
        rows = [("Tên", "Số", "Ngày")] + [(f"Mục {i}", i * 3, i) for i in range(1, 6)]
        if recipe == "calc-text":
            rows = [(f"a{i};b{i};c{i}",) for i in range(1, 6)]
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                cell = sheet.getCellByPosition(c, r)
                cell.setValue(value) if isinstance(value, (int, float)) else cell.setString(value)
        width = len(rows[0]) - 1
        doc.getCurrentController().select(sheet.getCellRangeByPosition(0, 0, width, len(rows) - 1))
        if recipe == "calc-copy":
            dispatch(".uno:Copy")
            doc.getCurrentController().select(sheet.getCellByPosition(5, 0))
    elif recipe in ("shape", "slides-table"):
        page = doc.getDrawPages().getByIndex(0)
        if recipe == "shape":
            from com.sun.star.awt import Point, Size
            shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
            page.add(shape)
            shape.setPosition(Point(3000, 3000))
            shape.setSize(Size(8000, 4000))
            shape.setString("Ẩn Ỗ Ữ Ặ ậ ỷ")
            doc.getCurrentController().select(shape)
        else:
            dispatch(".uno:InsertTable", props(Columns=3, Rows=3))
    time.sleep(1.5)
    return doc


def activate(office, frame):
    """Make `frame` the desktop's current frame: comphelper::dispatchCommand (UITest) dispatches there."""
    frame.activate()
    office.desktop().setActiveFrame(frame)
    frame.getContainerWindow().setFocus()


def office_alive(office):
    """Whether the office still answers over the bridge (a checker error is not an ended office)."""
    try:
        office.desktop().getFrames().getCount()
        return True
    except Exception:  # noqa: BLE001 - a dead bridge raises DisposedException or a RuntimeException
        return False


def park_pointer(args):
    """X11: the pointer to the screen's corner, so no tooltip appears where the dialog opens."""
    if args.plugin != "win":
        subprocess.run(["xdotool", "mousemove", "0", "0"], env=dict(os.environ, DISPLAY=args.display),
                       check=False, capture_output=True, timeout=10)


def end_execute(window):
    """endExecute only on a dialog (XDialog); False for any other window."""
    import uno
    try:
        dialog = window.queryInterface(uno.getTypeByName("com.sun.star.awt.XDialog"))
    except Exception:  # noqa: BLE001 - disposed meanwhile
        return False
    if not dialog:
        return False
    try:
        dialog.endExecute()
        return True
    except Exception:  # noqa: BLE001 - disposed meanwhile
        return False


X11_NOT_DIALOG_TYPES = ("_NET_WM_WINDOW_TYPE_TOOLTIP", "_NET_WM_WINDOW_TYPE_POPUP_MENU",
                        "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU", "_NET_WM_WINDOW_TYPE_COMBO",
                        "_NET_WM_WINDOW_TYPE_NOTIFICATION", "_NET_WM_WINDOW_TYPE_SPLASH")


class Platform:
    """Where dialogs are found, read, shot and closed."""

    def __init__(self, args, office):
        self.args, self.office = args, office
        self.roles = role_names() if args.plugin != "gtk3" else None
        self._kinds = {}

    def top_windows(self):
        """{key: window} of the office's shown top-level windows that are not document frames. VCL (gen, win): the
        toolkit's top windows keyed by their native handle (X window id or HWND); gtk3: the X top-levels."""
        if self.args.plugin == "gtk3":
            import hst_gui
            return {w[0]: w for w in hst_gui.toplevels(self.args.display, pid=self.office.pid)}
        import uno
        system = uno.getConstantByName("com.sun.star.lang.SystemDependent." +
                                       ("SYSTEM_WIN32" if self.args.plugin == "win" else "SYSTEM_XWINDOW"))
        toolkit = self.office.service("com.sun.star.awt.Toolkit")
        try:
            frames = self.office.desktop().getFrames()
            containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
        except Exception:  # noqa: BLE001 - frames come and go
            containers = []
        found = {}
        for index in range(toolkit.getTopWindowCount()):
            try:
                window = toolkit.getTopWindow(index)
                if not window.isVisible() or any(window == other for other in containers):
                    continue
                handle = window.getWindowHandle(uno.ByteSequence(bytes(16)), system)
                handle = getattr(handle, "WindowHandle", handle)
                if handle:
                    found[hex(int(handle))] = window
            except Exception:  # noqa: BLE001 - disposed while listed
                continue
        return found

    def is_dialog(self, key, window):
        """Whether the top window is a dialog or alert, and not a tooltip, a menu or a splash. A tooltip under the
        pointer must never get a close request: VCL's close handling of a help window crashes the office."""
        if key in self._kinds:
            return self._kinds[key]
        if self.args.plugin == "gtk3":
            out = subprocess.run(["xprop", "-display", self.args.display, "-id", key, "_NET_WM_WINDOW_TYPE"],
                                 capture_output=True, text=True, check=False).stdout
            if "not found" in out or "BadWindow" in out or "=" not in out:
                return False  # gone, or not typed yet: decided on the next look
            kind = not any(t in out for t in X11_NOT_DIALOG_TYPES)
        else:
            try:
                role = window.getProperty("XAccessible").getAccessibleContext().getAccessibleRole()
            except Exception:  # noqa: BLE001 - disposed while asked
                return False
            import uno
            kind = role in {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)
                            for name in ("DIALOG", "ALERT", "FILE_CHOOSER")}
        self._kinds[key] = kind
        return kind

    def new_dialogs(self, before):
        """{key: window} of the dialogs shown now that were not in `before`."""
        return {key: w for key, w in self.top_windows().items() if key not in before and self.is_dialog(key, w)}

    def wait_new(self, before, timeout=30):
        """The new dialogs' keys, looked up again after their first paint: a window that went in the meantime (the
        templates' first-use progress dialog) or a tooltip is not taken."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.new_dialogs(before):
                time.sleep(2)  # first paint, pages built
                new = list(self.new_dialogs(before))
                if new:
                    return new
            time.sleep(0.5)
        return []

    def read(self, key, select=None):
        """(dialog, nodes, [outer tab names, inner tab names]) of the dialog `key`; `select` = (level, index) selects
        that tab first (level 0: the dialog's tabs, 1: the tabs inside the shown page)."""
        if self.args.plugin == "gtk3":
            if select is not None:
                atspi(self.office.pid, *select)
                time.sleep(1)
            data = atspi(self.office.pid)
            if "error" in data:
                raise RuntimeError(data["error"])
            return data["dialog"], data["nodes"], data["tabs"]
        window = self.top_windows().get(key)
        if window is None:
            raise RuntimeError("dialog window gone")
        context = window.getProperty("XAccessible").getAccessibleContext()
        if select is not None:
            _dialog, _nodes, tablists = uno_nodes(context, self.roles)
            uno_select_tab(tablists[select[0]], select[1])
            time.sleep(1)
        dialog, nodes, tablists = uno_nodes(context, self.roles)
        levels = [[t.getAccessibleChild(i).getAccessibleContext().getAccessibleName()
                   for i in range(t.getAccessibleChildCount())] for t in tablists[:2]]
        return dialog, nodes, levels

    def shot(self, key, path):
        """A picture of the dialog; a shot that fails or hangs is reported, it does not stop the measurement."""
        if self.args.plugin == "win":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   os.path.join(HERE, "coat-window-shot.ps1"), "-Hwnd", str(int(key, 16)), "-Path", path]
        else:
            cmd = ["import", "-display", self.args.display, "-window", key, path]
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            print("shot timed out:", path, flush=True)

    def close(self, keys, before):
        """Close the measured dialogs and any other new dialog or alert (a Save Changes? prompt); never a tooltip
        or a menu, which go with their dialog."""
        for _ in range(5):
            now = self.new_dialogs(before)
            if not now:
                return True
            for key in sorted(now, key=lambda k: k not in keys):
                if self.args.plugin == "win":
                    import windows_gui_dialogs
                    windows_gui_dialogs.close_hwnd(int(key, 16)) or end_execute(now[key])
                else:
                    import hst_gui
                    hst_gui.send_close_request(key, self.args.display)
            time.sleep(1.5)
        return False


def measure(platform, key, case, out_dir, ident, scale):
    """Every tab (case.tabs: the dialog's tabs and the tabs inside each page) or the shown page: read, analysed and
    shot while it is shown."""
    pages = []

    def record(name, label, dialog, nodes):
        pages.append({"tab": name, "index": label, "dialog": dialog, "nodes": nodes,
                      "findings": analyse(dialog, nodes, scale, platform.args.plugin), "unverified": unverified(nodes)})
        platform.shot(key, os.path.join(out_dir, ident + ("" if label is None else f"-{label}") + ".png"))

    dialog, nodes, levels = platform.read(key)
    outer = levels[0] if case.tabs and levels else []
    if not outer:
        record(None, None, dialog, nodes)
        return pages
    for i, name in enumerate(outer):
        dialog, nodes, levels = platform.read(key, (0, i))
        inner = levels[1] if len(levels) > 1 else []
        if len(inner) < 2:
            record(name, f"{i:02d}", dialog, nodes)
            continue
        for j, sub in enumerate(inner):
            dialog, nodes, _levels = platform.read(key, (1, j))
            record(f"{name} › {sub}", f"{i:02d}{chr(97 + j)}", dialog, nodes)
    return pages


def run_case(platform, ui, ident, case, args):
    before = platform.top_windows()
    doc = setup_document(platform.office, ui, args.instdir, case.factory, case.setup)
    framed = platform.top_windows()
    if case.setup == "writer-modified":
        doc.getText().getEnd().setString(" (sửa)")
    frame = doc.getCurrentController().getFrame()
    for _attempt in range(2):
        # comphelper::dispatchCommand goes to the desktop's current frame: make it this document's
        activate(platform.office, frame)
        park_pointer(args)
        ui.executeDialog(case.command)
        new = platform.wait_new(framed, timeout=20)
        if new:
            break
    result = {"id": ident, "batch": case.batch, "en": case.en, "command": case.command, "scale": args.scale,
              "plugin": args.plugin}
    if not new:
        result["error"] = "no dialog window"
    else:
        try:
            result["pages"] = measure(platform, new[-1], case, args.out, ident, args.scale)
            result["title"] = result["pages"][0]["dialog"].get("title")
            if message_box(result["title"]):
                # the command answered with a message (nothing to hyphenate, a prompt) instead of its dialog:
                # keep the capture for the record, but it is not the dialog's layout
                result["error"] = f"message box instead of the dialog: {result['title']}"
                result["message"] = result.pop("pages")
        except Exception as error:  # noqa: BLE001 - one dialog's failure must not stop the run
            result["error"] = f"read failed: {type(error).__name__}: {getattr(error, 'Message', '') or error}"
        if not platform.close(new, framed):
            result["close"] = "dialog did not close"
    try:
        doc.setModified(False)
        doc.close(True)
    except Exception:  # noqa: BLE001 - closed with its dialog (Save Changes? closes the document)
        pass
    platform.close([], before)
    return result


def select_cases(every=False, ids=()):
    """{id: Case} to run: the ranked list with the batches' own cases, or with `every` every candidate and every
    batch case; `ids` picks some of all of them."""
    everything = {**cases.CANDIDATES, **cases.load_extra()}
    selected = everything if every else cases.listed()
    if ids:
        unknown = [i for i in ids if i not in everything]
        if unknown:
            raise SystemExit("unknown dialog: " + ", ".join(unknown))
        selected = {i: everything[i] for i in ids}
    return selected


def run(args):
    import hst_gui
    selected = select_cases(args.all, args.ids)
    runnable = {k: v for k, v in selected.items() if v.command}
    env = {"HST_UI_COAT": "1"}
    if args.plugin == "gtk3" and args.scale == 125:
        env["GDK_DPI_SCALE"] = "1.25"
    if args.plugin == "gen" and args.scale == 125:
        env["SAL_FORCEDPI"] = "120"
    if args.plugin == "gtk3":
        env.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    os.environ["HST_VCLPLUGIN"] = args.plugin
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work"), args.port, display=args.display,
                            lang=args.lang, env=env,
                            config=[("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"),
                                    ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")])
    # a stopped run (SIGTERM) still stops its office
    signal.signal(signal.SIGTERM, lambda *_args: sys.exit(143))
    results = []
    office.start()
    try:
        platform, ui = Platform(args, office), office.service("com.sun.star.ui.test.UITest")
        for ident, case in runnable.items():
            print("dialog", ident, flush=True)
            try:
                result = run_case(platform, ui, ident, case, args)
            except Exception as error:  # noqa: BLE001 - note it; start again only when the office really ended
                alive = office_alive(office)
                result = {"id": ident, "batch": case.batch, "en": case.en, "command": case.command,
                          "error": (f"checker error: {error!r}" if alive else f"office ended: {error!r}")[:300]}
                if not alive:
                    office.stop()
                    office.start()
                    platform, ui = Platform(args, office), office.service("com.sun.star.ui.test.UITest")
            with open(os.path.join(args.out, ident + ".json"), "w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=1)
            results.append(result)
    finally:
        office.stop()
    summary = []
    bad = 0
    for result in results:
        findings = [f for page in result.get("pages", []) for f in page["findings"]]
        hard = failing(findings, args.strict)
        bad += bool(hard)
        summary.append({"id": result["id"], "title": result.get("title"), "error": result.get("error"),
                        "gap": sum(f["kind"] == "gap" for f in findings),
                        "row_gap": sum(f["kind"] == "row-gap" for f in findings),
                        "clipped": sum(f["kind"] == "clipped" for f in findings),
                        "tight": sum(f["kind"] == "tight" for f in findings),
                        "unverified": sum(page.get("unverified", 0) for page in result.get("pages", [])),
                        "fit": sorted({f["target"] for f in findings if f["kind"] == "fit"}),
                        "min_gap_px": min((f["px"] for f in findings if f["kind"] in ("gap", "row-gap")), default=None),
                        "pages": len(result.get("pages", [])), "failing": len(hard)})
    meta = {"plugin": args.plugin, "lang": args.lang, "scale": args.scale, "instdir": os.path.abspath(args.instdir),
            "not_runnable": sorted(k for k, v in selected.items() if not v.command), "dialogs": summary}
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=1)
    for row in summary:
        print(json.dumps(row, ensure_ascii=False))
    return 1 if bad or any(r.get("error") for r in summary) else 0


def reanalyse(directory, scale):
    count = 0
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if not name.endswith(".json") or name == "summary.json" or "/work" in root:
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as handle:
                result = json.load(handle)
            if result.get("pages") and message_box(result.get("title")):
                result["error"] = f"message box instead of the dialog: {result['title']}"
                result["message"] = result.pop("pages")
            for page in result.get("pages", []):
                page["findings"] = analyse(page["dialog"], page["nodes"], result.get("scale", scale), result.get("plugin"))
                page["unverified"] = unverified(page["nodes"])
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=1)
            count += 1
    print("re-analysed", count, "results")
    return 0


# ---- self-test ----------------------------------------------------------------------------------------------------
def box(role, x, y, w, h, **extra):
    return dict({"role": role, "name": f"{role}@{x},{y}", "x": x, "y": y, "w": w, "h": h,
                 "bordered": role in BORDERED}, **extra)


def selftest_geometry():
    """The analysis on built-in windows: a bad one (3 px stacked spin boxes, a cut label, too tall) and a good one."""
    bad = [box("spin box", 100, 10, 80, 24), box("spin box", 100, 37, 80, 24), box("spin box", 100, 66, 80, 24),
           box("label", 10, 10, 60, 14, text=SAMPLE, text_box=[0, -2, 75, 17]),
           box("label", 10, 40, 90, 14, text="Thay thế bằng", text_box=[0, 0, 75, 17])]  # 3 px short: cut
    found = analyse({"w": 400, "h": 700}, bad, 100)
    kinds = sorted(f["kind"] for f in found)
    assert kinds == ["clipped", "clipped", "fit", "gap", "row-gap"], kinds
    assert [f["px"] for f in found if f["kind"] == "gap"] == [3]
    good = [box("spin box", 100, 10, 80, 24), box("spin box", 100, 40, 80, 24), box("push button", 186, 10, 60, 24),
            box("label", 10, 10, 80, 18, text=SAMPLE, text_box=[0, 1, 75, 16])]
    assert analyse({"w": 400, "h": 300}, good, 100) == []
    # a short line box without two-mark letters is a warning only
    tight = analyse({"w": 300, "h": 100}, [box("label", 0, 0, 40, 12, text="Chung", text_box=[0, 2, 36, 14]),
                                            box("label", 0, 30, 90, 12, text="Khóa sắp xếp 1",
                                                text_box=[0, 0, 80, 14])], 100)
    assert [(f["kind"], f["warning"]) for f in tight] == [("tight", True)] * 2 and failing(tight) == []
    assert message_box("Thông tin") and message_box("Information") and not message_box("Gạch nối từ")
    # a wide entry with two controls under its halves: both are its neighbours; an overlap is a negative gap
    halves = [box("text", 0, 0, 200, 24), box("text", 0, 26, 90, 24), box("text", 110, 27, 90, 24),
              box("combo box", 300, 0, 80, 24), box("combo box", 300, 23, 80, 24)]
    assert sorted(f["px"] for f in analyse({"w": 400, "h": 100}, halves, 100) if f["kind"] == "gap") == [-1, 2, 3]
    # a toolbar's flat buttons and a list's header bar over its rows are not neighbouring controls
    flat = [box("tool bar", 10, 10, 60, 24), box("push button", 10, 10, 30, 24), box("push button", 40, 10, 30, 24),
            box("table", 10, 50, 200, 18), box("table", 10, 68, 200, 100)]
    assert analyse({"w": 300, "h": 200}, flat, 100) == [], analyse({"w": 300, "h": 200}, flat, 100)
    # the same thresholds at 125 % (the toolkits do not scale .ui spacing): 4 px is a row-gap warning, not a gap
    four = [box("text", 0, 0, 80, 24), box("text", 0, 28, 80, 24)]
    assert [f["kind"] for f in analyse({"w": 100, "h": 60}, four, 100)] == ["row-gap"]
    assert [f["kind"] for f in analyse({"w": 100, "h": 60}, four, 125)] == ["row-gap"]
    # 1366x768 @125 % only reports: a 1400 px wide dialog fails the hard 1920 target only when above 1920
    wide = analyse({"w": 1400, "h": 600}, [], 125)
    assert [(f["target"], f["warning"]) for f in wide] == [("1366x768@125", True)]
    assert failing(wide) == []
    # Windows gives the outer window rect: Document Properties measured 857x709 with its title bar (HST5, 100 %,
    # work area 1366x728 target) fits; the same box as a Linux client area gets the 16x39 frame and does not
    assert [f for f in analyse({"w": 857, "h": 709}, [], 100, "win") if f["kind"] == "fit"] == []
    assert [f["size"] for f in analyse({"w": 857, "h": 709}, [], 100, "gtk3") if f["kind"] == "fit"] == [[873, 748]]
    assert [f["size"] for f in analyse({"w": 857, "h": 730}, [], 100, "win") if f["kind"] == "fit"] == [[857, 730]]
    print("geometry self-test: ok")


def selftest_live(args):
    """A VCL window built through the toolkit: two entries 3 px apart (red) and two 6 px apart (green), read back
    through the same accessibility walk as the dialogs."""
    import hst_gui
    import uno
    from com.sun.star.awt import Rectangle, WindowDescriptor
    from com.sun.star.awt.WindowClass import SIMPLE, TOP
    os.environ["HST_VCLPLUGIN"] = "gen" if args.plugin == "gtk3" else args.plugin
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "selftest"), args.port, display=args.display,
                            lang=args.lang)
    office.start()
    try:
        toolkit = office.service("com.sun.star.awt.Toolkit")
        attrs = uno.getConstantByName("com.sun.star.awt.WindowAttribute.BORDER") | \
            uno.getConstantByName("com.sun.star.awt.WindowAttribute.MOVEABLE") | \
            uno.getConstantByName("com.sun.star.awt.WindowAttribute.CLOSEABLE")

        border = uno.getConstantByName("com.sun.star.awt.WindowAttribute.BORDER")

        def descriptor(kind, service, parent, rect):
            d = WindowDescriptor()
            d.Type, d.WindowServiceName, d.Parent = kind, service, parent
            d.Bounds, d.WindowAttributes = Rectangle(*rect), attrs if kind == TOP else border
            return d

        top = toolkit.createWindow(descriptor(TOP, "dialog", None, (200, 200, 320, 160)))
        rects = [(20, 20, 120, 24), (20, 47, 120, 24), (180, 20, 120, 24), (180, 50, 120, 24)]
        children = [toolkit.createWindow(descriptor(SIMPLE, "edit", top, rect)) for rect in rects]
        for child in children:
            child.setVisible(True)
        top.setVisible(True)
        time.sleep(2)
        context = top.getProperty("XAccessible").getAccessibleContext()
        _dialog, nodes, _tabs = uno_nodes(context, role_names())
        gaps = [f for f in analyse({"w": 320, "h": 160}, nodes, 100) if f["kind"] in ("gap", "row-gap")]
        assert len([n for n in nodes if n["bordered"]]) == 4, nodes
        # only the left pair (3 px) is red; the right pair (6 px) is green
        assert [(f["kind"], f["px"], f["boxes"][0][0] < 150) for f in gaps] == [("gap", 3, True)], gaps
        top.dispose()
        print("live self-test: ok (3 px pair red, 6 px pair green)")
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir")
    parser.add_argument("--out", default=os.path.join(os.getcwd(), "dialog-layout"))
    parser.add_argument("--display", default=":143")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--plugin", choices=("gen", "gtk3", "win"), default="win" if os.name == "nt" else "gen")
    parser.add_argument("--lang", default="vi_VN.UTF-8")
    parser.add_argument("--scale", type=int, choices=(100, 125), default=100)
    parser.add_argument("--all", action="store_true", help="every candidate and the batches' own cases, not only the ranked list")
    parser.add_argument("--strict", action="store_true", help="row-gap and tight-line warnings fail too")
    parser.add_argument("--work-area", help="WxH: the measured work area of this machine for the hard target of "
                        "--scale (default: 1366x728 at 100 %%, 1920x1032 at 125 %%)")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--reanalyse", metavar="DIR", help="recompute the findings of a run's JSON files from their "
                        "saved controls (after a change to the analysis), with --scale unless a file names its own")
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    if args.selftest:
        selftest_geometry()
        if args.instdir:
            import hst_gui
            args.port = args.port or hst_gui.free_port()
            selftest_live(args)
        return 0
    if args.work_area:
        width, height = (int(v) for v in args.work_area.lower().split("x"))
        for name, (scale, _w, _h, hard) in list(TARGETS.items()):
            if scale == args.scale and hard:
                TARGETS[name] = (scale, width, height, hard)
    if args.reanalyse:
        return reanalyse(args.reanalyse, args.scale)
    if not args.instdir:
        parser.error("--instdir is required")
    if args.plugin == "win":
        import hst_gui_windows
        hst_gui_windows.install()
    elif args.plugin == "gtk3" and os.geteuid() == 0 and not os.environ.get("HST_LAYOUT_CHECK_SESSION"):
        import hst_gui
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.environ["HST_LAYOUT_CHECK_SESSION"] = "1"
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "HST_LAYOUT_CHECK_SESSION=1",
                              "dbus-run-session", "--", sys.executable] + sys.argv)
    import hst_gui
    args.port = args.port or hst_gui.free_port()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
