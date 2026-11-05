# SPDX-License-Identifier: AGPL-3.0-only
"""Send one error report and turn the answer into an outcome the dialog can show.

Called on a worker thread only after the user pressed "Gửi" in the dialog; nothing here runs on its own. The POST
runs in the private helper process (error_report_http.py) under a 15-second wall-clock deadline that covers DNS,
proxy, TLS, upload and reply; at expiry the helper is killed (banner_fetch._run, the same supervisor as the banner
feed). One call is one request; a retry from the dialog sends the same reportId, which the server answers with the
original ticket.

Test packages only (scripts/build-extensions.py --update-test-mode): HST_ERROR_REPORT_TEST_URL may point at a
plain-HTTP server on 127.0.0.1. Release packages ignore the variable.
"""
import json
import os
import re

from . import banner_fetch
from .error_report_payload import ENDPOINT, allowed_url

DEADLINE = 15
TEST_URL_ENV = "HST_ERROR_REPORT_TEST_URL"
_TICKET = re.compile(r"[\x21-\x7e](?:[\x20-\x7e]{0,30}[\x21-\x7e])?")  # shown as given, e.g. HSTO-000123

# Outcome kinds: sent (201/200 with a ticket), invalid (400), too_large (413), rate_limited (429),
# server (5xx, another status or an unreadable answer), network (no answer, timeout included).
OFFER_EMAIL = ("rate_limited", "server", "network")


class Outcome:
    def __init__(self, kind, ticket="", status=0):
        self.kind, self.ticket, self.status = kind, ticket, status

    @property
    def offers_email(self):
        return self.kind in OFFER_EMAIL

    def __repr__(self):
        return "Outcome(%r, %r, %r)" % (self.kind, self.ticket, self.status)


def endpoint(test_mode, environ=None):
    """The fixed endpoint, or the local test server of a test package."""
    environ = os.environ if environ is None else environ
    override = environ.get(TEST_URL_ENV, "")
    if test_mode and override and allowed_url(override, allow_test=True):
        return override
    return ENDPOINT


def classify(status, body):
    """Outcome of an HTTP answer (status, reply text) under the API contract."""
    if status in (200, 201):
        try:
            ticket = json.loads(body).get("ticket", "")
        except (ValueError, AttributeError):
            ticket = ""
        if isinstance(ticket, str) and _TICKET.fullmatch(ticket):
            return Outcome("sent", ticket, status)
        return Outcome("server", status=status)
    kinds = {400: "invalid", 413: "too_large", 429: "rate_limited"}
    return Outcome(kinds.get(status, "server"), status=status)


def send(body, version, proxy=None, test_mode=False, environ=None, timeout=DEADLINE, run=None):
    """Outcome of one POST of `body` (bytes from error_report_payload.encode) within `timeout` seconds."""
    run = run or banner_fetch._run
    request = json.dumps({"url": endpoint(test_mode, environ), "body": body.decode("utf-8"), "version": version,
                          "proxy": proxy, "allow_test": bool(test_mode)}, ensure_ascii=False).encode("utf-8")
    try:
        reply = json.loads(run(request, timeout, "error_report_http.py"))
        return classify(int(reply["status"]), reply.get("body", ""))
    except (OSError, ValueError, KeyError, TypeError):  # deadline (TimeoutError), no answer, unreadable helper output
        return Outcome("network")
