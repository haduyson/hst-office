# SPDX-License-Identifier: AGPL-3.0-only
"""Home tab checks of check-ribbon-home-fit.py: the "Công cụ" group, Find & Replace in the paragraph group and the
feature search in the "Trang đầu" menu (hst-ribbon-home-fit.patch)."""
import time

TOOLS = "Công cụ"
MENU = "Trang đầu"
SEARCH = "Tìm tính năng"
FIND = "Tìm và thay thế"
SECOND_ROW = {"writer": "Văn bản hành chính"}  # Sheets: sort and filter icons; Slides: the slide show icon
PARAGRAPH = {"writer": "Đoạn văn", "calc": "Căn chỉnh", "impress": "Đoạn văn"}
ROLES = ("push button", "toggle button", "push button menu", "menu button")


def items(tabs):
    """(name, box) of the showing buttons and tool items in the ribbon band."""
    found = []
    for node in tabs.walk(tabs.office_app()):
        try:
            role, name = node.getRoleName(), node.name or ""
            if not name or role not in ROLES or not node.getState().contains(_showing()):
                continue
            box = tabs.extents(node)
        except Exception:  # noqa: BLE001  widgets come and go
            continue
        if 40 < box[1] < 200 and box[2] > 0:
            found.append((name, box))
    return found


def _showing():
    import pyatspi
    return pyatspi.STATE_SHOWING


def group_range(captions, name):
    """x range of the group whose caption is `name`: halfway to the neighbouring captions."""
    ordered = sorted(captions, key=lambda c: c[1][0])
    index = next(i for i, c in enumerate(ordered) if c[0] == name)
    box = ordered[index][1]
    left = (ordered[index - 1][1][0] + ordered[index - 1][1][2] + box[0]) / 2 if index else 0
    right = (box[0] + box[2] + ordered[index + 1][1][0]) / 2 if index + 1 < len(ordered) else 10 ** 6
    return left, right


def check_tools_group(tabs, args, app, width, captions):
    """At a width where nothing folds: the group "Công cụ" has its rows in order, one feature search on Home."""
    found = items(tabs)
    names = [c[0] for c in captions]
    tabs.record(f"[{app} {width}] group '{TOOLS}' shows", TOOLS in names, names)
    if TOOLS not in names:
        return
    left, right = group_range(captions, TOOLS)
    rows = [n for n, b in sorted((i for i in found if left <= i[1][0] < right), key=lambda i: (i[1][1], i[1][0]))]
    expected_first, expected_last = MENU, SEARCH
    ok = bool(rows) and rows[0] == expected_first and rows[-1] == expected_last
    if app in SECOND_ROW:
        ok = ok and rows == [MENU, SECOND_ROW[app], SEARCH]
    tabs.record(f"[{app} {width}] '{TOOLS}' rows: {MENU}, …, {SEARCH}", ok, rows)
    searches = [n for n, _b in found if n.startswith(SEARCH)]
    tabs.record(f"[{app} {width}] one '{SEARCH}' on Home, without '…'", searches == [SEARCH], searches)


def check_find_in_paragraph(tabs, app, width, captions):
    group = PARAGRAPH[app]
    if group not in [c[0] for c in captions]:
        return
    left, right = group_range(captions, group)
    finds = [b for n, b in items(tabs) if n == FIND]
    tabs.record(f"[{app} {width}] '{FIND}' is a button of '{group}'",
                len(finds) == 1 and left <= finds[0][0] < right, (finds, left, right))


def check_menu_has_search(tabs, args, app):
    menu = [b for n, b in items(tabs) if n == MENU]
    tabs.record(f"[{app}] '{MENU} ▾' menu button", len(menu) == 1, menu)
    if len(menu) != 1:
        return
    tabs.click(args.display, menu[0])
    time.sleep(1.5)
    entries = []
    for node in tabs.walk(tabs.office_app()):
        try:
            if node.getRoleName() in ("menu item", "check menu item") and node.getState().contains(_showing()):
                entries.append(node.name or "")
        except Exception:  # noqa: BLE001
            continue
    tabs.record(f"[{app}] '{MENU}' menu offers '{SEARCH}'", any(e.startswith(SEARCH) for e in entries), entries)
    tabs.xdo(args.display, "key", "Escape")
    time.sleep(1)
