# SPDX-License-Identifier: AGPL-3.0-only
"""Per-OS default-apps actions and the "already registered" test (no uno; command building is pure and tested).

make_default(system) -> (ok, kind): kind "" (done) or "settings" (Windows: Settings opened, the user picks there).
is_registered(system) -> bool: HST already opens the main office types, or the Windows installer recorded the choice.
"""
import os
import platform
import urllib.parse

from .default_apps_linux import linux_is_registered, linux_make_default

BUNDLE_ID = "vn.hasontech.hstoffice"  # build-config/macos-*.conf --with-macosx-bundle-identifier
# UTIs declared in the HST bundle's Info.plist (sysui/desktop/macosx/Info.plist.in) for the office types.
MAC_UTIS = ("org.oasis-open.opendocument.text", "org.oasis-open.opendocument.spreadsheet",
            "org.oasis-open.opendocument.presentation", "org.oasis-open.opendocument.text-template",
            "org.oasis-open.opendocument.spreadsheet-template", "org.oasis-open.opendocument.presentation-template",
            "com.microsoft.word.doc", "com.microsoft.excel.xls", "com.microsoft.powerpoint.ppt",
            "org.openxmlformats.wordprocessingml.document", "org.openxmlformats.wordprocessingml.template",
            "org.openxmlformats.spreadsheetml.sheet", "org.openxmlformats.spreadsheetml.template",
            "org.openxmlformats.presentationml.presentation", "org.openxmlformats.presentationml.template")
MAC_PROBE_UTIS = ("org.openxmlformats.wordprocessingml.document", "org.openxmlformats.spreadsheetml.sheet",
                  "org.openxmlformats.presentationml.presentation")
WIN_EXTENSIONS = (".docx", ".xlsx", ".pptx")
WIN_PROGID_PREFIX = "HSTOffice."
WIN_MARKER_KEY = r"SOFTWARE\HASON TECH\HST Office\DefaultApps"  # written by the MSI when its checkbox is ticked
WIN_MARKER_VALUE = "ChosenAtInstall"
WIN_SETTINGS = "ms-settings:defaultapps"


def system():
    return platform.system()


# ---- macOS -------------------------------------------------------------------------------------------------------
NOT_IN_APPLICATIONS = "Hãy chuyển HST Office vào thư mục Ứng dụng (Applications) rồi thử lại."


def mac_bundle_of(path):
    """The outermost ".app" bundle that contains `path`, or None (pure)."""
    parts = os.path.normpath(path).split(os.sep)
    for index, part in enumerate(parts):
        if part.endswith(".app"):
            return os.sep.join(parts[:index + 1]) or None
    return None


def mac_in_applications(path=__file__):
    """True when this copy runs from /Applications. A .dmg, Downloads or a translocated copy
    (/private/var/folders/.../AppTranslocation/...) must not become the default app (pure apart from __file__)."""
    bundle = mac_bundle_of(path)
    return bool(bundle) and os.path.dirname(bundle) == "/Applications"


def _launch_services():
    import ctypes
    import ctypes.util
    cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    ls = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreServices"))
    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32)
    cf.CFStringGetCString.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32)
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    ls.LSSetDefaultRoleHandlerForContentType.restype = ctypes.c_int32
    ls.LSSetDefaultRoleHandlerForContentType.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p)
    ls.LSCopyDefaultRoleHandlerForContentType.restype = ctypes.c_void_p
    ls.LSCopyDefaultRoleHandlerForContentType.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    return ctypes, cf, ls


_UTF8, _ROLES_ALL = 0x08000100, 0xFFFFFFFF  # kCFStringEncodingUTF8, kLSRolesAll


def mac_make_default():
    if not mac_in_applications():
        raise RuntimeError(NOT_IN_APPLICATIONS)
    ctypes, cf, ls = _launch_services()
    bundle = cf.CFStringCreateWithCString(None, BUNDLE_ID.encode(), _UTF8)
    failed = []
    try:
        for uti in MAC_UTIS:
            ref = cf.CFStringCreateWithCString(None, uti.encode(), _UTF8)
            try:
                status = ls.LSSetDefaultRoleHandlerForContentType(ref, _ROLES_ALL, bundle)
            finally:
                cf.CFRelease(ref)
            if status != 0:
                failed.append("%s (%d)" % (uti, status))
    finally:
        cf.CFRelease(bundle)
    if len(failed) == len(MAC_UTIS):
        raise RuntimeError("LaunchServices: " + ", ".join(failed))
    return True, ""


def mac_is_registered():
    ctypes, cf, ls = _launch_services()
    for uti in MAC_PROBE_UTIS:
        ref = cf.CFStringCreateWithCString(None, uti.encode(), _UTF8)
        try:
            handler = ls.LSCopyDefaultRoleHandlerForContentType(ref, _ROLES_ALL)
        finally:
            cf.CFRelease(ref)
        if not handler:
            return False
        buffer = ctypes.create_string_buffer(256)
        cf.CFStringGetCString(handler, buffer, 256, _UTF8)
        cf.CFRelease(handler)
        if buffer.value.decode("utf-8", "replace").lower() != BUNDLE_ID:
            return False
    return True


# ---- Windows -----------------------------------------------------------------------------------------------------
def windows_settings_uri(registered_names):
    """Settings deep link for HST's registered application name, else the general default-apps page (pure)."""
    name = next((n for n in registered_names if n.startswith("HST Office")), None)
    if name is None:
        return WIN_SETTINGS
    return WIN_SETTINGS + "?registeredAppMachine=" + urllib.parse.quote(name)


def _registered_application_names():
    import winreg
    names = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r"Software\RegisteredApplications") as key:
                index = 0
                while True:
                    try:
                        names.append(winreg.EnumValue(key, index)[0])
                    except OSError:
                        break
                    index += 1
        except OSError:
            continue
    return names


def windows_make_default():
    uri = windows_settings_uri(_registered_application_names())
    try:
        os.startfile(uri)  # noqa: S606 - a fixed ms-settings URI, no user input
    except OSError:
        os.startfile(WIN_SETTINGS)  # noqa: S606 - older builds do not know the deep link
    return True, "settings"


def windows_is_registered():
    import winreg
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, WIN_MARKER_KEY) as key:
                if int(winreg.QueryValueEx(key, WIN_MARKER_VALUE)[0]) == 1:
                    return True
        except (OSError, ValueError):
            continue
    base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\%s\UserChoice"
    for extension in WIN_EXTENSIONS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base % extension) as key:
                if not str(winreg.QueryValueEx(key, "ProgId")[0]).startswith(WIN_PROGID_PREFIX):
                    return False
        except OSError:
            return False
    return True


_ACTIONS = {"Linux": (linux_make_default, linux_is_registered), "Darwin": (mac_make_default, mac_is_registered),
            "Windows": (windows_make_default, windows_is_registered)}


def make_default(name):
    if name not in _ACTIONS:
        raise RuntimeError("hệ điều hành chưa được hỗ trợ")
    return _ACTIONS[name][0]()


def is_registered(name):
    return _ACTIONS[name][1]() if name in _ACTIONS else False
