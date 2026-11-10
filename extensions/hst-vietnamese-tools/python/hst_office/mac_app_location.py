# SPDX-License-Identifier: AGPL-3.0-only
"""Where the running macOS app lives, and the one-time offer to move it into /Applications.

Started straight from the mounted .dmg (/Volumes/...), from an App Translocation path (macOS runs a quarantined download
from a random read-only mount) or from ~/Downloads, the bundle cannot be updated in place. offer_move_once() asks once per
version "Chuyển HST Office vào thư mục Ứng dụng?", copies the verified app into /Applications (administrator password when
needed), then quits so that the moved copy opens. update_target() tells the updater where to install instead.
mac_move_script runs the signature, team and Gatekeeper checks before any copy. A translocated bundle is recognised by
its path (".../AppTranslocation/<id>/d/..."): without native libraries its original location is unknown, never deleted.
"""
import os
import platform
import traceback

from . import mac_move_script as move

APP_NAME = "HST Office.app"
DESTINATION = "/Applications/" + APP_NAME
MOVABLE = ("volume", "downloads", "translocated")
MARKER = ("Library", "Application Support", "HSTOffice", "move-offered")


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
    """The bundle the updater replaces. Only a translocated bundle, or one on a volume that cannot be written (the .dmg),
    goes to /Applications; any other bundle is replaced where it is, with the administrator password if needed."""
    place = locate(bundle, home)
    if place["translocated"] or (place["kind"] == "volume" and not (writable or _writable)(bundle)):
        return DESTINATION
    return bundle


def _marker(home):
    return os.path.join(os.path.expanduser("~") if home is None else home, *MARKER)


def offered(release, home=None):
    """True when the question was already shown for this release."""
    try:
        with open(_marker(home), encoding="utf-8") as handle:
            return handle.read().strip() == release
    except (OSError, ValueError):
        return False


def remember(release, home=None):
    path = _marker(home)
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(release + "\n")
    except OSError:
        traceback.print_exc()  # asked again next time rather than never


def _running_bundle(ctx):
    from .update_install import office_paths
    return office_paths(ctx, "Darwin")[1]


def _peer(ctx):
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    return frame.getContainerWindow() if frame else None


def _ask(ctx, title, text, buttons):
    from .update_install import _ask as ask
    return ask(ctx, _peer(ctx), title, text, buttons, text_height=40)


def _tell(ctx, text, message):
    try:
        _ask(ctx, text["move_title"], message, [(text["close"], "close")])
    except Exception:  # noqa: BLE001 - not even the message could be shown
        traceback.print_exc()


def _with_progress(ctx, title, message, work):
    """work() on a worker thread behind a small modal message, so that the office keeps repainting; its result."""
    import threading
    from . import update_ui as ui
    from .dialogs import Dialog
    dialog = Dialog(ctx, title, 250, 30)
    dialog.label("status", message, 8, 10, 234)
    result, closed = [1], threading.Event()

    def run():
        try:
            result[0] = work()
        except Exception:  # noqa: BLE001 - reported as a failed move
            traceback.print_exc()
        while not closed.is_set():  # an end() requested before the modal loop runs is lost: repeat until closed
            ui.on_main_thread(ctx, lambda: None if closed.is_set() else dialog.end(1))
            closed.wait(0.3)
    worker = threading.Thread(target=run, name="hst-move-copy", daemon=True)
    worker.start()
    try:
        dialog.execute(_peer(ctx))
    finally:
        closed.set()
    worker.join()  # only waits when the user closed the message early
    return result[0]


def _quit_and_reopen(ctx, argv):
    """Start the waiter that opens the moved copy, then close this office the normal way (save prompts included)."""
    from . import update_launch as launch
    # Cancel at a save prompt: this copy keeps running, the moved one stays in /Applications.
    launch.spawn_and_quit(ctx, argv, "Darwin")


def _move(ctx, text, place, exists):
    from . import update_installer as installer
    cache = installer.cache_dir("Darwin")
    log = os.path.join(cache, move.LOG_NAME)
    script = move.write_script(cache)
    move.cap_log(log)
    remove = None
    if not exists:
        argv = move.copy_argv(script, place["source"], DESTINATION, log)
        code = _with_progress(ctx, text["move_title"], text["move_progress"], lambda: move.run_copy(argv))
        if code == move.CANCELLED:
            return
        if code != 0:
            _tell(ctx, text, text["move_slow"] if code == move.TIMED_OUT else text["move_failed"] % log)
            return
        remove = place["remove"]
    _quit_and_reopen(ctx, move.reopen_argv(script, os.getpid(), DESTINATION, log, remove))


def _offer(ctx, home=None):
    """True once the question was shown. The version counts as offered only after it was answered."""
    from .update_fetch import release_info
    from .update_texts import texts
    place = locate(_running_bundle(ctx), home)
    release = release_info()["release"]
    if place["kind"] not in MOVABLE or offered(release, home):
        return False
    text = texts(ctx)
    exists = os.path.lexists(DESTINATION)
    question = text["move_exists"] if exists else text["move_ask"] % text["move_from_" + place["kind"]]
    answer = _ask(ctx, text["move_title"], question, [(text["open" if exists else "move"], "go"), (text["later"], "later")])
    remember(release, home)
    if answer == "go":
        try:
            _move(ctx, text, place, exists)
        except Exception:  # noqa: BLE001 - never silent after the click: script, path or start of the helper failed
            traceback.print_exc()
            _tell(ctx, text, text["move_error"])
    return True


def offer_move_once(ctx):
    """Start-up hook, first in the start-up prompt order: True when a question was shown, so later prompts wait.

    Run it on the office's main thread after start-up (the question is modal). Never raises; False off macOS and when
    something failed before the question could be shown (that version is then offered again at the next start)."""
    if platform.system() != "Darwin":
        return False
    try:
        return _offer(ctx)
    except Exception:  # noqa: BLE001 - never block start-up; the updater still installs into /Applications
        traceback.print_exc()
        return False
