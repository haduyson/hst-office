# SPDX-License-Identifier: AGPL-3.0-only
"""GUI checks of the authored Extensions tab ("Phần mở rộng"), used by check-ribbon-hst-commands.py.

The expected layout is the one the unit test tests/unit/test_ribbon_extensions_tab.py holds for the patch.
"""
import importlib.util
import os
import sys
import time

import ribbon_tabs_gui as gui

VI = "org.hst.office.vi:"
MOVED = {"Kiểm tra cập nhật", "Kiểm tra cập nhật HST Office", "Thiết lập USB Token", "Macro VBA", "Ngôn ngữ giao diện"}
BUTTONS = ("push button", "toggle button", "push button menu", "menu button")


def _tab_spec():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "unit", "test_ribbon_extensions_tab.py")
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("test_ribbon_extensions_tab", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TAB = _tab_spec()
# app -> [(caption, [(one-line accessible name, command)])]
EXTENSION_TAB = {app: [(caption, [(label.replace("\n", " "), VI + command) for label, command, _ in buttons])
                       for caption, buttons in layout] for app, layout in TAB.LAYOUT.items()}
# Every tool name the tab can show, to tell its items from the rest of the ribbon.
KNOWN = {name for layout in EXTENSION_TAB.values() for _, buttons in layout for name, _ in buttons} | MOVED


def tab_buttons():
    """(name, box) of the showing Extensions tab tools, left to right."""
    found = {}
    for _name, _role, _box, bar in gui.ribbon_nodes(("tool bar",)):
        for i in range(bar.childCount):
            child = bar.getChildAtIndex(i)
            if child is not None and child.name in KNOWN and gui.showing(child):
                found[child.name] = gui.extents(child)
    for name, _role, box, _node in gui.ribbon_nodes(BUTTONS):
        if name in KNOWN:
            found.setdefault(name, box)
    return sorted(found.items(), key=lambda item: item[1][0])


def check_extension_tab(args, office, app, wid, record, shot):
    """Groups, captions and buttons at 1485 px, the date split button, and the fit beside the banner at 1366 px."""
    if not record(f"[{app}] Phần mở rộng opens", gui.open_tab(args.display, "Phần mở rộng")):
        return
    shot(f"{app}-phan-mo-rong-1485")
    layout = EXTENSION_TAB[app]
    expected = [name for _, group in layout for name, _ in group]
    # the groups merged from the Developer tab (Macro VBA, ...) follow the HST groups; only the HST tools are checked
    buttons = [(name, box) for name, box in tab_buttons() if name in expected]
    names = [name for name, _ in buttons]
    record(f"[{app}] Phần mở rộng shows the HST buttons in order", names == expected, names)
    captions = sorted((n for n in gui.ribbon_nodes(("label",)) if n[0] in {c for c, _ in layout}), key=lambda n: n[2][0])
    record(f"[{app}] group captions in order", [n[0] for n in captions] == [c for c, _ in layout], [n[0] for n in captions])
    for (caption, group), node in zip(layout, captions):  # each caption sits under its own buttons
        boxes = [box for name, box in buttons if name in {n for n, _ in group}]
        if boxes:
            left, right = min(b[0] for b in boxes), max(b[0] + b[2] for b in boxes)
            record(f"[{app}] '{caption}' is under its buttons",
                   left - 12 <= node[2][0] + node[2][2] / 2 <= right + 12 and node[2][1] > max(b[1] for b in boxes),
                   (node[2], left, right))
    small = [name for name, box in buttons if box[3] < 32 + 2 * 14]  # 32 px icon above two text lines
    record(f"[{app}] buttons are large (icon and two text lines)", bool(buttons) and not small, small or buttons[:1])
    if app in TAB.SPLIT:
        check_date_menu(args, app, buttons, record, shot)
    gui.xdo(args.display, "windowsize", wid, "1366", "900")
    time.sleep(3)
    shot(f"{app}-phan-mo-rong-1366")
    _top, _doc_tabs, banner = gui.geometry()
    narrow = tab_buttons()
    overlap = [name for name, box in narrow if banner and box[0] + box[2] > banner[0]]
    folded = [name for name in expected if name not in {n for n, _ in narrow}]
    record(f"[{app}] 1366 px: no button under the banner", banner is not None and not overlap, (banner, overlap))
    chevron = [n for n in gui.ribbon_nodes(BUTTONS) if banner and n[2][0] < banner[0] and n[0] not in KNOWN and n[2][2] < 40]
    record(f"[{app}] 1366 px: shown {len(narrow)}/{len(expected)}, folded groups reach the chevron",
           not folded or bool(chevron), (folded, [n[0] for n in chevron]))
    gui.xdo(args.display, "windowsize", wid, "1485", "900")
    time.sleep(3)


def check_date_menu(args, app, buttons, record, shot):
    split = dict(buttons).get("Định dạng ngày tháng")
    if not record(f"[{app}] 'Định dạng ngày tháng' is a button", split is not None, [b[0] for b in buttons]):
        return
    # the arrow part at the right end of the split button
    gui.xdo(args.display, "mousemove", str(split[0] + split[2] - 5), str(split[1] + split[3] // 2), "click", "1")
    time.sleep(1.5)
    items = [n[0] for n in sorted(gui.ribbon_nodes(("menu item", "check menu item", "radio menu item"), band=2000),
                                  key=lambda n: n[2][1])]
    shot(f"{app}-dinh-dang-ngay-thang-menu")
    record(f"[{app}] date menu lists the four formats", items == [label for _, label in TAB.DATE_MENU], items)
    gui.xdo(args.display, "key", "Escape")
    time.sleep(1)
