# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Steps of check-backstage-flows.py: the "Xuất PDF dạng sách" button of the Export page and the "Cập nhật HST Office"
entry of the Info page (the bundled extension's org.hst.office.update: commands)."""
import time

import backstage_gui as gui
from backstage_flow_steps import named

BOOKLET = ".uno:ExportDirectToPDF"
UPDATE_CHECK = "org.hst.office.update:Check"
UPDATE_AVAILABLE = "org.hst.office.update:Available"
STUBBED = {BOOKLET, UPDATE_CHECK, UPDATE_AVAILABLE}


def filter_data(args):
    """{name: value} of the FilterData argument of a dispatch."""
    for prop in args or ():
        if prop.Name == "FilterData":
            return {p.Name: p.Value for p in prop.Value}
    return {}


def open_page(office, frame, item):
    gui.reopen(office, frame)
    gui.press(gui.view_items()[item])
    time.sleep(0.8)


def check_extension_answers(office, frame):
    """The real extension (no interceptor yet) has the status command the entry and the File tab dot listen to."""
    import uno
    try:
        url = uno.createUnoStruct("com.sun.star.util.URL")
        url.Complete = UPDATE_AVAILABLE
        _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
        gui.record("the extension answers %s" % UPDATE_AVAILABLE, frame.queryDispatch(url, "", 0) is not None)
    except Exception as error:  # noqa: BLE001 - recorded as a failure, the other steps still run
        gui.record("the extension answers %s" % UPDATE_AVAILABLE, False, repr(error))


def check_booklet_and_update(office, frame, interceptor):
    open_page(office, frame, "Xuất")
    buttons = named("Xuất PDF dạng sách", "push button")
    gui.record("Export has the booklet button", bool(buttons))
    if buttons:
        gui.press(buttons[0])
        called = gui.expect_call(interceptor, BOOKLET)
        gui.record("the booklet button exports a PDF booklet",
                   called and filter_data(interceptor.args.get(BOOKLET)).get("Booklet") is True,
                   filter_data(interceptor.args.get(BOOKLET)))
        gui.record("the booklet button closes the panel", gui.wait_state(False))
    for available in (False, True):
        interceptor.states[UPDATE_AVAILABLE] = available
        open_page(office, frame, "Thông tin")
        buttons = named("Cập nhật HST Office", "push button")
        note = bool(named("Đã có phiên bản mới để cài đặt.", "label"))
        gui.record("Info has the update entry (update known: %s)" % available, bool(buttons))
        gui.record("Info says a new version is ready only when one is known (%s)" % available, note == available)
        if buttons and available:
            interceptor.calls.clear()
            gui.press(buttons[0])
            gui.record("the update entry runs %s" % UPDATE_AVAILABLE, gui.expect_call(interceptor, UPDATE_AVAILABLE))
        gui.xdo(office.display, "key", "Escape")
        gui.wait_state(False)
