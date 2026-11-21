# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: the end-of-run message on the document window's status bar, never in a dialog.

A modal box after Alt+\\ held the keyboard until Enter, so the user could neither type on nor undo at once. The line
is the frame's status indicator (XStatusIndicator.start with no range): it never takes the focus, and it goes away
after NOTICE_SECONDS or at the user's next key press or click in the document, whichever comes first. Key and click
events always go on to the document (the handlers never consume them)."""
import threading

import unohelper
from com.sun.star.awt import XCallback, XKeyHandler, XMouseClickHandler

from . import diag_log

NOTICE_SECONDS = 5.0


def _daemon_timer(delay, action):
    timer = threading.Timer(delay, action)
    timer.daemon = True
    timer.start()


class _Callback(unohelper.Base, XCallback):
    def __init__(self, fn):
        self.fn = fn

    def notify(self, data):
        try:
            self.fn()
        except Exception:  # noqa: BLE001 - never raise into the office's event loop
            diag_log.exception("tex_toggle_notice")


def _on_main_thread(ctx, fn):
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(_Callback(fn), None)


class StatusNotice(unohelper.Base, XKeyHandler, XMouseClickHandler):
    """One status-bar line, removed on the main thread by the timer or by the next key press or click."""

    def __init__(self, ctx, indicator, controller):
        self.ctx, self.indicator, self.controller, self.closed = ctx, indicator, controller, False

    def watch(self):
        try:
            self.controller.addKeyHandler(self)
            self.controller.addMouseClickHandler(self)
        except Exception:  # noqa: BLE001 - a view without input interception: the timer still clears the line
            pass

    def close_later(self):
        if not self.closed:
            try:
                _on_main_thread(self.ctx, self.close)
            except Exception:  # noqa: BLE001 - office shutting down: nothing left to clear
                pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        for remove in ("removeKeyHandler", "removeMouseClickHandler"):
            try:
                getattr(self.controller, remove)(self)
            except Exception:  # noqa: BLE001 - view closed meanwhile
                pass
        try:
            self.indicator.end()
        except Exception:  # noqa: BLE001 - window closed meanwhile
            pass
        self.controller = self.indicator = None

    def keyPressed(self, event):
        self.close_later()
        return False

    def keyReleased(self, event):
        return False

    def mousePressed(self, event):
        self.close_later()
        return False

    def mouseReleased(self, event):
        return False

    def disposing(self, source):
        self.controller = None


def show(ctx, frame, text, timer=None):
    """Put `text` (one line) on the status bar of `frame`; the StatusNotice, or None when the frame has no status
    indicator (hidden documents)."""
    try:
        indicator = frame.createStatusIndicator()
        indicator.start(" ".join(text.split("\n")), 0)
    except Exception:  # noqa: BLE001 - the conversion is done either way; the line is only a report
        diag_log.exception("tex_toggle_notice", print_too=False)
        return None
    notice = StatusNotice(ctx, indicator, frame.getController())
    notice.watch()
    (timer or _daemon_timer)(NOTICE_SECONDS, notice.close_later)
    return notice
