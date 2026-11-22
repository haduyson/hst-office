# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""macOS: the office stays open, behind a progress message, while the helper checks and copies the new app, and quits
only once the helper reports that it is ready (update-ready, written by update_helper_scripts RUN).

Then the app is gone for about a second (the swap and `open`) instead of the half minute the checks and the copy take.
With the old order, a user who saw no window for that long opened the app again from the Dock, and that copy ran on
inside a bundle that was then replaced under it. A failed check is reported at once and the office stays open; Cancel
in the progress message stops the helper, which removes its copy."""
import os
import threading
import time

READY_NAME = "update-ready"
WAIT_LIMIT = 15 * 60  # seconds; a slow disk copies the app in well under a minute
POLL = 0.3
MAX_SIZE = 128


class HelperFailed(Exception):
    """The helper's checks or copy failed before the quit; `code` is its failure code (update_outcome.CODES)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class PrepareCancelled(Exception):
    """Cancel in the progress message: the helper is stopped, the office stays open."""


def path(cache):
    return os.path.join(cache, READY_NAME)


def discard(cache):
    try:
        os.unlink(path(cache))
    except FileNotFoundError:
        pass


def read(cache, pid):
    """(code, failure) written by helper `pid`, or None when it has not written it (yet)."""
    try:
        with open(path(cache), encoding="ascii") as handle:
            fields = handle.read(MAX_SIZE).split()
    except (OSError, ValueError):
        return None
    if len(fields) != 3 or fields[0] != str(pid) or not fields[1].isdigit():
        return None
    return int(fields[1]), fields[2]


def wait(proc, cache, stop, limit=WAIT_LIMIT, clock=time.monotonic, sleep=time.sleep):
    """("ready" | "failed" | "exited" | "timeout" | "cancelled", failure code or None)."""
    started = clock()
    while True:
        mark = read(cache, proc.pid)
        if mark is not None:
            return ("ready", None) if mark[0] == 0 else ("failed", mark[1])
        if proc.poll() is not None:
            return "exited", None
        if stop.is_set():
            return "cancelled", None
        if clock() - started > limit:
            return "timeout", None
        sleep(POLL)


def message_key(code):
    """The update_texts key that explains a failure code."""
    return {"verify": "err_verify", "readonly": "err_readonly"}.get(code, "err_prepare")


def wait_with_dialog(ctx, peer, proc, cache):
    """Show "Đang chuẩn bị bản cập nhật…" until the helper is ready; raises HelperFailed or PrepareCancelled."""
    from . import update_ui as ui
    from .dialogs import CANCEL, Dialog
    from .update_texts import texts
    text = texts(ctx)
    dialog = Dialog(ctx, text["install_title"], 260, 50)
    dialog.label("status", text["preparing"], 8, 8, 244, 20, wrap=True)
    dialog.button("cancel", text["cancel"], 206, 32, 46, kind=CANCEL)
    outcome, stop, closed = [("exited", None)], threading.Event(), threading.Event()

    def work():
        try:
            outcome[0] = wait(proc, cache, stop)
        finally:
            while not closed.is_set():  # an end() requested before the modal loop runs is lost: repeat until closed
                ui.on_main_thread(ctx, lambda: None if closed.is_set() else dialog.end(1))
                closed.wait(POLL)
    worker = threading.Thread(target=work, name="hst-update-prepare", daemon=True)
    worker.start()
    try:
        finished = dialog.execute(peer)
    finally:
        closed.set()
    if not finished:  # Cancel or closed
        stop.set()
        worker.join()
        raise PrepareCancelled()
    worker.join()
    state, code = outcome[0]
    if state != "ready":
        raise HelperFailed(code or "install")
