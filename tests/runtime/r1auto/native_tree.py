# SPDX-License-Identifier: AGPL-3.0-only
"""The office's OS accessibility tree (tooling Python): role, name and screen bounds of each node.

The engine's toolkit peers expose no XAccessible over UNO (census of r1-auto Windows run 42746971607: the top
window advertises 18 interfaces, none accessible; queryInterface(XAccessible) is None), so the ribbon is read from
the OS: AX on macOS, UI Automation on Windows (which also starts LibreOffice's MSAA bridge)."""
import platform


def mac_nodes(limit):
    import ApplicationServices as ax
    from mac_access import applications, attribute, nodes
    out = []
    for app in applications():
        for node in nodes(app, budget=30.0):
            position, size = attribute(node, "AXPosition"), attribute(node, "AXSize")
            box = None
            if position is not None and size is not None:
                _, point = ax.AXValueGetValue(position, ax.kAXValueCGPointType, None)
                _, extent = ax.AXValueGetValue(size, ax.kAXValueCGSizeType, None)
                box = [round(point.x), round(point.y), round(extent.width), round(extent.height)]
            name = next((str(v) for k in ("AXTitle", "AXDescription", "AXValue")
                         if isinstance(v := attribute(node, k), str) and v), "")
            out.append([str(attribute(node, "AXRole") or ""), name[:80], box])
            if len(out) >= limit:
                return out
    return out


def windows_nodes(limit):
    """UI Automation from the office's own HWNDs: the UIA desktop root listed no soffice.bin window although
    EnumWindows finds them (r1-auto Windows run 42751960237, W8 tree)."""
    from pywinauto.uia_element_info import UIAElementInfo
    from windows_focus import office_windows
    out = []
    for hwnd, _title in office_windows():
        root = UIAElementInfo(handle=hwnd)
        for info in [root] + root.descendants():
            r = info.rectangle
            out.append([info.control_type or "", (info.name or "")[:80], [r.left, r.top, r.width(), r.height()]])
            if len(out) >= limit:
                return out
    return out or [["no soffice.bin window", [t for _, t in office_windows()], None]]


def tree(limit="4000"):
    if limit == "diagnose":
        from os_a11y_diagnose import diagnose
        return diagnose()
    limit = int(limit)
    return mac_nodes(limit) if platform.system() == "Darwin" else windows_nodes(limit)
