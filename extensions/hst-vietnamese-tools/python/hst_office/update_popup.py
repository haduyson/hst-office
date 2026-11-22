# SPDX-License-Identifier: AGPL-3.0-only
"""Pop-up "HST Office X is available" after the automatic start-up check found a new release.

The update check job (update_job.automatic_check) runs only when AutoCheck is on (administrator locks applied) and the
last check is CheckIntervalHours old; this module decides how the result is shown:
- a small window that does not block work (modeless, over the current window) with "Cập nhật ngay" (when installing is
  allowed and the signed manifest has an installer for this computer; otherwise "Tải về"), "Để sau" and
  "Bỏ qua bản này" (SkippedVersion, the same setting as the infobar's button);
- at most once a day per version (update-reminder.json beside update.log, on this machine only);
- not while a document is still loading, the start-up questions run (startup_prompts.prompting: the check starts
  before them) or a modal dialog of the extension is open: it waits; when that lasts beyond the wait, the infobar
  shows the release instead, so the pop-up never covers a question;
- when it is not due, or no window can hold it, the infobar of update_ui.notify is shown instead, as before.
"""
import json
import os
import platform
import threading
import time

from . import diag_log

REMINDER_NAME = "update-reminder.json"
REMIND_AFTER = 20 * 3600  # "once a day", with slack for the time of day the office is started
WAIT_STEP, WAIT_TRIES = 2.0, 300  # up to 10 minutes for a loading document or an open start-up dialog
_CURRENT = []  # the pop-up being shown (kept alive while it is open; runtime check hook)


def due(state, version, now):
    """Pure: True when the pop-up for `version` may be shown at `now` (state: the reminder record or None)."""
    if not isinstance(state, dict) or state.get("version") != version or type(state.get("shown")) is not int:
        return True
    return not (0 <= now - state["shown"] < REMIND_AFTER)


def load(cache):
    try:
        with open(os.path.join(cache, REMINDER_NAME), encoding="utf-8") as handle:
            return json.loads(handle.read(4096))
    except (OSError, ValueError):
        return None


def remember(cache, version, now):
    try:
        os.makedirs(cache, mode=0o700, exist_ok=True)
        path = os.path.join(cache, REMINDER_NAME)
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump({"version": version, "shown": int(now)}, handle)
        os.replace(path + ".tmp", path)
    except OSError:
        diag_log.exception("update_popup")  # shown again at the next check rather than never


def close_all():
    """Remove the pop-ups being shown (update_launch, before the office quits for an update)."""
    from . import dialog_modeless
    while _CURRENT:
        dialog_modeless.close(_CURRENT.pop())


def _cache():
    from . import update_installer as installer
    return installer.cache_dir(platform.system())


def _busy(ctx):
    """A document is still being imported, the start-up questions run, or a modal dialog of the extension is open (its
    window takes no input)."""
    from . import dialog_registry
    if dialog_registry.OPEN:
        return True
    try:
        from .startup_prompts import prompting
        if prompting():
            return True
    except Exception:  # noqa: BLE001 - unknown: the open dialogs above still count
        diag_log.exception("update_popup")
    try:
        from .welcome_job import loading
        return loading(ctx)
    except Exception:  # noqa: BLE001 - unknown: do not wait
        return False


def notify(ctx, release, installed, now=None, tries=0):
    """Main thread. The pop-up when it is due and a window can hold it, else the infobar (update_ui.notify)."""
    from . import update_ui as ui
    from .update_handler import set_available
    ui.STATE["release"] = release
    set_available(release)  # the File panel entry and the File tab dot, whether the pop-up or the infobar shows it
    now = int(time.time() if now is None else now)
    try:
        cache = _cache()
        if _CURRENT:  # still showing (an office left open for days): no second pop-up
            return None
        if not due(load(cache), release["version"], now):
            return ui.notify(ctx, release, installed)
        if _busy(ctx):
            if tries >= WAIT_TRIES:  # still busy: the infobar, never a pop-up over a question
                return ui.notify(ctx, release, installed)
            timer = threading.Timer(WAIT_STEP, ui.on_main_thread, args=(ctx, lambda: notify(ctx, release, installed, None, tries + 1)))
            timer.daemon = True
            timer.start()
            return None
        if show(ctx, release, installed):
            return remember(cache, release["version"], now)
    except Exception:  # noqa: BLE001 - never lose the notice: fall back to the infobar
        diag_log.exception("update_popup")
    return ui.notify(ctx, release, installed)


def run_action(ctx, release, action):
    """A button of the pop-up, after it closed: install | download | later | skip. "Bỏ qua bản này" also takes the
    release off the File panel entry and the File tab dot; "Để sau" leaves both as they are."""
    from . import update_ui as ui
    try:
        if action == "install":
            from .update_install import start
            start(ctx, _parent(ctx)[1])
        elif action == "download":
            ui.open_url(ctx, ui.release_download(release))
        elif action == "skip":
            from .update_handler import skip_release
            skip_release(ctx, release["version"])
    except Exception:  # noqa: BLE001 - a button must never raise into the office
        diag_log.exception("update_popup")


def _parent(ctx):
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    window = frame.getContainerWindow() if frame is not None else None
    return frame, window if window is not None and window.isVisible() else None


def show(ctx, release, installed):
    """Open the modeless pop-up over the current window; False when there is no visible window to hold it."""
    from . import dialog_modeless, update_ui as ui
    from .dialogs import Dialog
    from .update_texts import texts
    frame, parent = _parent(ctx)
    if parent is None:
        return False
    TEXT = texts(ctx)
    dialog = Dialog(ctx, TEXT["install_title"], 280, 54)
    dialog.label("message", TEXT["popup_text"] % (release["version"], installed), 8, 8, 264, 18, wrap=True)

    def close():
        if dialog in _CURRENT:
            _CURRENT.remove(dialog)
        dialog_modeless.close(dialog)

    def act(action):
        close()
        # Later, from the main loop: not on the stack of the button of a dialog that has just been disposed.
        ui.on_main_thread(ctx, lambda: run_action(ctx, release, action))

    first = ("install", TEXT["install"]) if ui.can_install(ctx, release) else ("download", TEXT["download"])
    buttons, x = (first, ("later", TEXT["later"]), ("skip", TEXT["skip"])), 8
    for index, (action, label) in enumerate(buttons):
        width = max(48, 8 + 5 * len(label))
        dialog.button("b%d" % index, label, x, 34, width, default=index == 0, callback=lambda a=action: act(a))
        x += width + 4
    dialog.closing = dialog_modeless.open_modeless(dialog, parent, on_close=close)
    _CURRENT.append(dialog)
    return True
