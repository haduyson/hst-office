# SPDX-License-Identifier: AGPL-3.0-only
"""Where a banner click goes: the click counter while it answers, else the company home page.

The probe is sent only on a user click, carries no identifiers and is a HEAD of the manifest, because a
request to /go/<id> would count a click. Never call this on the UI thread: it can wait 1.5 seconds.
"""
from urllib.parse import urlsplit

from .banner_fetch import head_status
from .banner_urls import FEED_URL, click_url

COUNTER_HOST = "system.hasontech.vn"
HOME = "https://hasontech.vn"
PROBE = head_status


def destination(url, utm, version, proxy=None):
    """url when its host answers below 500 or is not the counter; failures of any kind go to HOME."""
    if urlsplit(url).hostname != COUNTER_HOST:
        return url
    try:
        if PROBE(FEED_URL, version, proxy) < 500:
            return url
    except Exception:  # noqa: BLE001 - DNS, TLS, timeout: the user still lands somewhere useful, with no dialog
        pass
    return click_url(HOME, utm)
