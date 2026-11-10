# SPDX-License-Identifier: AGPL-3.0-only
"""W8–W10/M7: native shortcuts and hover, observed through the OS accessibility tree (ribbon_os.py)."""
import time
from support import native, says, wait
from style_hover_preview_gui import state


def search(e, doc):
    import ribbon_os
    window = doc.CurrentController.Frame.ContainerWindow
    area = e.office.service("com.sun.star.awt.Toolkit").getWorkArea()
    window.setPosSize(area.X, area.Y + 35, area.Width, area.Height - 60, 15)  # full screen, as the owner works
    time.sleep(2)
    e.office.focus(window)
    before = ribbon_os.read(e, "search-before")
    anchors = ribbon_os.named(before, "Tìm tính năng")
    anchor = anchors[0] if anchors else None
    native("key", "alt+cmd+k" if e.office.system == "Darwin" else "alt+q")
    native("text", "bảng")
    def rows():
        nodes = ribbon_os.read(e)
        return nodes if [n for n in nodes if says(n.name, "trong tài liệu")] else None
    e.require(anchor is not None, "Có ô tìm trên ribbon", method="OS accessibility tree")
    nodes = wait(rows, 30)
    ribbon_os.read(e, "search-open")
    e.shot("search")
    finals = [n for n in nodes if says(n.name, "trong tài liệu")]
    final = max(finals, key=lambda n: n.y)
    e.require(final.name == "Tìm “bảng” trong tài liệu", "Dòng cuối tìm trong tài liệu",
              method="OS accessibility tree", final=final.name)
    popup = [n for n in nodes if n.name and n.kind in ("item", "button", "label") and n.h > 0 and
             anchor.y + anchor.h - 2 <= n.y <= final.y and abs(n.x - final.x) < 40]
    e.require(len(popup) >= 2 and max(n.y for n in popup) == final.y, "Kết quả nằm dưới ô tìm, dòng tìm tài liệu ở cuối",
              method="OS accessibility tree", anchor=anchor.box, rows=[(n.name, n.box) for n in popup])
    native("key", "escape")


def hover(e, doc):
    import ribbon_os
    window = doc.CurrentController.Frame.ContainerWindow
    area = e.office.service("com.sun.star.awt.Toolkit").getWorkArea()
    window.setPosSize(area.X, area.Y + 35, area.Width, area.Height - 60, 15)
    e.office.focus(window)
    doc.Text.String = "Đoạn văn kiểm tra xem trước kiểu."
    # Start from a style other than the default: at 150% the gallery shows only the default entry, and hovering
    # the paragraph's own style can show no change (r1-auto Windows run 42883100228).
    cursor = doc.Text.createTextCursor()
    cursor.gotoEnd(True)
    cursor.setPropertyValue("ParaStyleName", "Heading 1")
    current = doc.StyleFamilies.getByName("ParagraphStyles").getByName("Heading 1").DisplayName
    doc.UndoManager.clear()
    doc.setModified(False)
    time.sleep(2)
    styles = doc.StyleFamilies.getByName("ParagraphStyles")
    names = {styles.getByName(name).DisplayName for name in styles.ElementNames}
    nodes = ribbon_os.read(e, "hover")
    dx, dy = ribbon_os.screen_mapper(e, nodes, window)
    frame = ribbon_os.ribbon_frame(nodes)
    candidates = [n for n in nodes if n.name in names - {current} and n.w > 40 and frame and frame.contains(n)]
    # At 150% or 1440 pt the gallery shows a single entry: hover what is shown, at least one.
    e.require(len(candidates) >= 1, "Có ô kiểu trong nhóm Kiểu để rê chuột", method="OS accessibility tree",
              names=[n.name for n in candidates], offset=[dx, dy])
    initial, text = state(doc), doc.Text.String
    changed = 0
    wx, wy, ww, wh = (lambda r: (r.X, r.Y, r.Width, r.Height))(window.getPosSize())
    for index, node in enumerate(candidates):
        cx, cy = node.center()
        native("move", int(cx + dx), int(cy + dy))
        time.sleep(1)
        during = state(doc)
        if during[0] != initial[0]:
            changed += 1
        e.require(during[1:] == initial[1:], "Rê chuột không thêm hoàn tác hoặc sửa tài liệu", before=initial, during=during)
        e.shot("hover-" + str(index))
        native("move", wx + ww // 2, wy + wh - 100)
        time.sleep(1)
        e.require(state(doc) == initial, "Rời chuột trả kiểu ban đầu", after=state(doc))
    e.require(changed > 0, "Đoạn văn đổi kiểu trong lúc rê", previews=changed, hovered=len(candidates),
              method="pointer from the OS accessibility tree")
    native("key", "cmd+z" if e.office.system == "Darwin" else "ctrl+z")
    e.require(state(doc) == initial and doc.Text.String == text, "Hoàn tác không đổi gì sau xem trước", after=state(doc))
    e.shot("after-undo")


def dump_os_tree(e, label):
    import json
    for kind, arg in (("os-a11y", "diagnose"), ("native-tree", 2500)):
        try:
            value = native("tree", arg, timeout=180)
        except Exception as error:
            value = f"{type(error).__name__}: {error}"
        (e.out / f"{kind}-{label}.log").write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")


def run(e):
    doc = e.office.load("private:factory/swriter")
    try:
        time.sleep(3)
        e.office.focus(doc.CurrentController.Frame.ContainerWindow)
        dump_os_tree(e, "open")  # while the document is on screen (a dump after close saw no window at all)
        if e.item in {"W8", "M7"}:
            from ribbon_fit import run as fit
            fit(e, doc)
        if e.item in {"W9", "M7"}:
            search(e, doc)
        if e.item in {"W10", "M7"}:
            hover(e, doc)
    finally:
        try:
            doc.setModified(False)
            doc.close(True)
        except Exception as error:  # an office that dies on close must not hide what the item measured
            e.checks.append(dict(ok=False, message="Đóng tài liệu làm office dừng", error=f"{type(error).__name__}"))
