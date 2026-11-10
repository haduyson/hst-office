# SPDX-License-Identifier: AGPL-3.0-only
"""Show-once logic for the welcome dialog plus the Jobs.xcu job (event onFirstVisibleTask).

Persistent flag: /org.hasontech.hstoffice.Welcome/Shown (boolean, per user; schema in welcome.xcs). It is
written as soon as the dialog is displayed, so a crash or kill never makes the dialog loop. The "do not show
again" tick is on by default; closing with it cleared writes Shown=false so the dialog appears again next start.
"""

import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .data_files import load_locale
from .welcome_dialog import Welcome
from . import diag_log

JOB_NAME = "org.hst.office.vi.WelcomeJob"
CONFIG_PATH = "/org.hasontech.hstoffice.Welcome"
DEFER_TURNS = 1  # event-loop passes to wait before the dialog opens
LOAD_POLL = 0.25  # seconds between checks while a document is still loading
LOAD_WAIT = 300  # seconds after which a modal start-up step runs even if a load never ends


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def is_shown(ctx):
    return bool(_access(ctx, False).getPropertyValue("Shown"))


def set_shown(ctx, value):
    node = _access(ctx, True)
    node.setPropertyValue("Shown", bool(value))
    node.commitChanges()


def show_welcome(ctx, medium, parent_peer=None, strings=None):
    """Open the dialog; marks the flag once displayed and clears it again if the user unticked "do not show again".

    The welcome dialog is introductory content: it is Vietnamese in every UI language (menus and features follow
    the UI language)."""
    strings = strings or load_locale("vi")
    dialog = Welcome(ctx, strings, medium, on_shown=lambda: _safe(set_shown, ctx, True))
    if not dialog.run(parent_peer):
        _safe(set_shown, ctx, False)


def _safe(fn, *args):
    try:
        fn(*args)
    except Exception:  # noqa: BLE001 - a failing config write must not break the office start
        diag_log.exception("welcome_job")


def loading(ctx):
    """True while a shown task frame of the desktop has no controller yet, i.e. a document is still being imported.

    A document opened from the file manager (double click, Open, Open with) starts the office with that file: the
    loader shows the document's frame BEFORE the import, to parent its dialogs, so onFirstVisibleTask fires mid-load,
    and the import reschedules the event loop for its progress bar. A modal dialog run from that nested loop holds the
    import under it: the window stays blank ("Load document") until the dialog is closed, and when the dialog is not
    noticed the document never appears. The controller is attached only when the import ends."""
    frames = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getFrames()
    for index in range(frames.getCount()):
        frame = frames.getByIndex(index)
        window = frame.getContainerWindow()
        # hidden loads (macros, conversions) never show a dialog parent, so they do not hold the prompts
        if frame.getController() is None and window is not None and window.isVisible():
            return True
    return False


class _Later(unohelper.Base, XCallback):
    """Runs `fn` on the office's main thread after `turns` further passes of the event loop, and only once no document
    is loading (checked every LOAD_POLL seconds, at most LOAD_WAIT seconds)."""

    def __init__(self, ctx, fn, turns, clock=None, timer=None):
        import time
        import threading
        self.ctx, self.fn, self.turns = ctx, fn, turns
        self.clock = clock or time.monotonic
        self.timer = timer or (lambda delay, action: threading.Timer(delay, action).start())
        self.deadline = self.clock() + LOAD_WAIT

    def notify(self, data):
        try:
            if self.turns > 0:
                self.turns -= 1
                _post(self.ctx, self)
            elif self.clock() < self.deadline and _safe_loading(self.ctx):
                # not from this (possibly nested) event loop: ask again shortly, from a timer thread
                self.timer(LOAD_POLL, lambda: _post(self.ctx, self))
            else:
                self.fn()
        except Exception:  # noqa: BLE001 - never raise into the office's event loop
            diag_log.exception("welcome_job")


def _safe_loading(ctx):
    try:
        return loading(ctx)
    except Exception:  # noqa: BLE001 - a broken check must not hold the start-up prompts forever
        traceback.print_exc()
        return False


def _post(ctx, callback):
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(callback, None)


def run_later(ctx, fn, turns=DEFER_TURNS):
    """Run fn() on the main thread after `turns` further passes of the event loop (not inside a start-up job) and
    after every document being opened has finished loading (see loading())."""
    _post(ctx, _Later(ctx, fn, turns))


def show_after_start_center(ctx, turns=DEFER_TURNS):
    """Show the welcome dialog once the event loop is back, not inside the job.

    onFirstVisibleTask fires while the Start Center frame is still being shown, before its content is built
    and painted; a modal dialog opened right there keeps the Start Center blank until it closes, so the
    office seems to load slowly after "Đóng". Posting the dialog to the main loop lets the Start Center
    finish first and appear behind the dialog."""
    run_later(ctx, lambda: show_welcome(ctx, "welcome"), turns)


class WelcomeJob(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return JOB_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.task.Job",)

    def execute(self, arguments):
        try:
            if not is_shown(self.ctx):
                show_after_start_center(self.ctx)
        except Exception:  # noqa: BLE001 - never block start-up
            diag_log.exception("welcome_job")
        return None
