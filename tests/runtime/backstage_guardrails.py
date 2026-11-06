# SPDX-License-Identifier: AGPL-3.0-only
"""Design-around guardrails of the File panel, read through AT-SPI while it is open (see check-backstage.py)."""
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


def guardrails(label):
    """While the panel is open: the ribbon and the document show, and the panel is a window of its own below the
    ribbon (it covers no part of the ribbon and not all of the document). Returns the panel's box."""
    found = showing(walk(nd30.office_app(), []))
    items = {name: node for role, name, node in found if role == "push button" and name in ALL_ITEMS}
    if "Thông tin" not in items:
        record(label + ": the panel is open for the guardrail checks", False)
        return None
    panel = toplevel_of(items["Thông tin"])
    tabs = [node for role, name, node in found if role == "page tab" and name in FILE_TAB_NAMES]
    frame = toplevel_of(tabs[0]) if tabs else None
    record(label + ": the panel is a separate floating window",
           panel is not None and frame is not None and panel != frame and panel.getRoleName() != "frame",
           "%s / %s" % (panel.getRoleName() if panel else None, frame.getRoleName() if frame else None))
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
        # never over the ribbon; the ribbon's own bottom margin (below its tab control) may lie in between
        record(label + ": the panel starts at the bottom edge of the ribbon", bottom - 1 <= box[1] <= bottom + 16,
               "ribbon bottom %d, panel top %d" % (bottom, box[1]))
    documents = [node for role, name, node in in_frame if role in DOCUMENT_ROLES]
    if documents:
        doc = extents(documents[0])
        right = doc[0] + doc[2] > box[0] + box[2]
        record(label + ": the document stays visible beside the panel", right, "document %s, panel %s" % (doc, box))
    else:
        record(label + ": the document stays visible beside the panel", False, "no document node showing")
    return box


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
