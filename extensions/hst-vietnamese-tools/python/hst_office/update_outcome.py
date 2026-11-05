# SPDX-License-Identifier: AGPL-3.0-only
"""The result of a failed "Cập nhật ngay", shown once when the office starts again.

The external helper (update_helper_scripts*.py, update_helper_cmd.py) writes update-result.json beside update.log when
an install fails, then relaunches the old build. A success, a stop at the save prompt or a declined password question
writes nothing. The file stays on this machine: it is read here and deleted before anything is shown.
"""
import json
import os
import platform
import stat

from . import update_installer as installer
from .update_fetch import release_info

STATE_NAME = "update-result.json"
MAX_SIZE = 1024
CODES = ("auth", "install", "verify", "tool", "wait")


def take(cache, current_release):
    """Read and delete the record; the failure as a dict, or None when there is none or it no longer applies."""
    path = os.path.join(cache, STATE_NAME)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(MAX_SIZE + 1) if stat.S_ISREG(os.fstat(handle.fileno()).st_mode) else b""
        os.unlink(path)
        outcome = json.loads(raw.decode("ascii")) if 0 < len(raw) <= MAX_SIZE else None
    except (OSError, ValueError):
        return None
    if not isinstance(outcome, dict) or outcome.get("schema") != 1 or outcome.get("code") not in CODES:
        return None
    if type(outcome.get("exit")) is not int or not isinstance(outcome.get("to"), str):
        return None
    # Another version runs now (installed some other way): the old failure no longer matters.
    return outcome if outcome.get("from") == current_release else None


def message(text, outcome, log):
    """The whole message in the language of `text` (update_texts)."""
    name = "HST Office %s" % outcome["to"] if outcome["to"] else "HST Office"
    template = text["outcome_" + outcome["code"]]
    first = template % (name, outcome["exit"]) if outcome["code"] == "install" else template % name
    return "%s\n%s" % (first, text["outcome_next"] % log)


def _show(ctx, outcome, log):
    from .update_install import _ask, manual_download
    from .update_texts import texts
    text = texts(ctx)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = desktop.getCurrentFrame()
    answer = _ask(ctx, frame.getContainerWindow() if frame else None, text["install_title"], message(text, outcome, log),
                  [(text["download"], "download"), (text["close"], "close")], text_height=52)
    if answer == "download":
        manual_download(ctx)


def show_pending(ctx):
    """Called on every start-up: one stat when nothing is pending; the dialog runs after the start-up event."""
    cache = installer.cache_dir(platform.system())
    if not os.path.lexists(os.path.join(cache, STATE_NAME)):
        return False
    outcome = take(cache, release_info()["release"])
    if outcome is None:
        return False
    from . import update_ui as ui
    ui.on_main_thread(ctx, lambda: _show(ctx, outcome, os.path.join(cache, "update.log")))
    return True
