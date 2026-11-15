# SPDX-License-Identifier: AGPL-3.0-only
"""Daily report of the local banner display counts (contract v1, docs/BANNERS.md "Display counting").

Sent by the feed worker within the same once-per-86,400-seconds attempt as the manifest, never on the UI thread,
through the private HTTPS helper with its five-second deadline. Always on and independent of SendInstallId: the
aggregate counts carry no machine ID. Not sent without a valid banner public key (bundled-only path), from test
packages or a FeedURL testing origin, or when there is nothing to send. The body holds only schemaVersion, the release and {day, counts}; no machine ID.
"""
import json

from . import banner_impressions as impressions
from .banner_fetch import post_status
from .banner_urls import IMPRESSIONS_URL
from .banner_verify import valid_key

MAX_BODY = 8192


def body(days, release):
    """(bytes, sent days) of the newest days that fit in 8 KiB, oldest dropped first; (None, {}) when empty."""
    names = sorted(days)
    while names:
        sent = {day: dict(sorted(days[day].items())) for day in names}
        doc = {"schemaVersion": 1, "release": release,
               "days": [{"day": day, "counts": sent[day]} for day in names]}
        data = json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if len(data) <= MAX_BODY:
            return data, sent
        names = names[1:]
    return None, {}


def may_send(key, production):
    """key: the banner public key (the empty placeholder is invalid); production: the production feed of a release
    package."""
    return production is True and valid_key(key)


def should_send(key, production, days):
    """may_send, and there are stored counts (days)."""
    return may_send(key, production) and bool(days)


def subtract(days, sent):
    """days minus what the server accepted; counts added while the request ran are kept."""
    out = {}
    for day, counts in days.items():
        left = {i: n - sent.get(day, {}).get(i, 0) for i, n in counts.items()}
        left = {i: n for i, n in left.items() if n > 0}
        if left:
            out[day] = left
    return out


def after_response(days, sent, status):
    """Stored counts after one attempt. status None: no answer (DNS, TLS, timeout, refused redirect).

    2xx (received) and 400 (refused schema, never accepted later): the sent counts are removed.
    413: the oldest sent day is dropped. Anything else (429, 5xx, no answer): kept for the next day."""
    if status is not None and (200 <= status < 300 or status == 400):
        return subtract(days, sent)
    if status == 413 and sent:
        oldest = min(sent)
        return {day: counts for day, counts in days.items() if day != oldest}
    return days


def report(counter, release, proxy, key, production, post=post_status):
    """One report attempt on the feed worker; returns the HTTP status, or None. Never raises."""
    try:
        if not may_send(key, production):
            return None  # nothing is read or written
        counter.flush()
        today = counter.today()
        with impressions.file_lock(counter.root):
            days = impressions.load(counter.root, today)
        if not days:
            return None
        data, sent = body(days, release)
        if data is None:
            return None
        try:
            status = post(IMPRESSIONS_URL, data, release, proxy)
        except Exception:  # noqa: BLE001 - no answer: keep the counts, never log URLs or details
            status = None
        with impressions.file_lock(counter.root):
            stored = impressions.load(counter.root, today)
            remaining = after_response(stored, sent, status)
            if remaining != stored:
                impressions.save(counter.root, remaining)
        return status
    except Exception:  # noqa: BLE001 - the feed refresh continues without the report
        print("HST banners: display report unavailable", flush=True)
        return None
