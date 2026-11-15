# SPDX-License-Identifier: AGPL-3.0-only
"""How this Linux copy of HST Office was installed, and so which installer of the signed manifest updates it.

  "appimage"  started from an AppImage: $APPIMAGE is set by the AppImage runtime and this program lies inside its
              mount ($APPDIR), so a variable inherited from some other AppImage does not count;
  "deb"       dpkg owns <program>/soffice (`dpkg-query -S`): the apt path, as before;
  "rpm"       rpm owns it (`rpm -qf`): dnf / zypper / rpm;
  None        neither (an unpacked tree, a developer build, no package tool): treated as "deb", as every Linux
              install was before .rpm and AppImage existed.
The answer is computed once per office process. Platform keys: update_logic.ALL_PLATFORMS.
"""
import os
import platform
import shutil
import subprocess

from . import update_logic as logic

KIND_PLATFORM = {"deb": "linux", "rpm": "linux-rpm", "appimage": "linux-appimage"}
UPDATE_DIR = ".hst-office-update"  # beside the AppImage: same file system, so the final rename is atomic
_CACHE = {}


def program_dir():
    """The office's program directory, from the location of the bundled uno.py (no UNO context needed)."""
    import uno  # noqa: PLC0415 - only available inside the office
    return os.path.dirname(os.path.realpath(uno.__file__))


def _inside(path, directory):
    path, directory = os.path.realpath(path), os.path.realpath(directory)
    return path == directory or path.startswith(directory.rstrip(os.sep) + os.sep)


def _owns(argv, run):
    try:
        return run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def detect(program, environ, which=shutil.which, run=subprocess.run):
    """"appimage", "deb", "rpm" or None for the office whose program directory is `program`."""
    appimage, appdir = environ.get("APPIMAGE", ""), environ.get("APPDIR", "")
    if os.path.isabs(appimage) and os.path.isfile(appimage) and appdir and _inside(program, appdir):
        return "appimage"
    soffice = os.path.join(program, "soffice")
    for kind, argv in (("deb", ["dpkg-query", "-S", soffice]), ("rpm", ["rpm", "-qf", soffice])):
        if which(argv[0]) and _owns(argv, run):
            return kind
    return None


def kind(environ=None):
    """detect() for this process, cached (one or two short package-database queries)."""
    if "kind" not in _CACHE:
        try:
            _CACHE["kind"] = detect(program_dir(), os.environ if environ is None else environ)
        except Exception:  # noqa: BLE001 - no uno module or unreadable path: unknown (handled as .deb)
            _CACHE["kind"] = None
    return _CACHE["kind"]


def install_platform(system=None, machine=None, environ=None):
    """Manifest platform key of the installer (and the "Tải về" link) that updates this copy."""
    system, machine = system or platform.system(), machine or platform.machine()
    if system != "Linux":
        return logic.platform_key(system, machine)
    return KIND_PLATFORM[linux_kind(environ)]


def linux_kind(environ=None):
    """kind(), with an unknown install handled like a .deb one."""
    return kind(environ) or "deb"


def appimage_update_dir(environ=None):
    """Hidden directory beside the running AppImage for the download; ValueError when that directory is not writable."""
    environ = os.environ if environ is None else environ
    folder = os.path.dirname(environ.get("APPIMAGE", ""))
    if not os.path.isabs(folder) or not os.access(folder, os.W_OK | os.X_OK):
        raise ValueError("the AppImage's directory is not writable")
    return os.path.join(folder, UPDATE_DIR)
