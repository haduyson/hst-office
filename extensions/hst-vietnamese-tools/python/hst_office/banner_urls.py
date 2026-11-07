# SPDX-License-Identifier: AGPL-3.0-only
"""Banner URL policy and anonymous campaign links; no network access."""
from urllib.parse import urlencode, urlsplit, urlunsplit

FEED_URL = "https://system.hasontech.vn/hst-office/banners.json"
EXACT_HOSTS = ("echatbot.vn", "espace.vn", "aidelam.com")
TEST_HOST = "127.0.0.1"
# Test-stamped packages only (release.json update_test_mode): local feed URL and signing key.
TEST_URL_ENV = "HST_BANNER_TEST_URL"
TEST_KEY_ENV = "HST_BANNER_TEST_KEY"


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


def test_url(url):
    """Plain HTTP to the local test server, without credentials, controls or fragments."""
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        return False
    if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        return False
    try:
        p = urlsplit(url)
        p.port  # raises ValueError for a malformed port
        return (p.scheme == "http" and p.hostname == TEST_HOST and p.username is None and p.password is None
                and not p.fragment)
    except ValueError:
        return False


def transport_url(url, allow_test=False):
    """What the fetch helper may request: strict HTTPS, or the local test server in test packages."""
    return https_url(url) or bool(allow_test and test_url(url))


def allowed_url(url):
    if not https_url(url):
        return False
    host = urlsplit(url).hostname
    return host in EXACT_HOSTS or host == "hasontech.vn" or host.endswith(".hasontech.vn")


def feed_url(override=""):
    """Only the expert config supplies override; HTTPS testing origins may be outside the item allow-list."""
    return override if https_url(override) and not urlsplit(override).query else FEED_URL


def click_url(url, utm, allow_test=False):
    """Replace the entire query with the three shared UTM parameters; never add user/app/document IDs.

    allow_test (test-stamped packages only) also accepts links to the local test server."""
    if not (allowed_url(url) or (allow_test is True and test_url(url))):
        raise ValueError("banner link refused")
    p = urlsplit(url)
    query = urlencode({"utm_source": utm["source"], "utm_medium": "banner", "utm_campaign": utm["campaign"]})
    return urlunsplit((p.scheme, p.netloc, p.path, query, ""))
