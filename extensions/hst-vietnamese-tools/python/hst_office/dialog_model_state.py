# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""What a dialog's control models hold (text, selection, check state, enabled, labels), kept across a re-run hook.

A dialog moved onto another window (macOS native full screen, dialogs.Dialog._move_to) gets new controls on the same
model, so what the user entered is already there. Its on_ready hook must run again to hook the new controls, but most
on_ready hooks also fill the form (the citation entry dialog puts the edited item back into every field): the user's
typing was replaced by the old values. snapshot() before the hook and restore() after it put back every property the
hook changed, so only the hook's listeners and side effects stay.
"""
import uno

READONLY = 16  # com.sun.star.beans.PropertyAttribute.READONLY
FIRST = ("StringItemList",)  # a list box's items before its selection: setting the items clears the selection


def _order(name):
    return (0 if name in FIRST else 1, name)


def snapshot(model):
    """{control name: [(property name, type name, value)]} of every writable property of the dialog's controls."""
    saved = {}
    try:
        names = model.getElementNames()
    except Exception:  # noqa: BLE001 - not a control container: nothing to keep
        return saved
    for name in names:
        try:
            control = model.getByName(name)
            props = sorted(control.getPropertySetInfo().getProperties(), key=lambda prop: _order(prop.Name))
        except Exception:  # noqa: BLE001 - a control without property info: nothing to keep
            continue
        rows = []
        for prop in props:
            if prop.Attributes & READONLY:
                continue
            try:
                rows.append((prop.Name, prop.Type.typeName, control.getPropertyValue(prop.Name)))
            except Exception:  # noqa: BLE001 - unreadable property: leave it to the hook
                continue
        saved[name] = rows
    return saved


def _set(control, name, type_name, value):
    try:
        uno.invoke(control, "setPropertyValue", (name, uno.Any(type_name, value)))  # typed: []short, []string, ...
    except Exception:  # noqa: BLE001 - e.g. a void value: let the bridge convert it
        control.setPropertyValue(name, value)


def restore(model, saved):
    """Put back the properties whose value the hook changed; returns how many were put back."""
    restored = 0
    for name, rows in saved.items():
        try:
            control = model.getByName(name)
        except Exception:  # noqa: BLE001 - the hook removed the control
            continue
        for prop, type_name, value in rows:
            try:
                if control.getPropertyValue(prop) == value:
                    continue
                _set(control, prop, type_name, value)
                restored += 1
            except Exception:  # noqa: BLE001 - one property that cannot be set must not stop the others
                continue
    return restored
