# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: is MathType installed, i.e. can this Windows machine open an equation's OLE server?

The double-click question offers "Mở bằng MathType" only then (owner decision 18/11/2026). An OLE server is installed
when HKEY_CLASSES_ROOT\\CLSID\\{class id} names a LocalServer32 or InprocServer32 program that exists; a TreatAs
entry (MathType can take over Equation Editor 3.x objects this way) is followed. Never true outside Windows."""
import os
import re
import sys

SERVER_KEYS = ("LocalServer32", "InprocServer32")


def _windows_reader():
    """read(path) -> default value of HKEY_CLASSES_ROOT\\path in the 64-bit or else the 32-bit registry view, or None.

    The office is a 64-bit process, so a plain OpenKey only sees the 64-bit view of HKCR\\CLSID. A 32-bit OLE server
    (MathType in "C:\\Program Files (x86)\\MathType") registers its class in the 32-bit view (WOW6432Node), which COM
    still starts for a 64-bit client: without the second view MathType counted as not installed."""
    import winreg
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)

    def read(path):
        for view in views:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path, 0, winreg.KEY_READ | view) as key:
                    return winreg.QueryValue(key, None)
            except OSError:
                continue
        return None
    return read


def program_path(command):
    """The program of a registry command line: quoted, or everything up to .exe/.dll, else the first word."""
    command = os.path.expandvars((command or "").strip())
    quoted = re.match(r'"([^"]+)"', command)
    if quoted:
        return quoted.group(1)
    found = re.match(r"(.+?\.(?:exe|dll))\b", command, re.IGNORECASE)
    return found.group(1) if found else command.split(" ")[0]


def server_installed(class_id, read=None, exists=os.path.exists, platform=sys.platform):
    """True when the OLE server of class_id ("0002CE03-0000-...") is installed on this Windows machine."""
    if platform != "win32" or not class_id:
        return False
    if read is None:
        read = _windows_reader()
    for _ in range(2):  # the class itself, then what it is treated as
        for key in SERVER_KEYS:
            command = read(r"CLSID\{%s}\%s" % (class_id, key))
            if command and exists(program_path(command)):
                return True
        class_id = (read(r"CLSID\{%s}\TreatAs" % class_id) or "").strip("{} ")
        if not class_id:
            return False
    return False


CONVERT, OPEN, LEAVE = "convert", "open", "leave"  # answers of the double-click question


def choices(class_id, installed=server_installed):
    """The answers offered for one equation: "Mở bằng MathType" only where MathType can open it."""
    return (CONVERT, OPEN, LEAVE) if installed(class_id) else (CONVERT, LEAVE)
