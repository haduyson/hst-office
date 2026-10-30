# SPDX-License-Identifier: AGPL-3.0-only
"""Network side of the update check: the only module of the extension allowed to use the network.

One GET for the manifest and one for its detached signature, HTTPS to office.hasontech.vn only, 5 s timeout,
at most 64 KiB each, redirects only within the same origin, no cookies, no personal data: the User-Agent
("HSTOffice/<release> (<OS>)") is the only information sent. The manifest is used only when its Ed25519
signature verifies with the public key built into the extension; anything else raises UpdateError, which
the caller logs without showing UI.

Test builds only (scripts/build-extensions.py --update-test-mode stamps data/release.json): the environment
variable HST_UPDATE_TEST_URL may point at a plain-HTTP server on 127.0.0.1 (any port). Release packages never carry
the stamp (scripts/check-extensions.py rejects it), so they ignore the variable.
"""
import base64
import os
import platform
import ssl
import urllib.error
import urllib.request

from . import ed25519
from . import update_logic as logic
from .data_files import load_data

TEST_URL_ENV = "HST_UPDATE_TEST_URL"
CA_BUNDLES = ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt")


class UpdateError(Exception):
    """The check could not be completed (offline, bad TLS, bad or unsigned manifest...)."""


def release_info():
    """{"release": "1.0.0-beta.2", "channel": "beta", "test_mode": bool} stamped into the package at build time."""
    info = load_data("release.json")
    release = info["release"]
    logic.version_key(release)
    return {"release": release, "channel": logic.channel_of(release), "test_mode": info.get("update_test_mode") is True}


def manifest_url(info, environ=None):
    environ = os.environ if environ is None else environ
    override = environ.get(TEST_URL_ENV, "")
    if override and info.get("test_mode") and logic.is_fetch_url(override, allow_test=True):
        return override
    return logic.MANIFEST_URL


class _SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not logic.same_origin(req.full_url, newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect to another origin refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def tls_context():
    """System trust store; bundled Pythons without one (macOS) fall back to the OS CA file."""
    context = ssl.create_default_context()
    if not context.cert_store_stats().get("x509_ca"):
        for path in CA_BUNDLES:
            if os.path.isfile(path):
                context.load_verify_locations(cafile=path)
                break
    return context


def _opener(proxy):
    handlers = [_SameOriginRedirect(), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:  # None: urllib's default (environment / system settings)
        handlers.append(urllib.request.ProxyHandler(proxy))
    return urllib.request.build_opener(*handlers)


def _get(opener, url, agent, allow_test):
    if not logic.is_fetch_url(url, allow_test):
        raise UpdateError("refused URL %s" % url)
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "*/*", "Cache-Control": "no-cache"})
    try:
        with opener.open(request, timeout=logic.TIMEOUT) as response:
            if not logic.is_fetch_url(response.geturl(), allow_test):
                raise UpdateError("final URL refused")
            data = response.read(logic.MAX_BYTES + 1)
    except UpdateError:
        raise
    except Exception as exc:  # noqa: BLE001 - offline, DNS, TLS, HTTP status, timeout: all "could not check"
        raise UpdateError("%s: %s" % (type(exc).__name__, exc))
    if len(data) > logic.MAX_BYTES:
        raise UpdateError("response too large")
    return data


def verify_manifest(data, signature_text, public_key=None):
    """Parsed channels when `signature_text` (base64 Ed25519 over the exact manifest bytes) verifies."""
    try:
        signature = base64.b64decode(signature_text.strip(), validate=True)
    except Exception:  # noqa: BLE001 - binascii.Error / bad type: unsigned for our purposes
        raise UpdateError("signature is not base64")
    if not ed25519.verify(public_key or logic.PUBLIC_KEY, bytes(data), signature):
        raise UpdateError("bad manifest signature")
    try:
        return logic.parse_manifest(data)
    except logic.ManifestError as exc:
        raise UpdateError("manifest rejected: %s" % exc)


def fetch_channels(info, proxy=None, environ=None):
    """Download, verify and parse the manifest; raises UpdateError on any failure."""
    url = manifest_url(info, environ)
    allow_test = url != logic.MANIFEST_URL
    agent = logic.user_agent(info["release"], platform.system())
    opener = _opener(proxy)
    data = _get(opener, url, agent, allow_test)
    signature = _get(opener, url + logic.SIGNATURE_SUFFIX, agent, allow_test)
    try:
        text = signature.decode("ascii")
    except UnicodeDecodeError:
        raise UpdateError("signature is not text")
    return verify_manifest(data, text)
