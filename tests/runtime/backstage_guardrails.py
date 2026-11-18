# SPDX-License-Identifier: AGPL-3.0-only
"""Design-around guardrails of the File panel, read through AT-SPI while it is open (see check-backstage.py)."""
import os
import subprocess
import time

from backstage_gui import ALL_ITEMS, nd30, record, showing, walk, xdo

# the ribbon's File tab (and the classic menu bar's File menu)
FILE_TAB_NAMES = ("Tệp tin",)
DOCUMENT_ROLES = ("document text", "document spreadsheet", "document presentation")


def extents(node):
    box = node.queryComponent().getExtents(0)
    return box.x, box.y, box.width, box.height


def toplevel_of(node):
    """The application's child (a frame or a window) that holds `node`."""
    while node is not None:
        parent = node.parent
        if parent is None or parent.getRoleName() == "application":
            return node
        node = parent
    return None


# the accessible name of the panel's box ("panel" in hstbackstage.ui)
PANEL_NAMES = ("Tệp tin", "File")


def panel_of(node):
    """The File panel's box around `node`; the window of its own of the former drop-down."""
    while node is not None:
        parent = node.parent
        if node.name in PANEL_NAMES and node.getRoleName() not in ("page tab", "push button"):
            return node
        if parent is None or parent.getRoleName() == "application":
            return node
        node = parent
    return None


def guardrails(label):
    """While the panel is open: the ribbon and the document show, and the panel is a part of the document's window
    below the ribbon (it covers no part of the ribbon and not all of the document). Returns the panel's box."""
    found = showing(walk(nd30.office_app(), []))
    items = {name: node for role, name, node in found if role == "push button" and name in ALL_ITEMS}
    if "Thông tin" not in items:
        record(label + ": the panel is open for the guardrail checks", False)
        return None
    panel = panel_of(items["Thông tin"])
    tabs = [node for role, name, node in found if role == "page tab" and name in FILE_TAB_NAMES]
    frame = toplevel_of(tabs[0]) if tabs else None
    # as in the reference suite the panel moves and resizes with the window (a window of its own was left behind and
    # closed by a press on the title bar)
    record(label + ": the panel is a part of the document's window",
           panel is not None and frame is not None and toplevel_of(panel) == frame,
           "%s / %s" % (toplevel_of(panel).getRoleName() if panel else None,
                        frame.getRoleName() if frame else None))
    in_frame = [(role, name, node) for role, name, node in found if frame is not None and toplevel_of(node) == frame]
    # the ribbon's tab control (tabs and the selected tab's groups) is at the top of the window; Sheets also has the
    # sheet tabs at the bottom
    ribbon = [node for role, name, node in in_frame if role == "page tab list" and extents(node)[1] < 100]
    home = [name for role, name, node in in_frame if role == "page tab" and name == "Trang đầu"]
    record(label + ": the ribbon stays visible", bool(ribbon) and bool(home), [name for role, name, _n in in_frame
                                                                              if role == "page tab"][:6])
    box = extents(panel)
    if ribbon:
        bottom = max(extents(node)[1] + extents(node)[3] for node in ribbon)
        # never over the ribbon; the rest of the NotebookBar below its tab control (its margin, up to about 30 px in
        # Slides) lies in between
        # the document tab strip (about 32 px) may lie in between: the panel starts below it
        record(label + ": the panel starts at the bottom edge of the ribbon", bottom - 1 <= box[1] <= bottom + 80,
               "ribbon bottom %d, panel top %d" % (bottom, box[1]))
    strips = [node for role, name, node in in_frame if role == "panel" and name == "Thẻ tài liệu"]
    if strips:  # owner 14/11/2026: the document tab strip stays visible while the panel is open
        strip = extents(strips[0])
        record(label + ": the document tab strip stays visible above the panel", strip[1] + strip[3] <= box[1] + 1,
               "strip %s, panel top %d" % (strip, box[1]))
    documents = [node for role, name, node in in_frame if role in DOCUMENT_ROLES]
    if documents:
        doc = extents(documents[0])
        right = doc[0] + doc[2] > box[0] + box[2]
        record(label + ": the document stays visible beside the panel", right, "document %s, panel %s" % (doc, box))
    else:
        record(label + ": the document stays visible beside the panel", False, "no document node showing")
    return box


def panel_box():
    """The box of the open panel's left column (its "Thông tin" item), or None."""
    found = showing(walk(nd30.office_app(), []))
    items = [node for role, name, node in found if role == "push button" and name == "Thông tin"]
    return extents(items[0]) if items else None


def follows_window_move(label, display, window_id, dx=90, dy=70):
    """Move the document's window: the open panel stays open and moves with it."""
    before = panel_box()
    geometry = subprocess.run(["xdotool", "getwindowgeometry", str(window_id)], env=dict(os.environ, DISPLAY=display),
                              capture_output=True, text=True, timeout=20).stdout
    position = [line for line in geometry.splitlines() if "Position:" in line]
    if before is None or not position:
        record(label + ": the panel follows the window", False, "panel %s, window %s" % (before, geometry.strip()))
        return
    x, y = (int(v) for v in position[0].split("Position:")[1].split("(")[0].strip().split(","))
    xdo(display, "windowmove", str(window_id), str(x + dx), str(y + dy))
    time.sleep(1.0)
    after = panel_box()
    record(label + ": the panel stays open when the window moves", after is not None)
    if after is not None:
        record(label + ": the panel moves with the window",
               abs(after[0] - before[0] - dx) <= 2 and abs(after[1] - before[1] - dy) <= 2,
               "%s -> %s, window moved by %d,%d" % (before[:2], after[:2], dx, dy))
    xdo(display, "windowmove", str(window_id), str(x), str(y))
    time.sleep(0.5)


def click_file_tab(display):
    """Click the ribbon's File tab; False when the ribbon shows none."""
    tabs = [node for role, name, node in showing(walk(nd30.office_app(), []))
            if role == "page tab" and name in FILE_TAB_NAMES]
    if not tabs:
        return False
    x, y, width, height = extents(tabs[0])
    xdo(display, "mousemove", str(x + width // 2), str(y + height // 2), "click", "1")
    time.sleep(0.3)
    return True
