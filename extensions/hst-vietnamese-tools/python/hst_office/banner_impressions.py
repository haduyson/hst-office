# SPDX-License-Identifier: AGPL-3.0-only
"""Local banner display counts: per local day and banner id, in the profile banner cache (docs/BANNERS.md).

The native widget reports a card once it stood one second in a visible window (one count per card change).
Counts are kept in memory and merged into impressions.json at most every 60 seconds and when the office
terminates, never on the UI thread except for that final write. The file holds at most 7 days, 24 ids per
day and 5000 per id and day; it is written atomically under a kernel lock shared by every office process.
Nothing here identifies the machine: only day, banner id and a number.
"""
import datetime
import json
from pathlib import Path
import re
import threading
import time

from . import banner_cache as cache
from .banner_store import publication_lock

FILE = "impressions.json"
LOCK = "impressions.lock"
MAX_DAYS = 7
MAX_IDS = 24
MAX_COUNT = 5000
FLUSH_SECONDS = 60
LIMIT = 65536  # bounded read; a full file is about 13 KiB
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def valid_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def local_day(timestamp):
    """The machine's local calendar day of a POSIX timestamp."""
    return datetime.date.fromtimestamp(timestamp)


def parse_day(text):
    if not isinstance(text, str) or not _DAY.fullmatch(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def merge(days, deltas):
    """days plus deltas ({day: {id: n}}), with the per-day id limit and the per-id cap. Returns days."""
    for day, counts in deltas.items():
        target = days.setdefault(day, {})
        for banner_id, count in counts.items():
            if banner_id in target or len(target) < MAX_IDS:
                target[banner_id] = min(target.get(banner_id, 0) + count, MAX_COUNT)
        if not target:
            del days[day]
    return days


def prune(days, today):
    """Only well-formed entries of the newest 7 days between today-6 and today+1 (a clock set back leaves
    no far-future day behind, which the server would reject)."""
    out = {}
    if not isinstance(days, dict):
        return out
    low, high = today - datetime.timedelta(days=6), today + datetime.timedelta(days=1)
    for day, counts in days.items():
        date = parse_day(day)
        if date is None or not low <= date <= high or not isinstance(counts, dict):
            continue
        kept = {}
        for banner_id, count in counts.items():
            if valid_id(banner_id) and type(count) is int and count >= 1 and len(kept) < MAX_IDS:
                kept[banner_id] = min(count, MAX_COUNT)
        if kept:
            out[day] = kept
    return {day: out[day] for day in sorted(out)[-MAX_DAYS:]}


def load(root, today):
    """Stored counts; a missing or corrupt file counts as empty (it is replaced at the next write)."""
    try:
        doc = json.loads(cache.read_bounded(Path(root) / FILE, LIMIT))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("schemaVersion") != 1:
        return {}
    return prune(doc.get("days"), today)


def save(root, days):
    data = json.dumps({"schemaVersion": 1, "days": days}, sort_keys=True, separators=(",", ":"))
    cache.atomic_write(Path(root) / FILE, data.encode("ascii"))


def file_lock(root):
    return publication_lock(Path(root), LOCK)


class Counter:
    """In-memory deltas of this process, merged into the shared file by flush()."""

    def __init__(self, root, clock=time.time, monotonic=time.monotonic):
        self.root, self.clock, self.monotonic = Path(root), clock, monotonic
        self._pending, self._lock = {}, threading.Lock()
        self._last_flush = monotonic()

    def today(self):
        return local_day(self.clock())

    def record(self, banner_id):
        """Count one display of banner_id today; flushes when the last write is 60 seconds old. Never raises."""
        if not valid_id(banner_id):
            return False
        try:
            day = self.today().isoformat()
            with self._lock:
                merge(self._pending, {day: {banner_id: 1}})
                due = self.monotonic() - self._last_flush >= FLUSH_SECONDS
            if due:
                self.flush()
            return True
        except Exception:  # noqa: BLE001 - a counter must never disturb the banner or the office
            print("HST banners: display count unavailable", flush=True)
            return False

    def flush(self):
        """Merge pending deltas into impressions.json. On failure they stay pending for the next flush."""
        with self._lock:
            pending, self._pending = self._pending, {}
            self._last_flush = self.monotonic()
        if not pending:
            return True
        try:
            today = self.today()
            with file_lock(self.root):
                save(self.root, prune(merge(load(self.root, today), pending), today))
            return True
        except Exception:  # noqa: BLE001 - read-only/unavailable profile: keep the counts in memory
            with self._lock:
                self._pending = merge(pending, self._pending)
            print("HST banners: display counts not saved", flush=True)
            return False
