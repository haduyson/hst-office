# SPDX-License-Identifier: AGPL-3.0-only
"""The one start-up dispatcher (Jobs.xcu, onFirstVisibleTask): at most ONE modal question per start.

Order (plan "Start-up prompts"): crash report question, macOS "move to Applications" (mac_app_location.offer_move_once),
welcome dialog, default-apps question, then the update notice. The first step that shows a modal dialog ends the
modal chain for this start; every later step waits for a later start, because each one keeps its own state until it
is shown (crash: the pending recovery state is re-read at the next OnStartApp only while Crashed stays set, so a skipped
crash question is NOT carried over, which is why it is first; welcome: Shown; default apps: Asked/LastAsked; update
outcome: its state file). The update check itself is not modal (an infobar) and always runs last.

Runs on the main thread after the Start Center has painted (welcome_job.run_later), never inside the job.
"""
import platform
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

JOB_NAME = "org.hst.office.vi.StartupPromptsJob"
ORDER = ("crash", "mac_move", "welcome", "default_apps", "update_outcome")


def run_chain(steps):
    """Run (name, step) in order until one step returns True (it showed a modal). Returns that name or None.

    A step that raises is logged and counts as "nothing shown", so one broken prompt never blocks the others."""
    for name, step in steps:
        try:
            if step():
                return name
        except Exception:  # noqa: BLE001 - never break start-up
            traceback.print_exc()
    return None


def _parent(ctx):
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    return frame.getContainerWindow() if frame is not None else None


def _crash(ctx):
    from . import error_report_crash
    return error_report_crash.ask(ctx) is not None


def offer_move_stub(ctx):
    """Same contract as mac_app_location.offer_move_once(ctx) -> bool: True when it asked; never raises; False off
    macOS. Used while that module is not in this build."""
    return False


def _mac_move(ctx):
    if platform.system() != "Darwin":
        return False
    try:
        from .mac_app_location import offer_move_once
    except ImportError:
        offer_move_once = offer_move_stub
    return bool(offer_move_once(ctx))


def _welcome(ctx):
    from . import welcome_job
    if welcome_job.is_shown(ctx):
        return False
    welcome_job.show_welcome(ctx, "welcome", _parent(ctx))
    return True


def _default_apps(ctx):
    from . import default_apps
    return default_apps.offer_at_startup(ctx, _parent(ctx))


def _update_outcome(ctx):
    from . import update_outcome
    return bool(update_outcome.show_pending(ctx))


def _update_check(ctx):
    from . import update_job
    update_job.automatic_check(ctx)


def steps_for(ctx):
    table = {"crash": _crash, "mac_move": _mac_move, "welcome": _welcome, "default_apps": _default_apps,
             "update_outcome": _update_outcome}
    return [(name, (lambda fn=table[name]: fn(ctx))) for name in ORDER]


def run(ctx, steps=None, after=None):
    """The whole start: the modal chain, then the non-modal update check. Returns the name of the modal shown."""
    shown = run_chain(steps if steps is not None else steps_for(ctx))
    try:
        (after or _update_check)(ctx)
    except Exception:  # noqa: BLE001 - never break start-up
        traceback.print_exc()
    return shown


class StartupPromptsJob(unohelper.Base, XServiceInfo, XJob):
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
            from .welcome_job import run_later
            run_later(self.ctx, lambda: run(self.ctx))
        except Exception:  # noqa: BLE001 - never block start-up
            traceback.print_exc()
        return None
