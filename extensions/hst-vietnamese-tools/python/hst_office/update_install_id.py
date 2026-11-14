# SPDX-License-Identifier: AGPL-3.0-only
"""Anonymous install ID sent with the update check, so HASON TECH can count the machines that use HST Office
(downloads do not: every update is a new download). docs/PRIVACY.md says what is sent and how to turn it off.

  * The ID is a random UUID4 (uuid.uuid4, from os.urandom), created at the first update check and stored in the user
    profile at /org.hasontech.hstoffice.UpdateCheck/InstallId (update.xcs). It is derived from nothing on the machine:
    not the hardware, the network (MAC) address, the user or machine name. A new or reset profile gets a new ID.
  * It travels as ?i=<id> on the manifest request of the update check (feed_url); the User-Agent already carries the
    release and the OS, so nothing else is added. An error report the user sends carries the same ID in its own
    "installId" field (for_report), so HASON TECH can group reports from the same machine; a report never creates one.
  * SendInstallId = false (Tùy chọn ▸ HST Office ▸ Cập nhật; administrators can lock it, update_config): no ID is sent,
    neither with the update check nor with an error report, and none is created. An ID created earlier stays in the
    profile, unused, so ticking the box again does not count the machine twice.
  * It is never logged: callers log errors without it (update_fetch), and the local log's filter replaces every UUID
    (error_report_filter.scrub), so in an error report it appears only in the "installId" field, never in free text.
"""
import re
import urllib.parse
import uuid

from . import diag_log
from . import update_config

SEND_KEY = "SendInstallId"
ID_KEY = "InstallId"
PARAM = "i"  # ?i=<install ID> on the manifest request
_INSTALL_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")  # str(uuid.uuid4())
_SENDING = {"on": True}  # the Cập nhật page's last choice in this session (update_options.set_sending)


def set_sending(on):
    """The user ticked or unticked the box: a check already under way (its retries) follows the new choice."""
    _SENDING["on"] = bool(on)


def current(install_id):
    """`install_id`, or None once the user unticked the box after the check began (read on the worker thread)."""
    return install_id if _SENDING["on"] else None


def is_install_id(value):
    """True for an install ID exactly as new_install_id creates it: a lowercase canonical UUID4."""
    return isinstance(value, str) and _INSTALL_ID.fullmatch(value) is not None


def feed_url(url, install_id=None):
    """The manifest request URL: `url`, plus ?i=<install ID> when one is sent. Anything that is not a valid install ID
    is never put into the URL."""
    if not is_install_id(install_id):
        return url
    separator = "&" if urllib.parse.urlsplit(url).query else "?"
    return url + separator + urllib.parse.urlencode({PARAM: install_id})


def new_install_id():
    """A fresh random ID (UUID4: 122 random bits, nothing taken from the machine)."""
    return str(uuid.uuid4())


def choose(values, create=new_install_id):
    """Pure: (ID to send or None, ID to store or None) from the resolved update settings."""
    if not values.get(SEND_KEY, True):
        return None, None
    current = values.get(ID_KEY, "")
    if is_install_id(current):
        return current, None
    fresh = create()
    return fresh, fresh


def add_to(ctx, info):
    """`info` plus "install_id" for update_fetch (None when turned off). Main thread: the first check stores the ID."""
    return dict(info, install_id=for_check(ctx))


def for_check(ctx):
    """The ID to send with this update check, or None. Call on the main thread (it may write the profile once).
    Never raises: on any failure the check runs without an ID, and an ID that could not be stored is not sent,
    so a read-only profile is not counted as a new machine at every check."""
    try:
        send, store = choose(update_config.settings(ctx))
        if store is not None and not update_config.save(ctx, ID_KEY, store):
            return None
        return send
    except Exception:  # noqa: BLE001 - the update check must work without the ID
        diag_log.exception("update_install_id")
        return None


def for_report(values):
    """Pure: the ID an error report carries, from the resolved update settings, or None. Never creates one: no ID when
    SendInstallId is off, or when no update check has stored a valid ID yet."""
    if not values.get(SEND_KEY, True):
        return None
    stored = values.get(ID_KEY, "")
    return stored if is_install_id(stored) else None


def for_error_report(ctx):
    """The ID to put in an error report now, or None. Reads the profile only (never writes) and never raises: on any
    failure the report goes without an ID."""
    try:
        return for_report(update_config.settings(ctx))
    except Exception:  # noqa: BLE001 - the report must work without the ID
        diag_log.exception("update_install_id")
        return None
