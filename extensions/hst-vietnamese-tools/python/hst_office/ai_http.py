# SPDX-License-Identifier: AGPL-3.0-only
"""Private HTTPS helper of the Trợ lý AI: one request to an AI provider, run in its own process so DNS, TLS and the
transfer share one wall-clock deadline that the parent enforces by killing it (ai_client.http_transport).

Input (stdin, JSON): {"method", "url", "headers", "body", "provider", "key", "version", "proxy"}. The API key only
travels on stdin (never a command line, file or log) and becomes the provider's auth header here. Output (stdout,
JSON): {"status", "body"} (body text, at most 2 MB, also for an HTTP error, whose JSON names the reason); exit 1
when no HTTP answer arrived. Only HTTPS to the three provider hosts on port 443; redirects are refused; no cookies.
"""
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "hst_office"

from .ai_providers import PROVIDERS  # noqa: E402
from .update_fetch import tls_context  # noqa: E402
from .update_logic import version_key  # noqa: E402

TIMEOUT = 110  # the parent kills the helper at its own deadline (ai_client.DEADLINE)
MAX_BODY = 2 * 1024 * 1024
MAX_REQUEST = 512 * 1024
HEADER_NAMES = ("Content-Type", "Accept", "anthropic-version")


def allowed(url, provider):
    parts = urllib.parse.urlsplit(url)
    return (parts.scheme == "https" and provider in PROVIDERS and parts.hostname == PROVIDERS[provider]["host"]
            and not parts.username and not parts.password and parts.port in (None, 443) and not parts.fragment)


def valid_key(key):
    """Printable ASCII without spaces: no header injection, nothing a provider would issue otherwise."""
    return isinstance(key, str) and 8 <= len(key) <= 512 and all(33 <= ord(c) < 127 for c in key)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then reports the 3xx status itself; the key is never sent to another URL


def send(args):
    """(status, body bytes) of one request; raises ValueError on a refused request, OSError on no answer."""
    provider, url, method = args.get("provider"), args.get("url"), args.get("method")
    if not allowed(url, provider) or method not in ("GET", "POST") or not valid_key(args.get("key")):
        raise ValueError("AI request refused")
    version_key(args.get("version"))  # also prevents User-Agent header injection
    headers = {name: value for name, value in (args.get("headers") or {}).items()
               if name in HEADER_NAMES and isinstance(value, str) and value.isprintable()}
    header, prefix = PROVIDERS[provider]["auth"]
    headers[header] = prefix + args["key"]
    headers["User-Agent"] = "HSTOffice/" + args["version"]
    body = args.get("body")
    data = body.encode("utf-8") if method == "POST" and isinstance(body, str) else None
    if method == "POST" and (data is None or len(data) > MAX_REQUEST):
        raise ValueError("AI request refused")
    handlers = [_NoRedirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if args.get("proxy") is not None:
        handlers.append(urllib.request.ProxyHandler(args["proxy"]))
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(*handlers).open(request, timeout=TIMEOUT) as response:
            return response.status, response.read(MAX_BODY)
    except urllib.error.HTTPError as error:
        try:
            return error.code, error.read(MAX_BODY)
        finally:
            error.close()


def main():
    try:
        args = json.loads(sys.stdin.buffer.read(MAX_REQUEST + 65536))
        status, body = send(args)
        sys.stdout.buffer.write(json.dumps({"status": status, "body": body.decode("utf-8", "replace")}).encode())
        return 0
    except Exception as error:  # noqa: BLE001 - never echo the key, URLs, proxy credentials or TLS details
        if _timed_out(error):  # the provider stopped answering: not a connection problem of the user
            sys.stdout.buffer.write(b'{"timeout": true}')
            return 0
        return 1


def _timed_out(error):
    """A connect or read timeout, bare or wrapped by urllib (socket.timeout is TimeoutError)."""
    return isinstance(error, TimeoutError) or (isinstance(error, urllib.error.URLError)
                                               and isinstance(error.reason, TimeoutError))


if __name__ == "__main__":
    sys.exit(main())
