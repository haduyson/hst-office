# SPDX-License-Identifier: AGPL-3.0-only
"""Setting "Lưu phiên bản trước khi ghi đè tệp" (Tùy chọn ▸ HST Office ▸ Phiên bản trước) and its administrator lock.

The value lives in the extension schema /org.hasontech.hstoffice.PreviousVersions/Enabled (previousversions.xcs,
default true). Administrators lock it for the whole machine (docs/PREVIOUS_VERSIONS.md):
- Windows: HST Office's own policy key, HKLM (or HKCU) SOFTWARE\\Policies\\HASON TECH\\HST Office\\
  org.hasontech.hstoffice.PreviousVersions\\Enabled with "Value" = "true"/"false" and DWORD "Final" = 1, the format of
  the update locks. The core reads HKLM before the bundled extension's schema exists, so it would drop that value;
  this module reads the key itself (HKLM over HKCU).
- macOS: the dictionary "PreviousVersions" of the vn.hasontech.hstoffice managed preferences (update_config).
- Any OS: a value finalized in the configuration (a shared policy extension, or the HKCU policy layer of the core).
Precedence: Windows policy > macOS profile > finalized configuration > the user's value (default true).
"""
import sys

from . import diag_log

PATH = "/org.hasontech.hstoffice.PreviousVersions"
KEY = "Enabled"
MACOS_SECTION = "PreviousVersions"
STORE_FOLDER = "hst-versions"  # in the user profile's user/ folder, next to hst-office (diag_log)
POLICY_KEY = "SOFTWARE\\Policies\\HASON TECH\\HST Office\\org.hasontech.hstoffice.PreviousVersions\\Enabled"


def parse_bool(value):
    """An administrator value as bool, or None when it is not a recognisable boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value or "").strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return None


def windows_policy(winreg=None):
    """Locked value from the Windows policy key (HKLM first, then HKCU), or None."""
    if winreg is None:
        if sys.platform != "win32":
            return None
        import winreg
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, POLICY_KEY) as key:
                final, _ = winreg.QueryValueEx(key, "Final")
                value, _ = winreg.QueryValueEx(key, "Value")
        except OSError:
            continue
        if final == 1 and parse_bool(value) is not None:
            return parse_bool(value)
    return None


def macos_policy(user=None, base=None):
    """Locked value from the macOS configuration profile, or None."""
    from . import managed_preferences
    if base is None and sys.platform != "darwin":
        return None
    section = managed_preferences.section(MACOS_SECTION, user, base or managed_preferences.MANAGED_DIR)
    return parse_bool(section.get(KEY)) if KEY in section else None


def resolve(configured, windows, macos):
    """Pure: (enabled, locked). configured: (value, finalized) from the configuration or None; windows/macos: a locked
    bool or None."""
    for forced in (windows, macos):
        if forced is not None:
            return forced, True
    if configured is not None:
        value = parse_bool(configured[0])
        return (True if value is None else value), bool(configured[1])
    return True, False


def load(ctx):
    """(enabled, locked) of the running office."""
    from .update_config import _read
    try:
        configured = (_read(ctx, PATH, (KEY,)) or {}).get(KEY)
    except Exception:  # noqa: BLE001 - no schema (an older package): the default applies
        diag_log.exception("version_config")
        configured = None
    try:
        windows = windows_policy()
    except Exception:  # noqa: BLE001 - an unreadable policy key must not disable saving
        diag_log.exception("version_config")
        windows = None
    return resolve(configured, windows, macos_policy())


def enabled(ctx):
    return load(ctx)[0]


def document_path(model):
    """System path of the document's file, or None (not stored yet, embedded object, or not a file: URL)."""
    try:
        url = model.getLocation() if model is not None and model.hasLocation() else ""
    except Exception:  # noqa: BLE001 - not an XStorable (e.g. a component without a location)
        return None
    if not url.startswith("file:"):
        return None
    import uno
    return uno.fileUrlToSystemPath(url)


def store(ctx):
    """The VersionStore of this user profile: <profile>/user/hst-versions."""
    import os
    import uno
    from .version_store import VersionStore
    subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    return VersionStore(os.path.join(uno.fileUrlToSystemPath(subst.substituteVariables("$(user)", True)), STORE_FOLDER))


def save(ctx, value):
    """Write the user's value; False when it is locked or the write failed."""
    from .update_config import _node
    try:
        if load(ctx)[1]:
            return False
        node = _node(ctx, PATH, True)
        node.setPropertyValue(KEY, bool(value))
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001 - a failing config write must never disturb the office
        diag_log.exception("version_config")
        return False
