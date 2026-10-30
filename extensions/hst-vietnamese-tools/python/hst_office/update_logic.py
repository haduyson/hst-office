# SPDX-License-Identifier: AGPL-3.0-only
"""Pure logic of the update check (no uno, no network): versions, manifest, channels, URLs, throttle.

Manifest (website/office.hasontech.vn/update/latest.json, detached Ed25519 signature in latest.json.sig):
  {"schema": 1, "channels": {"stable": <release>|null, "beta": <release>|null}}
  <release> = {"version": "1.0.0-beta.2", "date": "YYYY-MM-DD", "notes": "https://office.hasontech.vn/...",
               "downloads": {"windows"|"macos-arm"|"macos-intel"|"linux": "https://office.hasontech.vn/tai/..."},
               "critical": false}   # optional; critical releases ignore "skip this version"
Beta installs are offered the newest of beta and stable; stable installs only stable.
"""
import json
import re
import urllib.parse

MANIFEST_URL = "https://office.hasontech.vn/update/latest.json"
SIGNATURE_SUFFIX = ".sig"
# Ed25519 public key of the manifest signer; the private key never enters the repository (docs/UPDATE_CHECK.md).
PUBLIC_KEY = bytes.fromhex("d0f221c93fa61b12b57815046e3bce720006fb4b0b2ce57e67bed7c250a6c1e7")
FETCH_HOST = "office.hasontech.vn"
LINK_HOSTS = ("hasontech.vn",)  # links in the manifest: hasontech.vn and its subdomains, https only
CHECK_INTERVAL = 24 * 60 * 60
TIMEOUT = 5
MAX_BYTES = 64 * 1024
SCHEMA = 1
CHANNELS = ("stable", "beta")
PLATFORMS = ("windows", "macos-arm", "macos-intel", "linux")
TEST_HOST = "127.0.0.1"  # local test server, accepted only by packages built with --update-test-mode

_SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                     r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
                     r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class ManifestError(ValueError):
    """The manifest is malformed; the check fails silently (logged only)."""


def version_key(text):
    """Sort key with SemVer 2.0 precedence: 1.0.0-beta.2 < 1.0.0-beta.10 < 1.0.0 < 1.0.1 (build metadata ignored)."""
    m = _SEMVER.fullmatch(text.strip()) if isinstance(text, str) else None
    if not m:
        raise ValueError("not a semantic version: %r" % (text,))
    core = tuple(int(g) for g in m.groups()[:3])
    if m.group(4) is None:
        return core + (1, ())
    pre = tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in m.group(4).split("."))
    return core + (0, pre)


def is_valid_version(text):
    try:
        version_key(text)
        return True
    except ValueError:
        return False


def channel_of(release):
    """Installs of a pre-release (1.0.0-beta.2) follow the beta channel, the rest stable."""
    return "beta" if "-" in release.split("+")[0] else "stable"


def _host_ok(host, allowed):
    return any(host == a or host.endswith("." + a) for a in allowed)


def is_safe_link(url):
    """https link to hasontech.vn (or a subdomain), no credentials, no odd port: opened in the browser."""
    if not isinstance(url, str) or any(c.isspace() for c in url):
        return False
    parts = urllib.parse.urlsplit(url)
    return (parts.scheme == "https" and parts.hostname is not None and parts.username is None
            and parts.port is None and _host_ok(parts.hostname, LINK_HOSTS))


def is_fetch_url(url, allow_test=False):
    """Manifest URL: https://office.hasontech.vn/... only; plain HTTP to 127.0.0.1 only for test builds."""
    if not isinstance(url, str) or any(c.isspace() for c in url):
        return False
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    if parts.scheme == "https" and parts.hostname == FETCH_HOST and port in (None, 443):
        return True
    return bool(allow_test and parts.scheme == "http" and parts.hostname == TEST_HOST)


def same_origin(old, new):
    """A redirect is followed only to the same scheme, host and port."""
    a, b = urllib.parse.urlsplit(old), urllib.parse.urlsplit(new)
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def _release(name, entry):
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ManifestError("channel %s: not an object" % name)
    version, date, notes = entry.get("version"), entry.get("date"), entry.get("notes")
    downloads, critical = entry.get("downloads"), entry.get("critical", False)
    if not is_valid_version(version):
        raise ManifestError("channel %s: bad version %r" % (name, version))
    if not (isinstance(date, str) and _DATE.fullmatch(date)):
        raise ManifestError("channel %s: bad date %r" % (name, date))
    if not is_safe_link(notes):
        raise ManifestError("channel %s: bad notes URL" % name)
    if not isinstance(downloads, dict) or not downloads:
        raise ManifestError("channel %s: no downloads" % name)
    for key, url in downloads.items():
        if key not in PLATFORMS or not is_safe_link(url):
            raise ManifestError("channel %s: bad download %r" % (name, key))
    if not isinstance(critical, bool):
        raise ManifestError("channel %s: critical must be boolean" % name)
    return {"channel": name, "version": version, "date": date, "notes": notes, "downloads": dict(downloads),
            "critical": critical}


def parse_manifest(data):
    """Validated {"stable": release|None, "beta": release|None} from the manifest bytes."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ManifestError("not JSON: %s" % exc)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("channels"), dict):
        raise ManifestError("unsupported schema")
    return {name: _release(name, doc["channels"].get(name)) for name in CHANNELS}


def select_update(channels, installed, channel):
    """Newest release newer than `installed` that the install's channel may see, else None."""
    names = ("beta", "stable") if channel == "beta" else ("stable",)
    current = version_key(installed)
    best = None
    for name in names:
        rel = channels.get(name)
        if rel and version_key(rel["version"]) > current and (best is None or version_key(rel["version"]) > version_key(best["version"])):
            best = rel
    return best


def should_notify(release, skipped):
    """False when the user chose "skip this version" for exactly this version (unless it is critical)."""
    return bool(release) and (release["critical"] or release["version"] != (skipped or ""))


def check_due(now, last):
    """At most one automatic check per 24 h; a clock set back by the user makes the check due again."""
    return not (0 <= now - int(last or 0) < CHECK_INTERVAL)


def platform_key(system, machine):
    system, machine = (system or "").lower(), (machine or "").lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos-arm" if machine in ("arm64", "aarch64") else "macos-intel"
    return "linux"


def download_url(release, platform):
    """Download link of this platform; the release notes page when the platform has none."""
    return release["downloads"].get(platform) or release["notes"]


def user_agent(installed, system):
    """The only data sent with the request: product version and operating system name."""
    os_name = {"windows": "Windows", "darwin": "macOS", "linux": "Linux"}.get((system or "").lower(), "Other")
    return "HSTOffice/%s (%s)" % (installed, os_name)
