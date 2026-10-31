# SPDX-License-Identifier: AGPL-3.0-only
"""Pure installer metadata, file verification and cache helpers (no UNO or network)."""
import hashlib
import hmac
import os
import re
import stat
import urllib.parse

_EXTENSIONS = {"windows": ".msi", "macos-arm": ".dmg", "macos-intel": ".dmg", "linux": ".deb"}
_NAME = re.compile(r"[A-Za-z0-9._-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GITHUB_PATH = "/haduyson/hst-office/releases/download/"
_REDIRECT_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
                   "github-releases.githubusercontent.com")


class InstallerError(Exception):
    """An installer file could not be read or did not match its signed metadata."""


def _url_parts(url, allow_test):
    if not isinstance(url, str):
        return None
    for char in url:
        if char.isspace() or ord(char) < 32:
            return None
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    if allow_test and parts.scheme == "http" and parts.hostname == "127.0.0.1":
        return parts
    if parts.scheme == "https" and parts.hostname and port is None and ":" not in parts.netloc:
        return parts
    return None


def _hst_host(host):
    return host == "hasontech.vn" or host.endswith(".hasontech.vn")


def is_installer_url(url, allow_test=False):
    """Accept a direct installer on HST or this project's GitHub releases."""
    parts = _url_parts(url, allow_test)
    if parts is None:
        return False
    name = parts.path.rsplit("/", 1)[-1]
    if not _NAME.fullmatch(name) or not name.endswith(tuple(_EXTENSIONS.values())):
        return False
    return (parts.scheme == "http" or _hst_host(parts.hostname)
            or (parts.hostname == "github.com" and parts.path.startswith(_GITHUB_PATH)))


def is_redirect_allowed(url, allow_test=False):
    """Allow only HST and GitHub's release delivery hosts after the initial URL."""
    parts = _url_parts(url, allow_test)
    return bool(parts and (parts.scheme == "http" or _hst_host(parts.hostname)
                          or parts.hostname in _REDIRECT_HOSTS))


def parse_installers(value, platforms, allow_test=False):
    """Validate metadata and derive a safe cache filename; malformed input raises ValueError."""
    if not isinstance(value, dict):
        raise ValueError("installers must be an object")
    result = {}
    for platform, entry in value.items():
        if platform not in platforms or platform not in _EXTENSIONS:
            raise ValueError("unknown installer platform: %r" % platform)
        if not isinstance(entry, dict):
            raise ValueError("installer %s must be an object" % platform)
        url, digest, size = entry.get("url"), entry.get("sha256"), entry.get("size")
        if not is_installer_url(url, allow_test):
            raise ValueError("installer %s: invalid URL" % platform)
        name = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
        if not name.endswith(_EXTENSIONS[platform]):
            raise ValueError("installer %s: wrong file extension" % platform)
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("installer %s: invalid sha256" % platform)
        if type(size) is not int or not 1 <= size <= 4294967296:
            raise ValueError("installer %s: size must be an integer in 1..4294967296" % platform)
        result[platform] = {"url": url, "sha256": digest, "size": size, "name": name}
    return result


def choose_installer(release, platform):
    return release.get("installers", {}).get(platform) if release else None


def verify_file(path, entry):
    """Check size before streaming SHA-256 in 1 MiB chunks."""
    try:
        with open(path, "rb") as handle:
            size = os.fstat(handle.fileno()).st_size
            if size != entry["size"]:
                raise InstallerError("size mismatch: expected %s, got %s" % (entry["size"], size))
            digest, size = hashlib.sha256(), 0
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
            if size != entry["size"]:
                raise InstallerError("size mismatch: file changed while reading")
            if not hmac.compare_digest(digest.hexdigest(), entry["sha256"]):
                raise InstallerError("sha256 mismatch: installer content differs from manifest")
    except OSError as exc:
        raise InstallerError("cannot read installer: %s" % exc) from exc


def cache_dir(system, environ=None, home=None):
    """Build the per-user cache path without creating directories."""
    environ = os.environ if environ is None else environ
    home = os.path.expanduser("~") if home is None else home
    if system == "Windows":
        base = environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, "HSTOffice", "update")
    if system == "Darwin":
        return os.path.join(home, "Library", "Caches", "HSTOffice", "update")
    return os.path.join(environ.get("XDG_CACHE_HOME") or os.path.join(home, ".cache"), "hst-office", "update")


def installer_path(cache, entry):
    return os.path.join(cache, entry["name"])


def cleanup(cache, keep_name=None):
    """Remove other regular files, preserving update.log, directories and all symlinks."""
    try:
        if not stat.S_ISDIR(os.lstat(cache).st_mode):
            return
        with os.scandir(cache) as entries:
            for entry in entries:
                try:
                    if entry.name not in (keep_name, "update.log") and entry.is_file(follow_symlinks=False):
                        os.unlink(entry.path)
                except OSError:
                    pass
    except OSError:
        pass
