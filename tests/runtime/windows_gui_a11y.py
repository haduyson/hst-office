# SPDX-License-Identifier: AGPL-3.0-only
"""The accessibility tree of the office over UNO, for the Windows GUI checks (run with the office's python.exe)."""


def _state(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType." + name)


def _role(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)


def walk(accessible, depth=0, limit=14):
    """Yield (accessible context, depth) for the whole tree under `accessible` (depth-first)."""
    try:
        context = accessible.getAccessibleContext()
    except Exception:  # noqa: BLE001 - a disposed node
        return
    if context is None:
        return
    yield context, depth
    if depth >= limit:
        return
    try:
        count = min(context.getAccessibleChildCount(), 400)
    except Exception:  # noqa: BLE001
        return
    for index in range(count):
        try:
            child = context.getAccessibleChild(index)
        except Exception:  # noqa: BLE001
            continue
        if child is not None:
            yield from walk(child, depth + 1, limit)


def showing(context):
    try:
        return bool(context.getAccessibleStateSet() & _state("SHOWING"))
    except Exception:  # noqa: BLE001
        return False


def find_named(accessible, name, role=None):
    """First accessible context named `name` (and of `role`, an AccessibleRole name) under `accessible`."""
    wanted = _role(role) if role else None
    for context, _depth in walk(accessible):
        try:
            if context.getAccessibleName() == name and (wanted is None or context.getAccessibleRole() == wanted):
                return context
        except Exception:  # noqa: BLE001
            continue
    return None


def texts(accessible, limit=60):
    """Names of the showing labels, buttons and texts under `accessible` (evidence for a report)."""
    out = []
    for context, _depth in walk(accessible):
        try:
            name = context.getAccessibleName()
        except Exception:  # noqa: BLE001
            continue
        if name and showing(context) and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def press(context):
    """Run the default action (a button's click) of an accessible context."""
    context.doAccessibleAction(0)

