# SPDX-License-Identifier: AGPL-3.0-only
"""Steps of check-backstage-flows.py: AT-SPI lookups, the New page and the keyboard."""
import os
import time

import backstage_gui as gui
import hst_gui

ND30 = "org.hst.office.vi:Nd30Wizard"


def found(role=None):
    return [(name, node) for got, name, node in gui.showing(gui.walk(gui.nd30.office_app(), []))
            if role is None or got == role]


def named(name, role=None):
    return [node for got, node in found(role) if got == name]


def menu_items():
    return [name for name, _node in found("menu item") if name]


def template_rows():
    """(template, category) rows of the New page's compact list."""
    lists = named("Mẫu", "tree table") or named("Mẫu", "table")
    if not lists:
        return []
    cells = [node.name for _r, _n, node in gui.showing(gui.walk(lists[0], [])) if node.getRoleName() == "table cell"]
    return list(zip(cells[0::2], cells[1::2]))


def check_new(office, frame, interceptor, out):
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Mới"])
    time.sleep(2)
    hst_gui.screenshot(os.path.join(out, "moi.png"), office.display)
    rows = template_rows()
    gui.record("New lists the templates in a compact list", len(rows) >= 5, rows[:4])
    gui.record("the list shows the HST template groups", any(group.startswith("HST") for _name, group in rows),
               sorted({group for _name, group in rows})[:6])
    samples = os.path.join(office.program, "..", "share", "template", "common", "l10n")
    gui.record("the upstream language samples are not installed", not os.path.exists(samples))
    gui.press(gui.view_items()["Quản lý mẫu…"])
    gui.record("New: Manage Templates opens the Templates dialog", gui.expect_call(interceptor, ".uno:NewDoc"))
    gui.record("New: Manage Templates closed the panel", gui.wait_state(False))
    # a template opens as a new untitled document
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Mới"])
    time.sleep(1.5)
    lists = named("Mẫu", "tree table") or named("Mẫu", "table")
    before = office.desktop().getFrames().getCount()
    if lists:
        cell = [node for _r, _n, node in gui.showing(gui.walk(lists[0], [])) if node.getRoleName() == "table cell"]
        box = cell[0].queryComponent().getExtents(0) if cell else None
        if box:
            gui.xdo(office.display, "mousemove", str(box.x + 20), str(box.y + box.height // 2), "click", "--repeat", "2",
                    "--delay", "60", "1")
    gui.record("a template closes the panel", gui.wait_state(False))
    deadline = time.time() + 20
    while time.time() < deadline and office.desktop().getFrames().getCount() <= before:
        time.sleep(0.5)
    frames = office.desktop().getFrames()
    gui.record("a template opens as a new document", frames.getCount() > before, "%d -> %d" % (before, frames.getCount()))
    if frames.getCount() > before:
        created = frames.getByIndex(frames.getCount() - 1).getController().getModel()
        gui.record("the new document is untitled", not created.getURL(), created.getURL())
        gui.close_document(created)
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Mới"])
    time.sleep(1)
    gui.press(gui.view_items()["Văn bản hành chính (NĐ 30)"])
    gui.record("New: the Decree 30 button runs the wizard", gui.expect_call(interceptor, ND30))
    gui.wait_state(False)
    interceptor.calls.clear()
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Văn bản hành chính (NĐ 30)"])
    gui.record("Home: the Decree 30 tile runs the wizard", gui.expect_call(interceptor, ND30))
    gui.wait_state(False)


def check_keyboard(office, frame, out):
    display = office.display
    if gui.is_open():
        gui.xdo(display, "key", "Escape")
        gui.wait_state(False)
    gui.xdo(display, "key", "alt")
    time.sleep(1.2)
    gui.xdo(display, "key", "f")
    gui.record("the Alt, F KeyTip opens the panel", gui.wait_state(True))
    time.sleep(0.4)
    first = gui.focused_name()
    gui.xdo(display, "key", "Right")
    time.sleep(0.4)
    gui.record("Right moves from the left column into the page", first == "Trang chủ" and gui.focused_name() != first,
               "%s -> %s" % (first, gui.focused_name()))
    gui.xdo(display, "key", "Escape")
    gui.record("Esc closes the panel", gui.wait_state(False))
