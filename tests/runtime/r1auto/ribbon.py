# SPDX-License-Identifier: AGPL-3.0-only
"""W8–W10/M7: native shortcuts and hover, observed through UNO accessibility."""
import time
from access import box, center, labels, named, snapshot
from support import native, says, wait
from style_hover_preview_gui import state


def search(e, doc):
    from com.sun.star.accessibility.AccessibleRole import LIST_ITEM, MENU_ITEM
    e.office.focus(doc.CurrentController.Frame.ContainerWindow)
    anchors = named(e.office, "Tìm tính năng") or named(e.office, "Search features")
    anchor = next((box(n) for n in anchors if box(n)[1] < 200), None)
    native("key", "alt+cmd+k" if e.office.system == "Darwin" else "alt+q")
    native("text", "bảng")
    found = wait(lambda: [n for n in snapshot(e.office)
                          if says(n.getAccessibleName(), "trong tài liệu", "in the document")])
    e.shot("search")
    final = found[-1]
    e.require(final.getAccessibleName() in ("Tìm “bảng” trong tài liệu", "Find “bảng” in the document"),
              "Dòng cuối tìm trong tài liệu",
              labels=labels(e.office))
    e.require(anchor is not None, "Có ô tìm trên ribbon")
    popup_rows = [n for n in snapshot(e.office) if n.getAccessibleRole() in (LIST_ITEM, MENU_ITEM) and
                  box(n)[1] >= anchor[1] + anchor[3] - 2 and box(n)[1] <= box(final)[1]]
    e.require(len(popup_rows) >= 2 and max(box(n)[1] for n in popup_rows) == box(final)[1],
              "Kết quả nằm dưới ô tìm, dòng tìm tài liệu ở cuối", anchor=anchor,
              rows=[(n.getAccessibleName(), box(n)) for n in popup_rows])
    native("key", "escape")


def hover(e, doc):
    window = doc.CurrentController.Frame.ContainerWindow
    window.setPosSize(0, 35, 1800, 900, 15)
    e.office.focus(window)
    doc.Text.String = "Đoạn văn kiểm tra xem trước kiểu."
    doc.UndoManager.clear()
    doc.setModified(False)
    styles = doc.StyleFamilies.getByName("ParagraphStyles")
    names = {styles.getByName(name).DisplayName for name in styles.ElementNames}
    candidates = [n for n in snapshot(e.office) if n.getAccessibleName() in names and
                  box(window)[1] < box(n)[1] < box(window)[1] + 260 and box(n)[2] > 40]
    e.require(len(candidates) >= 2, "Có ít nhất hai ô kiểu để rê chuột", names=[n.getAccessibleName() for n in candidates])
    initial, text = state(doc), doc.Text.String
    changed = 0
    for index, node in enumerate(candidates):
        native("move", *center(node))
        during = state(doc)
        if during[0] != initial[0]:
            changed += 1
        e.require(during[1:] == initial[1:], "Rê chuột không thêm hoàn tác hoặc sửa tài liệu", before=initial, during=during)
        e.shot("hover-" + str(index))
        wx, wy, ww, wh = box(window)
        native("move", wx + ww // 2, wy + wh - 100)
        e.require(state(doc) == initial, "Rời chuột trả kiểu ban đầu", after=state(doc))
    e.require(changed > 0, "Đoạn văn đổi kiểu trong lúc rê", previews=changed)
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
