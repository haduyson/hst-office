# SPDX-License-Identifier: AGPL-3.0-only
"""Launchers of HST Writer, HST Sheets and HST Slides outside the office (no uno; tested in tests/unit).

macOS: the three launcher apps ship inside the bundle (HST Office.app/Contents/Helpers/<name>.app, built by
scripts/macos/make-app-launchers.py). add_to_dock() pins the missing ones with `defaults write com.apple.dock
persistent-apps -array-add` and restarts the Dock; the tiles name the launchers by path, so an in-place update of
HST Office keeps them working. Linux: the menu launchers of the .deb (vn.hasontech.hstoffice-<module>.desktop) are
copied to the desktop folder, made executable and marked trusted for GNOME (gio metadata::trusted). Windows: the
installer creates the desktop shortcuts (hst-msi-app-desktop-shortcuts.patch); nothing here.
"""
import configparser
import os
import plistlib
import shutil
import subprocess
import urllib.parse
from xml.sax.saxutils import escape

from .default_apps_linux import DESKTOP_IDS, _data_dirs

APPS = (("writer", "HST Writer"), ("calc", "HST Sheets"), ("impress", "HST Slides"))
HELPERS = ("Contents", "Helpers")
DOCK_DOMAIN = "com.apple.dock"
TIMEOUT = 15


class ShortcutError(RuntimeError):
    """A failure the user is told about in Vietnamese (the message is the text shown)."""


def _run(argv, stdin=None):
    try:
        return subprocess.run(argv, input=stdin, capture_output=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ShortcutError("Không chạy được %s: %s" % (os.path.basename(argv[0]), exc)) from exc


# ---- macOS Dock --------------------------------------------------------------------------------------------------
def mac_launchers(bundle):
    """[(name, launcher bundle path)] inside the HST Office bundle, in menu order (pure)."""
    return [(name, os.path.join(bundle, *HELPERS, name + ".app")) for _module, name in APPS]


def dock_url(path):
    """The file URL the Dock stores for an app bundle: percent-encoded, with a trailing slash (pure)."""
    return "file://" + urllib.parse.quote(os.path.normpath(path)) + "/"


def _url_path(url):
    if not isinstance(url, str) or not url.startswith("file://"):
        return None  # web links, other tile kinds and damaged entries name no app
    return os.path.normpath(urllib.parse.unquote(urllib.parse.urlparse(url).path))


def dock_paths(dock_plist):
    """Paths of the apps pinned in the Dock (persistent-apps of an exported com.apple.dock plist; pure)."""
    paths = set()
    for tile in (dock_plist or {}).get("persistent-apps") or []:
        try:
            path = _url_path(tile["tile-data"]["file-data"]["_CFURLString"])
        except (KeyError, TypeError):
            continue
        if path:
            paths.add(path)
    return paths


def missing_from_dock(launchers, dock_plist):
    """The launchers not pinned yet (pure)."""
    pinned = dock_paths(dock_plist)
    return [(name, path) for name, path in launchers if os.path.normpath(path) not in pinned]


def dock_tile(name, path):
    """The `defaults write ... -array-add` argument of one app tile (pure)."""
    return ("<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>%s</string>"
            "<key>_CFURLStringType</key><integer>15</integer></dict><key>file-label</key><string>%s</string></dict>"
            "<key>tile-type</key><string>file-tile</string></dict>" % (escape(dock_url(path)), escape(name)))


def read_dock():
    done = _run(["defaults", "export", DOCK_DOMAIN, "-"])
    if done.returncode != 0:
        raise ShortcutError("Không đọc được cấu hình Dock.")
    try:
        return plistlib.loads(done.stdout)
    except Exception as exc:  # noqa: BLE001 - plistlib raises several types for a damaged file
        raise ShortcutError("Không đọc được cấu hình Dock.") from exc


def dock_status(bundle):
    """(launchers, the ones not in the Dock yet). Raises ShortcutError when this bundle has no launchers."""
    launchers = mac_launchers(bundle)
    absent = [name for name, path in launchers if not os.path.isdir(path)]
    if absent:
        raise ShortcutError("Bản HST Office này không có %s." % ", ".join(absent))
    return launchers, missing_from_dock(launchers, read_dock())


def add_to_dock(missing):
    """Pin `missing` [(name, path)], check that the Dock settings hold them, then restart the Dock."""
    for name, path in missing:
        if _run(["defaults", "write", DOCK_DOMAIN, "persistent-apps", "-array-add", dock_tile(name, path)]).returncode:
            raise ShortcutError("Không thêm được %s vào Dock." % name)
    left = missing_from_dock(missing, read_dock())
    if left:
        raise ShortcutError("Dock không ghi nhận %s." % ", ".join(name for name, _path in left))
    _run(["killall", "Dock"])  # the Dock restarts by itself and reads the new tiles


# ---- Linux desktop -----------------------------------------------------------------------------------------------
def desktop_dir(home=None, environ=None, user_dirs_text=None):
    """The desktop folder: XDG_DESKTOP_DIR of ~/.config/user-dirs.dirs (localised names such as "Màn hình nền"),
    else ~/Desktop (pure when `user_dirs_text` is given)."""
    home = home or os.path.expanduser("~")
    environ = os.environ if environ is None else environ
    if user_dirs_text is None:
        config = environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        try:
            with open(os.path.join(config, "user-dirs.dirs"), encoding="utf-8") as handle:
                user_dirs_text = handle.read()
        except OSError:
            user_dirs_text = ""
    for line in user_dirs_text.splitlines():
        key, _, value = line.strip().partition("=")
        if key == "XDG_DESKTOP_DIR" and value:
            value = value.strip().strip('"').replace("$HOME", home)
            if os.path.isabs(value) and os.path.normpath(value) != os.path.normpath(home):
                return os.path.normpath(value)
    return os.path.join(home, "Desktop")


def installed_launchers(data_dirs=None):
    """[(name, desktop id, installed launcher path)] of the three apps. Raises ShortcutError when one is missing."""
    found, absent = [], []
    for module, name in APPS:
        desktop = DESKTOP_IDS[module]
        path = next((p for p in (os.path.join(d, "applications", desktop) for d in (data_dirs or _data_dirs()))
                     if os.path.isfile(p)), None)
        if path is None:
            absent.append(name)
        else:
            found.append((name, desktop, path))
    if absent:
        raise ShortcutError("Không tìm thấy lối tắt trình đơn của %s." % ", ".join(absent))
    return found


def check_launcher(text, name):
    """True when the launcher text is an application entry named `name` (pure)."""
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(text)
    except configparser.Error:
        return False
    entry = "Desktop Entry"
    return (parser.get(entry, "Type", fallback="") == "Application" and parser.get(entry, "Name", fallback="") == name
            and bool(parser.get(entry, "Exec", fallback="")))


def copy_to_desktop(launchers, folder):
    """Copy each launcher into `folder` under its desktop id (running it again replaces, never doubles), executable
    and trusted. Returns the paths written."""
    os.makedirs(folder, exist_ok=True)
    written = []
    for name, desktop, source in launchers:
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        if not check_launcher(text, name):
            raise ShortcutError("Lối tắt trình đơn của %s không hợp lệ." % name)
        target = os.path.join(folder, desktop)
        partial = target + ".tmp"
        with open(partial, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(partial, 0o755)  # desktops start only executable launchers
        os.replace(partial, target)
        written.append(target)
    if shutil.which("gio"):
        for target in written:  # GNOME asks "Allow Launching" for untrusted ones; elsewhere a harmless attribute
            _run(["gio", "set", target, "metadata::trusted", "true"])
    return written
