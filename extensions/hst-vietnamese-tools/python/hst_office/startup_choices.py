# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The user's answers to the start-up questions, kept in a small file of the user profile.

<profile>/user/hst-office/startup-choices.json, e.g.
    {"welcome_shown": true, "crash_never_ask": true,
     "default_apps": {"Asked": 1, "LastAsked": 1795010742, "Done": false, "Release": "1.0.3"}}

Why not only the configuration: until 1.0.2 the answers lived only in the bundled extension's own schemas
(welcome.xcs, errorreport.xcs, defaultapps.xcs). configmgr keeps a user value of a schema only if it knows the schema
when it reads registrymodifications.xcu at start (configmgr xcuparser.cxx handleItem skips an "unknown item"), and it
rewrites the file from what it read (writemodfile.cxx), so a skipped value is gone after the next settings write. The
bundled extension's schemas are known at start only through the profile's registration cache
(user/extensions/bundled/registry/.../configmgr.ini; bundled extensions are not deployed live, dp_configuration.cxx),
so a start without a complete cache (a removed or damaged user/extensions folder, a start ended while the extensions
were registered again after an update) erased the answers. Since hst-extension-settings-core.patch these schemas are
core (main.xcd) and that path is closed; the file still covers registrymodifications.xcu restored from an older copy
or reset after a power cut (hst-profile-durability.patch), and an office whose core lacks the schemas. The
configuration is still written too, so an older HST Office sharing the profile and an administrator's lock keep
working, and a value found only there is copied here (migration).

Reads and writes never raise: a read-only profile only loses the answer, as before. Writes are atomic (temporary
file, fsync, rename), so a power cut leaves the old or the new file, never a broken one.
"""
import json
import os
import threading

from . import diag_log
from .citation_store import atomic_write

FILE_NAME = "startup-choices.json"
MAX_BYTES = 64 * 1024
READONLY = 16  # com.sun.star.beans.PropertyAttribute.READONLY: an administrator finalized the value
_LOCK = threading.Lock()


def profile_dir(ctx):
    """<profile>/user/hst-office of the running office (the folder of diag_log's hst-office.log)."""
    import uno
    subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    return os.path.join(uno.fileUrlToSystemPath(subst.substituteVariables("$(user)", True)), "hst-office")


def read(folder):
    """The stored answers ({} when the file is missing, too large or not a JSON object)."""
    try:
        with open(os.path.join(folder, FILE_NAME), "rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        data = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_BYTES else None
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write(folder, **changes):
    """Merge `changes` into the stored answers. Returns True when the file was written."""
    with _LOCK:
        data = read(folder)
        if all(key in data and data[key] == value for key, value in changes.items()):
            return True
        data.update(changes)
        try:
            atomic_write(os.path.join(folder, FILE_NAME), json.dumps(data, sort_keys=True).encode("utf-8"))
            return True
        except OSError:
            diag_log.exception("startup_choices")
            return False


def merge_default_apps(configured, stored):
    """The state from the configuration and the copy in startup-choices.json (pure). The configuration value can be
    lost (see above) or newer (an older version sharing the profile): Done counts when either
    says so; the counts are those of the latest question (higher LastAsked). Ask stays the configuration's: an
    administrator locks it there."""
    if not isinstance(stored, dict):
        return dict(configured)
    merged = dict(configured)
    try:
        newer = int(stored.get("LastAsked", 0)) >= int(configured.get("LastAsked", 0))
    except (TypeError, ValueError):
        return merged
    if newer:
        for key in ("Asked", "LastAsked", "Release"):
            if key in stored:
                merged[key] = stored[key]
    merged["Done"] = bool(configured.get("Done")) or bool(stored.get("Done"))
    return merged


def default_apps_answered(state):
    """True when the state holds an answer worth keeping (pure)."""
    return bool(state.get("Done")) or int(state.get("Asked", 0)) > 0


def opt_out(ctx, key, node_of, name):
    """For a question the user can turn off ("Không hỏi lại"): False when `key` is stored, else the configured boolean
    `name` of node_of() (an update access). A false value an administrator did not finalize is copied into the file
    (migration); a missing schema reads as the default, true."""
    if get(ctx, key):
        return False
    try:
        node = node_of()
        enabled = bool(node.getPropertyValue(name))
        locked = bool(node.getPropertySetInfo().getPropertyByName(name).Attributes & READONLY)
    except Exception:  # noqa: BLE001 - schema missing: behave like the default
        return True
    if not enabled and not locked:
        put(ctx, key, True)
    return enabled


def get(ctx, key, default=None):
    """One stored answer of the running office's profile, or `default`."""
    try:
        return read(profile_dir(ctx)).get(key, default)
    except Exception:  # noqa: BLE001 - no profile folder: as if nothing was stored
        diag_log.exception("startup_choices")
        return default


def migrate(ctx):
    """Copy the answers a version without this file left in the configuration (at every start, before any question:
    a start that shows another question, or none, still keeps them). The readers copy what they find."""
    from . import default_apps, error_report_crash, welcome_job
    for read_answer in (welcome_job.is_shown, default_apps.load_state, error_report_crash.ask_enabled):
        try:
            read_answer(ctx)
        except Exception:  # noqa: BLE001 - one missing schema must not stop the others
            diag_log.exception("startup_choices")


def put(ctx, key, value):
    """Store one answer in the running office's profile; False when it could not be written."""
    try:
        return write(profile_dir(ctx), **{key: value})
    except Exception:  # noqa: BLE001 - a failing write must not break the start
        diag_log.exception("startup_choices")
        return False
