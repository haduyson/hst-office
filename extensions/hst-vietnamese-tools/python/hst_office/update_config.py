# SPDX-License-Identifier: AGPL-3.0-only
"""Settings of the update check: the core schema, the old extension schema and administrator locks.

The settings live in the core configuration /org.openoffice.Office.HSTUpdate (officecfg HSTUpdate.xcs, added by
patches/libreoffice/hst-update-config.patch), so an administrator can lock them with the usual LibreOffice layers:
a share/registry .xcd (Linux, macOS), HKLM\\SOFTWARE\\Policies\\LibreOffice\\org.openoffice.Office.HSTUpdate\\...
(Windows) or a shared extension. On macOS a configuration profile (managed preferences of vn.hasontech.hstoffice,
dictionary "HSTUpdate") is read as well. See docs/UPDATE_ADMIN.md.

Earlier releases kept the settings in the extension schema /org.hasontech.hstoffice.UpdateCheck (update.xcs):
- the per-user values there are copied once into the core schema (migrate);
- a value finalized there (old hst-update-policy.oxt) is still honoured as a lock.

Precedence of one setting: core finalized > macOS managed preference > legacy finalized > core (user or default).
"""
import os
import plistlib
import sys
import traceback

CORE_PATH = "/org.openoffice.Office.HSTUpdate"
LEGACY_PATH = "/org.hasontech.hstoffice.UpdateCheck"
MACOS_DOMAIN = "vn.hasontech.hstoffice"
MACOS_KEY = "HSTUpdate"
MANAGED_DIR = "/Library/Managed Preferences"

DEFAULTS = {"AutoCheck": True, "ManualCheck": True, "CheckIntervalHours": 24, "AllowInstall": True, "Channel": "",
            "LastCheck": 0, "SkippedVersion": ""}
ADMIN_KEYS = ("AutoCheck", "ManualCheck", "CheckIntervalHours", "AllowInstall", "Channel")
LEGACY_KEYS = ("AutoCheck", "AllowInstall", "LastCheck", "SkippedVersion")  # what update.xcs ever had
CHANNELS = ("", "stable", "beta")
READONLY = 16  # com.sun.star.beans.PropertyAttribute.READONLY: set on finalized properties of an update access


def _log(message):
    print("HST update config: %s" % message, flush=True)


def _node(ctx, path, writable=False):
    import uno  # imported lazily: the pure helpers below are unit-tested without an office
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def _read(ctx, path, names):
    """{name: (value, finalized)} of an update access, or None when the node does not exist."""
    try:
        node = _node(ctx, path, True)
    except Exception:  # noqa: BLE001 - schema missing (e.g. a core without HSTUpdate, or no legacy schema)
        return None
    info, out = node.getPropertySetInfo(), {}
    for name in names:
        if info.hasPropertyByName(name):
            out[name] = (node.getPropertyValue(name), bool(info.getPropertyByName(name).Attributes & READONLY))
    return out


def normalize(name, value):
    """Clamp an administrator-supplied value to what the update check understands."""
    if name in ("AutoCheck", "ManualCheck", "AllowInstall"):
        return bool(value)
    if name == "CheckIntervalHours":
        try:
            return min(max(int(value), 1), 8760)
        except (TypeError, ValueError):
            return DEFAULTS[name]
    if name == "Channel":
        value = str(value or "").strip().lower()
        return value if value in CHANNELS else ""
    if name == "LastCheck":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return "" if value is None else str(value)


def macos_managed(user=None, base=MANAGED_DIR):
    """Forced values of the macOS configuration profile: the "HSTUpdate" dictionary of the vn.hasontech.hstoffice
    managed preferences (per user first, then computer-wide). Everything under Managed Preferences is forced."""
    if not os.path.isdir(base):
        return {}
    if user is None:
        try:
            import pwd
            user = pwd.getpwuid(os.getuid()).pw_name
        except Exception:  # noqa: BLE001 - no user name: only the computer-wide profile
            user = None
    out = {}
    paths = [os.path.join(base, MACOS_DOMAIN + ".plist")]
    if user:
        paths.insert(0, os.path.join(base, user, MACOS_DOMAIN + ".plist"))
    for path in reversed(paths):  # computer-wide first, the per-user profile overrides it
        try:
            with open(path, "rb") as fh:
                doc = plistlib.load(fh)
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - a broken profile must not break the office
            _log("ignoring %s: %s" % (path, exc))
            continue
        section = doc.get(MACOS_KEY) if isinstance(doc, dict) else None
        if isinstance(section, dict):
            out.update({k: normalize(k, v) for k, v in section.items() if k in ADMIN_KEYS})
    return out


def resolve(core, legacy, managed):
    """Pure merge. core/legacy: {name: (value, finalized)} or None; managed: {name: value}.
    Returns (values, locked names)."""
    values, locked = dict(DEFAULTS), set()
    for name in DEFAULTS:
        c = (core or {}).get(name)
        lg = (legacy or {}).get(name)
        if c and c[1]:
            values[name], _ = c
            locked.add(name)
        elif name in managed:
            values[name] = managed[name]
            locked.add(name)
        elif lg and lg[1] and name in ADMIN_KEYS:
            values[name] = lg[0]
            locked.add(name)
        elif c:
            values[name] = c[0]
        elif lg:  # a core without the HSTUpdate schema: keep working on the old settings
            values[name] = lg[0]
        values[name] = normalize(name, values[name])
    return values, locked


def migration_plan(core, legacy):
    """Pure: the legacy per-user values to copy into the core schema ({name: value}).
    Only values that differ from the default, are not locked on either side and are not already set in the core."""
    plan = {}
    for name in LEGACY_KEYS:
        lg, c = (legacy or {}).get(name), (core or {}).get(name)
        if not lg or lg[1] or not c or c[1]:
            continue
        if lg[0] != DEFAULTS[name] and c[0] == DEFAULTS[name]:
            plan[name] = lg[0]
    return plan


def migrate(ctx):
    """Copy the old per-user values into the core schema once (flag LegacyMigrated). Safe to call at every start."""
    try:
        node = _node(ctx, CORE_PATH, True)
        if node.getPropertyValue("LegacyMigrated"):
            return {}
        core = _read(ctx, CORE_PATH, LEGACY_KEYS)
        plan = migration_plan(core, _read(ctx, LEGACY_PATH, LEGACY_KEYS))
        for name, value in plan.items():
            node.setPropertyValue(name, value)
        node.setPropertyValue("LegacyMigrated", True)
        node.commitChanges()
        if plan:
            _log("migrated %s from %s" % (", ".join(sorted(plan)), LEGACY_PATH))
        return plan
    except Exception:  # noqa: BLE001 - no core schema or a locked flag: nothing to migrate
        traceback.print_exc()
        return {}


def load(ctx):
    """(values, locked names) of every setting, after migration and with all administrator locks applied."""
    migrate(ctx)
    core = _read(ctx, CORE_PATH, DEFAULTS)
    legacy = _read(ctx, LEGACY_PATH, LEGACY_KEYS)
    return resolve(core, legacy, macos_managed() if sys.platform == "darwin" else {})


def settings(ctx):
    return load(ctx)[0]


def is_locked(ctx, name):
    return name in load(ctx)[1]


def save(ctx, name, value):
    """Write one per-user value into the core schema; False when it is locked or the write failed."""
    try:
        if is_locked(ctx, name):
            return False
        path = CORE_PATH if _read(ctx, CORE_PATH, (name,)) else LEGACY_PATH
        node = _node(ctx, path, True)
        node.setPropertyValue(name, value)
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001 - a failing config write must never disturb the office
        traceback.print_exc()
        return False
