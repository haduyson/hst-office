# SPDX-License-Identifier: AGPL-3.0-only
"""Show-once logic for the welcome dialog plus the Jobs.xcu job (event onFirstVisibleTask).

Persistent flag: /org.hasontech.hstoffice.Welcome/Shown (boolean, per user; schema in welcome.xcs). It is
written as soon as the dialog is displayed, so a crash or kill never makes the dialog loop. The "do not show
again" tick is on by default; closing with it cleared writes Shown=false so the dialog appears again next start.
"""
import traceback

import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .data_files import load_locale
from .welcome_dialog import Welcome

JOB_NAME = "org.hst.office.vi.WelcomeJob"
CONFIG_PATH = "/org.hasontech.hstoffice.Welcome"
DEFER_TURNS = 1  # event-loop passes to wait before the dialog opens


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
        traceback.print_exc()


class _Later(unohelper.Base, XCallback):
    """Runs `fn` on the office's main thread after `turns` further passes of the event loop."""

    def __init__(self, ctx, fn, turns):
        self.ctx, self.fn, self.turns = ctx, fn, turns

    def notify(self, data):
        try:
            if self.turns > 0:
                self.turns -= 1
                _post(self.ctx, self)
            else:
                self.fn()
        except Exception:  # noqa: BLE001 - never raise into the office's event loop
            traceback.print_exc()


def _post(ctx, callback):
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(callback, None)


def show_after_start_center(ctx, turns=DEFER_TURNS):
    """Show the welcome dialog once the event loop is back, not inside the job.

    onFirstVisibleTask fires while the Start Center frame is still being shown, before its content is built
    and painted; a modal dialog opened right there keeps the Start Center blank until it closes, so the
    office seems to load slowly after "Đóng". Posting the dialog to the main loop lets the Start Center
    finish first and appear behind the dialog."""
    _post(ctx, _Later(ctx, lambda: show_welcome(ctx, "welcome"), turns))


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
            traceback.print_exc()
        return None
