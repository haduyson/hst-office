# SPDX-License-Identifier: AGPL-3.0-only
"""The one start-up dispatcher (Jobs.xcu, onFirstVisibleTask): at most ONE modal question per start.

Order: macOS "move to Applications" (mac_app_location.offer_move_once), the notice that the settings file was repaired
after a power cut (profile_notice: rare, and the user must know their settings changed), crash report question, welcome dialog,
default-apps question, then the update notice. The move comes first (coordinator 2026-11-07): an app run from the
.dmg or a translocated path would register the wrong copy as the default app and every other question is wasted until
it moves; it returns False off macOS and once the app is in /Applications. The first step that shows a modal dialog
ends the modal chain for this start; every later step waits for a later start, because each one keeps its own state
until it is shown (welcome: Shown; default apps: Asked/LastAsked; update outcome: its state file). A crash question
skipped behind the move question is not carried over: the recovery state is read once per start. The update check
itself is not modal (an infobar) and always runs last. Before the questions, an installed macOS copy puts its app
launchers in /Applications or refreshes them (mac_app_launchers_ui.sync_at_startup, no dialog); the one-time notice
about them ("mac_launchers") comes after the welcome dialog, so a first start still opens with the welcome.

Runs on the main thread after the Start Center has painted and after a document opened at start has loaded
(welcome_job.run_later), never inside the job and never inside a document import. When the user has started working
by then (startup_activity: documents opened or closed, a document modified), only the crash question still runs; the
others wait for a later start, so no question lands on the user's work and holds closing a tab or quitting. When other
software started the office (automation_start: headless, invisible, --accept, a conversion), the welcome dialog, the
notice about the macOS launchers and the default-apps question wait for a start by a person.
"""
import platform

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob
from . import diag_log

JOB_NAME = "org.hst.office.vi.StartupPromptsJob"
ORDER = ("mac_move", "profile_repaired", "crash", "welcome", "mac_launchers", "default_apps", "update_outcome")
# skipped when other software started the office (automation_start)
FOR_PERSON = ("welcome", "mac_launchers", "default_apps")


def run_chain(steps):
    """Run (name, step) in order until one step returns True (it showed a modal). Returns that name or None.

    A step that raises is logged and counts as "nothing shown", so one broken prompt never blocks the others."""
    for name, step in steps:
        try:
            if step():
                return name
        except Exception:  # noqa: BLE001 - never break start-up
            diag_log.exception("startup_prompts")
    return None


def _parent(ctx):
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    return frame.getContainerWindow() if frame is not None else None


def _crash(ctx):
    from . import error_report_crash
    return error_report_crash.ask(ctx) is not None


def _profile_repaired(ctx):
    from . import profile_notice
    return profile_notice.show_once(ctx, _parent(ctx))


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


def _mac_launchers(ctx):
    from . import mac_app_launchers_ui
    return mac_app_launchers_ui.notice_once(ctx)


def _sync_mac_launchers(ctx):
    if platform.system() == "Darwin":
        from . import mac_app_launchers_ui
        mac_app_launchers_ui.sync_at_startup(ctx)


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
    table = {"crash": _crash, "mac_move": _mac_move, "profile_repaired": _profile_repaired, "welcome": _welcome, "default_apps": _default_apps,
             "mac_launchers": _mac_launchers, "update_outcome": _update_outcome}
    return [(name, (lambda fn=table[name]: fn(ctx))) for name in ORDER]


def only_after_work(steps):
    """The steps that still run once the user has started working: the crash question (read once per start). The
    others keep their state until shown and wait for a calmer start (startup_activity)."""
    return [(name, step) for name, step in steps if name == "crash"]


def for_automation(steps):
    """The steps without those meant for a person at the screen (FOR_PERSON), for a start by other software."""
    return [(name, step) for name, step in steps if name not in FOR_PERSON]


def _safe_automated():
    try:
        from .automation_start import started_by_automation
        return started_by_automation()
    except Exception:  # noqa: BLE001 - a broken check keeps the questions as before
        diag_log.exception("startup_prompts")
        return False


def run(ctx, steps=None, after=None, before=None, prepare=None):
    """The whole start: the macOS launchers, the modal chain, then the non-modal update check. Returns the name of the
    modal shown.

    before: startup_activity.snapshot() taken when the questions were scheduled; when the user has started working
    since, only the crash question may still open a modal."""
    try:
        (prepare or _sync_mac_launchers)(ctx)
    except Exception:  # noqa: BLE001 - never break start-up
        diag_log.exception("startup_prompts")
    steps = steps if steps is not None else steps_for(ctx)
    if before is not None and _started_working(ctx, before):
        steps = only_after_work(steps)
    shown = run_chain(steps)
    try:
        (after or _update_check)(ctx)
    except Exception:  # noqa: BLE001 - never break start-up
        diag_log.exception("startup_prompts")
    return shown


def _safe_snapshot(ctx):
    try:
        from .startup_activity import snapshot
        return snapshot(ctx)
    except Exception:  # noqa: BLE001 - without a snapshot the questions run as before
        diag_log.exception("startup_prompts")
        return None


def _started_working(ctx, before):
    try:
        from .startup_activity import started_working
        return started_working(ctx, before)
    except Exception:  # noqa: BLE001 - a broken check must not hide the questions for good
        diag_log.exception("startup_prompts")
        return False


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
            before = _safe_snapshot(self.ctx)
            if _safe_automated():
                steps = for_automation(steps_for(self.ctx))
                run_later(self.ctx, lambda: run(self.ctx, steps=steps, before=before))
            else:
                run_later(self.ctx, lambda: run(self.ctx, before=before))
        except Exception:  # noqa: BLE001 - never block start-up
            diag_log.exception("startup_prompts")
        return None
