# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Time windows of build slots: a slot with a "window" in config.json takes new jobs only while it is open, and a job
still running on it when the window closes is stopped and requeued (dispatch_windows.WindowsRunner.enforce_windows).

    "window": {"open": "18:00", "close": "07:30", "all_day": ["sun"], "idle_by": "08:00", "utc_offset_minutes": 420}

  open/close   local HH:MM; open > close is an overnight window (18:00 -> 07:30 the next morning)
  all_day      weekdays open for the whole day (mon..sun); "sun" joins Saturday 18:00 to Monday 07:30
  idle_by      local HH:MM by which the host must be idle again after a close (a warning when it is not)
  utc_offset_minutes  the local time zone as a fixed offset: Asia/Saigon is UTC+7 all year (no daylight saving),
               so the dispatcher needs no time zone database
"""
from datetime import datetime, timedelta, timezone

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SAIGON_OFFSET_MINUTES = 7 * 60


class WindowError(ValueError):
    pass


def _minutes(text, field):
    try:
        hh, mm = str(text).split(":")
        value = int(hh) * 60 + int(mm)
    except ValueError:
        raise WindowError(f"window {field} must be HH:MM, not {text!r}") from None
    if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
        raise WindowError(f"window {field} must be HH:MM, not {text!r}")
    return value


def parse(window):
    """Validated (open, close, all_day set, idle_by or None, offset) in minutes; WindowError when malformed."""
    if not isinstance(window, dict):
        raise WindowError(f"window must be an object, not {window!r}")
    unknown = set(window) - {"open", "close", "all_day", "idle_by", "utc_offset_minutes"}
    if unknown:
        raise WindowError(f"unknown window keys: {', '.join(sorted(unknown))}")
    opens, closes = _minutes(window.get("open"), "open"), _minutes(window.get("close"), "close")
    if opens == closes:
        raise WindowError("window open and close are equal; leave the window out for a slot that is always open")
    days = window.get("all_day", [])
    if not isinstance(days, list) or any(d not in DAYS for d in days):
        raise WindowError(f"window all_day must be a list of {', '.join(DAYS)}")
    idle = _minutes(window["idle_by"], "idle_by") if window.get("idle_by") is not None else None
    offset = window.get("utc_offset_minutes", SAIGON_OFFSET_MINUTES)
    if not isinstance(offset, int) or abs(offset) > 14 * 60:
        raise WindowError(f"window utc_offset_minutes must be an integer within +-840, not {offset!r}")
    return opens, closes, set(days), idle, offset


def local_time(window, now):
    return datetime.fromtimestamp(now, timezone(timedelta(minutes=parse(window)[4])))


def is_open(window, now):
    """True while the slot may start a job. No window: always open."""
    if not window:
        return True
    opens, closes, days, _idle, _offset = parse(window)
    t = local_time(window, now)
    if DAYS[t.weekday()] in days:
        return True
    m = t.hour * 60 + t.minute
    if opens < closes:
        return opens <= m < closes
    return m >= opens or m < closes


def overdue(window, now):
    """True when the window is closed and the local time has passed idle_by (the host should be idle by now)."""
    if not window or is_open(window, now):
        return False
    _opens, closes, _days, idle, _offset = parse(window)
    if idle is None:
        return False
    t = local_time(window, now)
    since_close = (t.hour * 60 + t.minute - closes) % 1440
    return since_close >= (idle - closes) % 1440


def describe(window):
    if not window:
        return "always"
    opens, closes, days, idle, offset = parse(window)
    fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}"   # noqa: E731 - a local formatter
    text = f"{fmt(opens)}-{fmt(closes)}"
    if days:
        text += f", all day {','.join(d for d in DAYS if d in days)}"
    if idle is not None:
        text += f", idle by {fmt(idle)}"
    return f"{text} (UTC{offset // 60:+d})"
