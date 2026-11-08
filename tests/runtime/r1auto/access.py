# SPDX-License-Identifier: AGPL-3.0-only
"""UNO accessibility observations shared across native desktops."""
from support import native


def context(node):
    return node.getAccessibleContext() if hasattr(node, "getAccessibleContext") else node


def walk(node, depth=0):
    if depth > 24:
        return
    ctx = context(node)
    if ctx is None or not hasattr(ctx, "getAccessibleStateSet"):
        return  # a macOS top window can expose no accessible context (r1-auto macOS run 42471573001, M4)
    yield ctx
    for index in range(min(ctx.getAccessibleChildCount(), 2500)):
        try:
            yield from walk(ctx.getAccessibleChild(index), depth + 1)
        except Exception:
            continue  # disposed child during repaint; missing observations fail the caller


def visible(node):
    from com.sun.star.accessibility.AccessibleStateType import SHOWING
    states = node.getAccessibleStateSet()
    return bool(states & SHOWING) if isinstance(states, int) else states.contains(SHOWING)


def box(node):
    window = node
    node = context(node)
    if not hasattr(node, "getLocationOnScreen") and hasattr(window, "getPosSize"):
        rect = window.getPosSize()  # a frame's container window on Windows has no accessible component
        return rect.X, rect.Y, rect.Width, rect.Height
    if not hasattr(node, "getLocationOnScreen"):
        return -100000, -100000, 0, 0  # no XAccessibleComponent: never inside any measured region
    point, size = node.getLocationOnScreen(), node.getSize()
    return point.X, point.Y, size.Width, size.Height


def center(node):
    x, y, width, height = box(node)
    return x + width // 2, y + height // 2


def click(node):
    native("click", *center(node))


def snapshot(office):
    toolkit = office.service("com.sun.star.awt.Toolkit")
    return [node for i in range(toolkit.getTopWindowCount())
            for node in walk(toolkit.getTopWindow(i)) if visible(node)]


def census(office):
    """Per top window: title, accessible role and child count (failure evidence for empty snapshots)."""
    toolkit = office.service("com.sun.star.awt.Toolkit")
    out = []
    for i in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(i)
        try:
            ctx = context(window)
            out.append((getattr(window, "Title", ""), ctx.getAccessibleRole(), ctx.getAccessibleChildCount()))
        except Exception as error:
            out.append((getattr(window, "Title", ""), type(error).__name__))
    return out


def named(office, text):
    return [node for node in snapshot(office) if text in node.getAccessibleName()]


def labels(office):
    return [node.getAccessibleName() for node in snapshot(office) if node.getAccessibleName()]
