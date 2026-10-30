# SPDX-License-Identifier: AGPL-3.0-only
"""Show-once logic for the welcome dialog plus the Jobs.xcu job (event onFirstVisibleTask).

Persistent flag: /org.hasontech.hstoffice.Welcome/Shown (boolean, per user; schema in welcome.xcs). It is
written as soon as the dialog is displayed, so a crash or kill never makes the dialog loop. The "do not show
again" tick is on by default; closing with it cleared writes Shown=false so the dialog appears again next start.
"""
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .data_files import load_locale
from .welcome_dialog import Welcome

JOB_NAME = "org.hst.office.vi.WelcomeJob"
CONFIG_PATH = "/org.hasontech.hstoffice.Welcome"


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
                show_welcome(self.ctx, "welcome")
        except Exception:  # noqa: BLE001 - never block start-up
            traceback.print_exc()
        return None
