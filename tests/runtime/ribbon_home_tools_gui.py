# SPDX-License-Identifier: AGPL-3.0-only
"""Home tab checks of check-ribbon-home-fit.py for the 1.0.2 ribbon: Find & Replace is a button of the "Chỉnh sửa"
(editing) group, as in the reference suite; the old "Công cụ" block and its "Trang đầu ▾" menu are gone and the
feature search is the search box of the tab row (hst-ribbon-feature-search.patch), not a Home button."""

EDITING = "Chỉnh sửa"
OLD_TOOLS = "Công cụ"
SEARCH = "Tìm tính năng"
# the editing group's find button (Sheets: "Tìm và chọn", as the reference suite's spreadsheet)
FIND = {"writer": "Thay thế", "calc": "Tìm và chọn", "impress": "Thay thế", "draw": "Thay thế"}
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
            found.append((name.replace("\n", " "), box))  # a two-line label is one name
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


def check_wide_home(tabs, app, width, captions):
    """Where nothing folds: no old "Công cụ" group, no feature search button on the page; the tab row has the box."""
    names = [c[0] for c in captions]
    tabs.record(f"[{app} {width}] no '{OLD_TOOLS}' group (its commands moved to '{EDITING}')", OLD_TOOLS not in names, names)
    searches = [n for n, _b in items(tabs) if n.startswith(SEARCH)]
    tabs.record(f"[{app} {width}] no '{SEARCH}' button on Home", not searches, searches)
    row = []
    for node in tabs.walk(tabs.office_app()):
        try:
            if (node.name or "").startswith(SEARCH) and node.getState().contains(_showing()):
                row.append(tabs.extents(node))
        except Exception:  # noqa: BLE001  widgets come and go
            continue
    tabs.record(f"[{app} {width}] the tab row has the '{SEARCH}' box", any(b[1] < 45 for b in row), row)


def check_find_in_editing(tabs, app, width, captions):
    if EDITING not in [c[0] for c in captions]:
        return  # the group is its button at this width
    left, right = group_range(captions, EDITING)
    finds = [b for n, b in items(tabs) if n == FIND[app]]
    tabs.record(f"[{app} {width}] '{FIND[app]}' is a button of '{EDITING}'",
                len(finds) == 1 and left <= finds[0][0] < right, (finds, left, right))
