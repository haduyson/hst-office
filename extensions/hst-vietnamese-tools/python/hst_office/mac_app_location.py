# SPDX-License-Identifier: AGPL-3.0-only
"""Where the running macOS app lives, and the one-time offer to move it into /Applications.

Started straight from the mounted .dmg (/Volumes/...), from an App Translocation path (macOS runs a quarantined download
from a random read-only mount) or from ~/Downloads, the bundle cannot be updated in place. offer_move_once() asks once per
version "Chuyển HST Office vào thư mục Ứng dụng?", copies the verified app into /Applications (administrator password when
needed), then quits so that the moved copy opens. update_target() tells the updater where to install instead.
The shell side is mac_move_script.MAC_MOVE: the signature, team and Gatekeeper checks run there before any copy.

A translocated bundle is recognised by its path (".../AppTranslocation/<id>/d/HST Office.app"); the extension does not
load native libraries, so its original location is unknown and that original is never deleted.
"""
import os
import platform
import traceback

from . import mac_move_script
from . import update_helper_cmd as cmd
from . import update_helper_scripts as scripts

APP_NAME = "HST Office.app"
DESTINATION = "/Applications/" + APP_NAME
MOVABLE = ("volume", "downloads", "translocated")
SCRIPT_NAME = "hst-move.sh"
MARKER = ("Library", "Application Support", "HSTOffice", "move-offered")
COPY_TIMEOUT = 900
CANCELLED = 2  # MAC_MOVE --copy: the administrator password dialog was cancelled


def _under(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def locate(bundle, home=None):
    """{"kind", "translocated", "source", "remove"} for a running bundle.

    kind: volume | downloads | applications | user-applications | translocated | other. source is the copy to move;
    remove is the copy to delete once the moved one opens (only a bundle that runs from ~/Downloads itself)."""
    bundle = os.path.normpath(bundle)
    home = os.path.normpath(os.path.expanduser("~") if home is None else home)
    translocated = "/AppTranslocation/" in bundle
    if translocated:
        kind = "translocated"
    elif _under(bundle, "/Volumes"):
        kind = "volume"
    elif _under(bundle, os.path.join(home, "Downloads")):
        kind = "downloads"
    elif _under(bundle, "/Applications"):
        kind = "applications"
    elif _under(bundle, os.path.join(home, "Applications")):
        kind = "user-applications"
    else:
        kind = "other"
    return {"kind": kind, "translocated": translocated, "source": bundle, "remove": bundle if kind == "downloads" else None}


def _writable(path):
    return os.access(path, os.W_OK) and os.access(os.path.dirname(path), os.W_OK)


def update_target(bundle, home=None, writable=None):
    """The bundle the updater replaces: the running one, or /Applications when the running one cannot be written."""
    place = locate(bundle, home)
    if place["translocated"] or (place["kind"] != "applications" and not (writable or _writable)(bundle)):
        return DESTINATION
    return bundle


def script_text():
    return scripts.HEADER + cmd.mac_swap() + mac_move_script.MAC_MOVE


def write_script(directory):
    """The private move script (mode 0700, never through a symlink); returns its validated path."""
    path = cmd.mac_path(os.path.join(os.path.abspath(directory), SCRIPT_NAME))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o700), "w", encoding="utf-8", newline="\n") as handle:
        os.chmod(path, 0o700)
        handle.write(script_text())
    return path


def copy_argv(script, source, dest, log):
    return ["/bin/sh", cmd.mac_path(script), "--copy", cmd.mac_bundle(source), cmd.mac_bundle(dest), cmd.mac_path(log)]


def reopen_argv(script, pid, dest, log, remove=None):
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive process ID")
    extra = [cmd.mac_bundle(remove)] if remove else []
    return ["/bin/sh", cmd.mac_path(script), "--reopen", str(pid), cmd.mac_bundle(dest), cmd.mac_path(log)] + extra


def first_offer(release, home=None):
    """True the first time for this release (and remembers it); False when it was already offered."""
    path = os.path.join(os.path.expanduser("~") if home is None else home, *MARKER)
    try:
        with open(path, encoding="utf-8") as handle:
            if handle.read().strip() == release:
                return False
    except (OSError, ValueError):
        pass
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(release + "\n")
    except OSError:
        traceback.print_exc()  # asked again next time rather than never
    return True


def copy(argv):
    """Run the --copy step (it may show the administrator password dialog) and return its exit code."""
    from . import update_launch as launch
    proc = launch.spawn(argv, "Darwin")
    try:
        return proc.wait(timeout=COPY_TIMEOUT)
    except Exception:  # noqa: BLE001 - timed out or interrupted: stop it, report a failed move
        traceback.print_exc()
        launch.cancel(proc)
        return 1


def _running_bundle(ctx):
    from .update_install import office_paths
    return office_paths(ctx, "Darwin")[1]


def _ask(ctx, title, text, buttons):
    from .update_install import _ask as ask
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    return ask(ctx, frame.getContainerWindow() if frame else None, title, text, buttons, text_height=40)


def _quit_and_reopen(ctx, argv):
    """Start the waiter that opens the moved copy, then close this office the normal way (save prompts included)."""
    from . import update_launch as launch
    proc, closing = launch.spawn(argv, "Darwin"), False
    try:
        closing = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
    finally:
        if not closing:  # Cancel at a save prompt: this copy keeps running, the moved one stays in /Applications
            launch.cancel(proc)


def _offer(ctx, home=None):
    from . import update_installer as installer
    from .update_fetch import release_info
    from .update_texts import texts
    place = locate(_running_bundle(ctx), home)
    if place["kind"] not in MOVABLE or not first_offer(release_info()["release"], home):
        return False
    text = texts(ctx)
    exists = os.path.lexists(DESTINATION)
    question = text["move_exists"] if exists else text["move_ask"] % text["move_from_" + place["kind"]]
    if _ask(ctx, text["move_title"], question, [(text["open" if exists else "move"], "go"), (text["later"], "later")]) != "go":
        return True
    cache = installer.cache_dir("Darwin")
    log = os.path.join(cache, "move.log")
    script = write_script(cache)
    remove = None
    if not exists:
        code = copy(copy_argv(script, place["source"], DESTINATION, log))
        if code == CANCELLED:
            return True
        if code != 0:
            _ask(ctx, text["move_title"], text["move_failed"] % log, [(text["close"], "close")])
            return True
        remove = place["remove"]
    _quit_and_reopen(ctx, reopen_argv(script, os.getpid(), DESTINATION, log, remove))
    return True


def offer_move_once(ctx):
    """Start-up hook, first in the start-up prompt order: True when a question was shown, so later prompts wait.

    Run it on the office's main thread after start-up (the question is modal). Never raises; False off macOS."""
    if platform.system() != "Darwin":
        return False
    try:
        return _offer(ctx)
    except Exception:  # noqa: BLE001 - never block start-up; the updater still installs into /Applications
        traceback.print_exc()
        return False
