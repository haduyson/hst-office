# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Progress dialog of "Cập nhật ngay": downloads and verifies the installer (update_prepare) on a worker thread, with
Cancel; used by update_install."""
import threading
import time

from . import diag_log
from . import update_ui as ui
from .update_download import DownloadCancelled
from .update_prepare import PrepareError, prepare
from .update_texts import texts


def _size(n):
    return "%.1f MB" % (n / 1048576.0)


def _download_dialog(ctx, peer, info, proxy):
    """Progress dialog with Cancel around the worker thread; returns the prepare() result or a PrepareError code."""
    from .dialogs import CANCEL, Dialog
    TEXT = texts(ctx)
    dialog = Dialog(ctx, TEXT["progress_title"], 260, 56)
    label = dialog.label("status", TEXT["checking"], 8, 8, 244)
    bar = dialog._add("ProgressBar", "bar", 8, 22, 244, 10, ProgressValueMin=0, ProgressValueMax=100, ProgressValue=0)
    dialog.button("cancel", TEXT["cancel"], 206, 38, 46, kind=CANCEL)
    outcome, stop, closed, last = {}, threading.Event(), threading.Event(), [0.0]

    def progress(done, total):
        now = time.monotonic()
        if done < total and now - last[0] < 0.2:
            return
        last[0] = now
        percent = int(done * 100 / total) if total else 0

        def show():
            label.Label = TEXT["downloading"] % (percent, _size(total))
            bar.ProgressValue = percent
        ui.on_main_thread(ctx, show)

    def work():
        try:
            outcome["result"] = prepare(info, proxy, progress, stop.is_set)
        except DownloadCancelled:
            outcome["cancelled"] = True
        except PrepareError as exc:
            print("HST update install: %s" % exc, flush=True)
            outcome["code"] = exc.code
        except Exception:  # noqa: BLE001 - never let the worker die silently
            diag_log.exception("update_install")
            outcome["code"] = "err_network"
        while not closed.is_set():  # a request to end before the modal loop runs is lost: repeat until it is closed
            ui.on_main_thread(ctx, lambda: None if closed.is_set() else dialog.end(1))
            closed.wait(0.3)
    threading.Thread(target=work, name="hst-update-download", daemon=True).start()
    try:
        finished = dialog.execute(peer)
    finally:
        closed.set()
    if not finished:  # Cancel (or closed): the worker notices, removes its partial file and stops
        stop.set()
        return None
    return outcome
