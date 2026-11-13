# SPDX-License-Identifier: AGPL-3.0-only
"""What the session heartbeat left in the marker of a session that did not close, as crash-report lines (pure).

session_heartbeat stores in the marker the last time the office answered ("beat") and the app keys of the open
documents, the active one and how many were modified or still loading; diag_crash.previous_session passes them on
with the hang event Windows recorded, if any. Lines carry app names and counts only, never document names.
"""
import time


def _clock(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def _app_name(key):
    """Product name of an app key where the release has the table (error_report_apps), else the key itself."""
    try:
        from .error_report_apps import app_name
    except ImportError:
        return key
    return app_name(key)


def beat_facts(previous):
    """Lines about the last heartbeat (pure): when the office last answered, what was open; no names."""
    beat = previous.get("beat")
    if not beat:
        return ["Last heartbeat: none recorded (version without heartbeat, or ended within seconds of the start)"]
    started = previous.get("started") or beat
    lines = ["Last heartbeat: %s (%d s after the start)" % (_clock(beat), max(0, beat - started))]
    hang = previous.get("hang")
    if hang and hang.get("time"):
        lines.append("Not responding for at least %d s before it was closed (%s)" % (
            max(0, hang["time"] - beat), _clock(hang["time"])))
    apps = previous.get("apps") or []
    counts = ", ".join("%s %d" % (_app_name(key), apps.count(key)) for key in sorted(set(apps)))
    lines.append("Documents open at the last heartbeat: %d%s; modified: %d; still loading: %d" % (
        len(apps), (" (%s)" % counts) if counts else "", previous.get("modified", 0), previous.get("loading", 0)))
    if previous.get("active"):
        lines.append("Active app: %s" % _app_name(previous["active"]))
    return lines


def last_app(previous):
    """App key of the previous session's active document, else of its documents when they share one app; else ""."""
    if not previous:
        return ""
    active = previous.get("active") or ""
    if active and active not in ("start", "unknown"):
        return active
    apps = set(previous.get("apps") or [])
    return apps.pop() if len(apps) == 1 else ""
