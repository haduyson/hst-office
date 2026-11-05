# SPDX-License-Identifier: AGPL-3.0-only
"""Private HTTPS helper of the error report: one POST, run in its own process so DNS, TLS, the upload and the reply
share one wall-clock deadline that the parent enforces by killing it (error_report_send).

Input (stdin, JSON): {"url", "body" (the exact request body, text), "version", "proxy", "allow_test"}.
Output (stdout, JSON): {"status": <HTTP status>, "body": <reply text, at most 4 KiB>}; exit 1 when no HTTP answer
arrived (DNS, TLS, refused or reset connection). Redirects are never followed: a report goes to one fixed URL.
No cookies, no authentication, no header beyond Content-Type, Accept and the User-Agent "HSTOffice/<release>".
"""
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "hst_office"

from .error_report_payload import MAX_BODY, allowed_url
from .update_fetch import tls_context
from .update_logic import version_key

TIMEOUT = 15
MAX_REPLY = 4096


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then reports the 3xx status itself, which the caller treats as a server failure


def post(url, body, version, proxy=None, allow_test=False):
    """(status, reply bytes) of one POST; raises on a failed connection."""
    if not allowed_url(url, allow_test):
        raise ValueError("error report URL refused")
    version_key(version)  # also prevents User-Agent header injection
    data = body.encode("utf-8") if isinstance(body, str) else bytes(body)
    if len(data) > MAX_BODY:
        raise ValueError("error report too large")
    handlers = [_NoRedirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:
        handlers.append(urllib.request.ProxyHandler(proxy))
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "User-Agent": "HSTOffice/" + version, "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.build_opener(*handlers).open(request, timeout=TIMEOUT) as response:
            return response.status, response.read(MAX_REPLY)
    except urllib.error.HTTPError as error:
        try:
            reply = error.read(MAX_REPLY)
        except Exception:  # noqa: BLE001 - an error status without a readable body is still an answer
            reply = b""
        return error.code, reply


def main():
    try:
        args = json.loads(sys.stdin.buffer.read(MAX_BODY * 4 + 16384))
        status, reply = post(args["url"], args["body"], args["version"], args.get("proxy"), bool(args.get("allow_test")))
        sys.stdout.buffer.write(json.dumps({"status": status, "body": reply.decode("utf-8", "replace")}).encode())
        return 0
    except Exception:  # noqa: BLE001 - never expose URLs, proxy credentials or TLS exception details
        return 1


if __name__ == "__main__":
    sys.exit(main())
