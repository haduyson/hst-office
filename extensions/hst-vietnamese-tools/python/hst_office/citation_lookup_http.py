# SPDX-License-Identifier: AGPL-3.0-only
"""Private HTTPS helper of the reference lookup: one GET, run in its own process so DNS, TLS and the transfer
share one wall-clock deadline that the parent enforces by killing it (citation_lookup.http_transport).

Input (stdin, JSON): {"url", "accept", "version", "proxy"}. Output (stdout, JSON): {"status", "body"}
(body: text, at most 2 MB); exit 1 when no HTTP answer arrived. Only HTTPS to the lookup hosts is allowed, also
after a redirect (doi.org forwards to Crossref or DataCite). No cookies; headers: Accept and the User-Agent
"HSTOffice/<release>" only (never a contact address; an administrator-set one travels as a query parameter).
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

from .update_fetch import tls_context
from .update_logic import version_key

TIMEOUT = 15
MAX_BODY = 2 * 1024 * 1024
HOSTS = ("doi.org", "api.crossref.org", "data.crossref.org", "api.datacite.org", "data.datacite.org",
         "eutils.ncbi.nlm.nih.gov", "export.arxiv.org", "openlibrary.org")


def allowed(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname in HOSTS and not parts.username and parts.port in (None, 443)


class _AllowedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            return None  # urllib then reports the 3xx status itself
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get(url, accept, version, proxy=None):
    """(status, body bytes) of one GET; raises on a failed connection or a refused URL."""
    if not allowed(url):
        raise ValueError("lookup URL refused")
    version_key(version)  # also prevents User-Agent header injection
    agent = "HSTOffice/" + version
    handlers = [_AllowedRedirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:
        handlers.append(urllib.request.ProxyHandler(proxy))
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": accept})
    try:
        with urllib.request.build_opener(*handlers).open(request, timeout=TIMEOUT) as response:
            return response.status, response.read(MAX_BODY)
    except urllib.error.HTTPError as error:
        return error.code, b""


def main():
    try:
        args = json.loads(sys.stdin.buffer.read(65536))
        status, body = get(args["url"], args.get("accept", "application/json"), args["version"], args.get("proxy"))
        sys.stdout.buffer.write(json.dumps({"status": status, "body": body.decode("utf-8", "replace")}).encode())
        return 0
    except Exception:  # noqa: BLE001 - never expose URLs, proxy credentials or TLS exception details
        return 1


if __name__ == "__main__":
    sys.exit(main())
