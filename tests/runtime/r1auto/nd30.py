# SPDX-License-Identifier: AGPL-3.0-only
"""W5/W7/M5/M6: real native input against the installed wizard."""
import time
from support import background, native, wait
from access import box, center, context, walk, visible


def run(e):
    from hst_office import data_files, wizard_nd30
    office = e.office
    doc = office.load("private:factory/swriter")
    wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
    thread = background(wizard.run, doc.CurrentController.Frame.ContainerWindow)
    try:
        wait(lambda: wizard.picker.handler and wizard.d.dialog.getPeer(), 60)
        dialog, picker = wizard.d.dialog, wizard.picker
        office.focus(dialog)
        e.shot("dialog")
        if e.item == "W5":
            picker.field.setFocus()
            native("key", "ctrl+a")
            native("text", "quyet")
            wait(lambda: picker.open)
            e.shot("quyet")
            native("key", "tab")
            e.require(picker.current == "quyet-dinh" and not picker.open,
                      "Tab chọn Quyết định và đóng danh sách", chosen=picker.current, opened=picker.open)
            field = dialog.getControl("parentAgency")
            e.require(field.getPeer().hasFocus(), "Con trỏ sang Cơ quan chủ quản")
            e.shot("tab")
        elif e.item in {"W7", "M5"}:
            text = "Ủy ban nhân dân tỉnh Quảng Ngãi"
            for name in ("parentAgency", "agency", "place"):
                control = dialog.getControl(name)
                control.setFocus()
                native("key", "cmd+a" if office.system == "Darwin" else "ctrl+a")
                native("text", text)
                time.sleep(1)
                e.shot("typed-" + name)  # before any check: shows a popup that took the keyboard, if one did
                e.require(control.getText() == text, "Giữ đúng chữ và dấu khi nhập", field=name,
                          value=control.getText(), bounds=box(control))
                # Glyph rows measured in the screenshot (getCharacterBounds returned only empty rectangles).
                area = office.service("com.sun.star.awt.Toolkit").getWorkArea().Width
                shot = e.out / ("typed-" + name + ".png")
                band = native("field-text", shot, *box(control), area)
                e.require(band.get("ink") and not band.get("clipped"), "Khung chữ Ủy nằm trọn trong ô",
                          field=name, **band)
                e.require(abs(band["above"] - band["below"]) <= max(3, band["inner_height"] * 0.2),
                          "Khung chữ được căn giữa theo chiều dọc", field=name, **band)
            e.review("Kiểm tra căn giữa, đuôi chữ y và dấu Ủ trên các ô nhập", "vietnamese-fields")
        else:
            native("click", *center(dialog.getControl("typeOpen")))
            wait(lambda: picker.open)
            popup = context(picker.list)
            rows = [n for n in walk(popup) if visible(n) and n.getAccessibleName() in
                    {label for label, ident in picker.table if ident}]
            e.require(len(rows) >= 3, "Quan sát được các dòng danh sách", rows=len(rows))
            observed = []
            for node in rows:
                label = node.getAccessibleName()
                native("move", *center(node))
                selected = picker.list.getSelectedItemPos()
                wanted = next(i for i, row in enumerate(picker.table) if row[0] == label)
                observed.append(dict(label=label, selected=selected, wanted=wanted))
                e.require(selected == wanted and picker.open, "Dòng sáng đi theo con trỏ", **observed[-1])
            e.shot("hover")
            agency = box(dialog.getControl("agency"))
            target = next((node for node in rows if agency[1] <= center(node)[1] < agency[1] + agency[3]), None)
            e.require(target is not None, "Có dòng nằm trên ô Cơ quan ban hành", agency=agency)
            label = target.getAccessibleName()
            chosen = next(ident for name, ident in picker.table if name == label)
            native("click", *center(target))
            e.require(picker.current == chosen and not picker.open, "Bấm chọn đúng dòng và đóng danh sách",
                      expected=chosen, actual=picker.current)
            e.require(not dialog.getControl("agency").getPeer().hasFocus(), "Ô bị che không nhận cú bấm")
            e.shot("selected")
    finally:
        dialog = wizard.d.dialog
        dialog.endExecute()
        thread.join(5)
        doc.setModified(False)
        doc.close(True)
