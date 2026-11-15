# SPDX-License-Identifier: AGPL-3.0-only
"""Windows collector for ribbon_mockup_geometry: the showing nodes of the ribbon band through the UNO accessibility
tree of the office's windows (run with the office's python.exe, so `import uno` works).
"""
import windows_gui_a11y as a11y

# AccessibleRole constant name -> the role names of ribbon_mockup_geometry (the AT-SPI names)
ROLE_NAMES = {"LABEL": "label", "PUSH_BUTTON": "push button", "TOGGLE_BUTTON": "toggle button",
              "BUTTON_DROPDOWN": "push button menu", "BUTTON_MENU": "menu button", "PAGE_TAB": "page tab",
              "LINK": "link", "PANEL": "panel", "DOCUMENT_TEXT": "document text", "TABLE": "table",
              "RULER": "ruler", "STATUS_BAR": "status bar", "MENU_BAR": "menu bar"}
SKIP_ROLES = ("document text", "table", "ruler", "status bar", "menu bar")
BAND_BOTTOM = 230
MAX_DEPTH = 20


def _role_of(value):
    import uno
    for name, text in ROLE_NAMES.items():
        if uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name) == value:
            return text
    return "other"


def _box(context):
    try:
        if a11y.showing(context):
            where, size = context.getLocationOnScreen(), context.getSize()
            return (where.X, where.Y, size.Width, size.Height)
    except Exception:  # noqa: BLE001 - widgets come and go
        pass
    return None


def _collect(accessible, ancestors, out, depth=0):
    if accessible is None or depth > MAX_DEPTH:
        return
    try:
        context = accessible.getAccessibleContext()
        if context is None:
            return
        role = _role_of(context.getAccessibleRole())
        if role in SKIP_ROLES:
            return
        name = context.getAccessibleName() or ""
        box = _box(context)
        if box is not None and box[1] < BAND_BOTTOM:
            out.append((role, name, box, list(ancestors)))
        children = [context.getAccessibleChild(i) for i in range(min(context.getAccessibleChildCount(), 400))]
    except Exception:  # noqa: BLE001
        return
    for child in children:
        _collect(child, ancestors + [box], out, depth + 1)


def ribbon_nodes(windows):
    """Showing ribbon nodes of the given top windows, as (role, name, box, ancestor_boxes)."""
    out = []
    for window in windows:
        _collect(window, [], out)
    return out
