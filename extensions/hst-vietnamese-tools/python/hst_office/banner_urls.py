# SPDX-License-Identifier: AGPL-3.0-only
"""Banner URL policy and anonymous campaign links; no network access."""
from urllib.parse import urlencode, urlsplit, urlunsplit

FEED_URL = "https://system.hasontech.vn/hst-office/banners.json"
EXACT_HOSTS = ("echatbot.vn", "espace.vn", "aidelam.com")


def https_url(url):
    """Strict HTTPS URL, without credentials, controls, fragments or nonstandard ports."""
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        return False
    if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and bool(p.hostname) and p.username is None and p.password is None
                and p.port in (None, 443) and not p.fragment and p.hostname.isascii())
    except ValueError:
        return False


def allowed_url(url):
    if not https_url(url):
        return False
    host = urlsplit(url).hostname
    return host in EXACT_HOSTS or host == "hasontech.vn" or host.endswith(".hasontech.vn")


def feed_url(override=""):
    """Only the expert config supplies override; HTTPS testing origins may be outside the item allow-list."""
    return override if https_url(override) and not urlsplit(override).query else FEED_URL


def click_url(url, utm):
    """Replace the entire query with the three shared UTM parameters; never add user/app/document IDs."""
    if not allowed_url(url):
        raise ValueError("banner link refused")
    p = urlsplit(url)
    query = urlencode({"utm_source": utm["source"], "utm_medium": "banner", "utm_campaign": utm["campaign"]})
    return urlunsplit((p.scheme, p.netloc, p.path, query, ""))
