# SPDX-License-Identifier: AGPL-3.0-only
"""Document tab checks of check-windows-smoke.py (see there).

The first-start welcome dialog waits until no document is loading (welcome_job.run_later), so on a busy machine it can
open in the middle of this section; a modal dialog over the tabs then blocks closing a tab and quitting the office.
While the section runs, a sweeper closes that dialog only (it is checked earlier, when it opens during the first load)
and notes it in the life-cycle record."""
import threading
import time

from windows_smoke_report import LIFE, office_alive, record
from windows_smoke_ui import close_dialog, open_document, top_windows, window_title

WELCOME_TITLE = "HST Office chào đón bạn"  # Vietnamese in every UI language (welcome_job.show_welcome)


def close_welcome_while(ctx, running):
    """Close the deferred welcome dialog whenever it opens, until running is cleared."""
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    while running.is_set():
        try:
            for window in top_windows(toolkit):
                if window_title(window).startswith(WELCOME_TITLE):
                    LIFE.note("harness closed the deferred welcome dialog")
                    close_dialog(window)
        except Exception:  # noqa: BLE001 - windows come and go
            pass
        time.sleep(0.5)


def tab_checks(ctx, desktop):
    """Document tabs (HST Office): three documents form one tab group with one shown window, the tab
    command switches, closing a tab shows the neighbour. Runs in the office of the smoke test."""
    def frames():
        access = desktop.getFrames()
        return [access.getByIndex(i) for i in range(access.getCount())]

    def shown():
        return [f for f in frames() if f.getContainerWindow().isVisible()]

    def wait(predicate, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - UNO objects change while windows open and close
                pass
            time.sleep(0.3)
        return False

    running = threading.Event()
    running.set()
    threading.Thread(target=close_welcome_while, args=(ctx, running), daemon=True).start()
    try:
        _tabs(ctx, desktop, frames, shown, wait)
    finally:
        running.clear()


def _tabs(ctx, desktop, frames, shown, wait):
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    start = len(frames())
    docs = [open_document(ctx, desktop, kind) for kind in ("swriter", "scalc", "simpress")]
    record("tabs: three documents open", all(docs) and len(frames()) == start + 3, len(frames()))
    record("tabs: one shown window (others parked)", wait(lambda: len(shown()) == 1), len(shown()))
    before = shown()[0].getTitle()
    began = time.time()
    helper.executeDispatch(shown()[0], ".uno:NextDocumentTab", "_self", 0, ())
    record("tabs: NextDocumentTab shows another tab",
           wait(lambda: len(shown()) == 1 and shown()[0].getTitle() != before),
           "%s, %.2f s" % (shown()[0].getTitle() if shown() else "-", time.time() - began))
    for doc in docs:
        doc.setModified(False)
    helper.executeDispatch(shown()[0], ".uno:CloseWin", "_self", 0, ())
    record("tabs: closing a tab shows the neighbour",
           wait(lambda: len(frames()) == start + 2 and len(shown()) == 1 and shown()[0].isActive()),
           "frames=%d shown=%d" % (len(frames()), len(shown())))
    for doc in docs:
        try:
            doc.close(True)
            LIFE.note("test closed a tab document")
        except Exception as error:  # noqa: BLE001 - already closed (DisposedException) or the office is gone
            LIFE.note("test close raised %s" % type(error).__name__)
        LIFE.note("office %s, frames=%s" % ("alive" if office_alive(ctx) else "GONE", len(frames()) if office_alive(ctx) else "-"))
