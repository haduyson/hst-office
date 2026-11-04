# SPDX-License-Identifier: AGPL-3.0-only
"""Private HTTPS helper, isolated so DNS, TLS, redirects and reads share one cancellable deadline."""
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "hst_office"

from .banner_urls import https_url
from .update_fetch import tls_context
from .update_logic import same_origin, version_key

TIMEOUT = 5


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not https_url(newurl) or not same_origin(req.full_url, newurl):
            raise ValueError("banner redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request(url, limit, version, proxy=None):
    """One bounded GET; callers apply the item allow-list before reaching this transport."""
    if not https_url(url):
        raise ValueError("banner HTTPS required")
    version_key(version)  # also prevents User-Agent header injection
    handlers = [_Redirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:
        handlers.append(urllib.request.ProxyHandler(proxy))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers={"User-Agent": "HSTOffice/" + version, "Accept": "*/*"})
    with opener.open(request, timeout=TIMEOUT) as response:
        if not https_url(response.geturl()) or not same_origin(url, response.geturl()):
            raise ValueError("banner final URL refused")
        if response.status != 200 or response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("banner response refused")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("banner response too large")
    return data


def head_status(url, version, proxy=None, timeout=TIMEOUT):
    """HTTP status of one HEAD; an error status is an answer, a failed connection raises."""
    if not https_url(url):
        raise ValueError("banner HTTPS required")
    version_key(version)
    handlers = [_Redirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:
        handlers.append(urllib.request.ProxyHandler(proxy))
    probe = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "HSTOffice/" + version, "Accept": "*/*"})
    try:
        with urllib.request.build_opener(*handlers).open(probe, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main():
    try:
        args = json.loads(sys.stdin.buffer.read(16385))
        if args.pop("head", False):
            sys.stdout.buffer.write(str(head_status(**args)).encode("ascii"))
            return 0
        data = request(**args)
        sys.stdout.buffer.write(data)
        return 0
    except Exception:  # noqa: BLE001 - never expose URLs, proxy credentials or TLS exception details
        return 1


if __name__ == "__main__":
    sys.exit(main())
