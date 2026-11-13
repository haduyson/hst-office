# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-windows-document-window-modes.py: the taskbar identity of a window, profile seeding and
configuration changes over UNO."""
import ctypes
import os
from ctypes import wintypes

MISC = "/org.openoffice.Office.Common/Misc"


class _Key(ctypes.Structure):
    _fields_ = [("fmtid", ctypes.c_byte * 16), ("pid", wintypes.DWORD)]


def aumid(hwnd):
    """System.AppUserModel.ID of a window (its taskbar group), "" when it has none."""
    import uuid
    store = ctypes.c_void_p()
    iid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99").bytes_le)
    if ctypes.windll.shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), iid, ctypes.byref(store)) or not store:
        return ""
    key = _Key((ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3").bytes_le), 5)
    variant = (ctypes.c_byte * 24)()
    vtable = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(vtable[5])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
    value = ""
    if get_value(store, ctypes.byref(key), variant) == 0 and int.from_bytes(bytes(variant[:2]), "little") == 31:
        value = ctypes.wstring_at(ctypes.c_void_p.from_buffer(variant, 8).value)
    release(store)
    return value


def seed(profile, items):
    path = os.path.join(profile, "user", "registrymodifications.xcu")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    xml = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % i
                  for i in items)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace("</oor:items>", xml + "</oor:items>"))


def set_config(office, name, value):
    import uno
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", MISC
    access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
    access.setPropertyValue(name, value)
    access.commitChanges()
