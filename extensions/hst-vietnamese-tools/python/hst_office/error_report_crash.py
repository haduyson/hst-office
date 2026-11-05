# SPDX-License-Identifier: AGPL-3.0-only
"""After an abnormal exit, ask once at the next start whether to send a crash report (Jobs.xcu, two events).

The signal is the office's own recovery state (/org.openoffice.Office.Recovery), the same test the office uses to
decide on document recovery (desktop/source/app/app.cxx impl_checkRecoveryState):
  * RecoveryInfo/Crashed: set by the emergency save after a crash;
  * RecoveryList not empty while RecoveryInfo/SessionData is false: documents were open when the office ended without
    closing them (killed, power loss, a crash before the emergency save).
No crash handler of its own. The state is read at OnStartApp, before document recovery runs and resets it; the
question is asked after onFirstVisibleTask, i.e. after the recovery dialog has closed and the recovered documents or
the Start Center are shown, so both never compete. Crashed is then cleared, as recovery itself does, so the same exit
is asked about once; "Không hỏi lại" stores /org.hasontech.hstoffice.ErrorReport/AskAfterCrash = false.

The crash facts are what the office knows: which signal, how many documents were open and in which apps. Never
their names or locations.
"""
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .error_report_info import app_of_module
from .error_report_texts import TEXT

JOB_NAME = "org.hst.office.vi.CrashReportJob"
RECOVERY = "/org.openoffice.Office.Recovery"
SETTINGS = "/org.hasontech.hstoffice.ErrorReport"
STATE = {"pending": None}


def _node(ctx, path, writable=False):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def _write(ctx, path, name, value):
    node = _node(ctx, path, True)
    node.setPropertyValue(name, value)
    node.commitChanges()


def recovery_state(ctx):
    """{"crashed", "session", "modules"}: the office's recovery flags and the module of each listed document."""
    info = _node(ctx, RECOVERY + "/RecoveryInfo")
    listed = _node(ctx, RECOVERY + "/RecoveryList")
    modules = []
    for name in listed.getElementNames():
        try:
            modules.append(listed.getByName(name).getPropertyValue("Module"))
        except Exception:  # noqa: BLE001 - an entry without a module still counts
            modules.append("")
    return {"crashed": bool(info.getPropertyValue("Crashed")), "session": bool(info.getPropertyValue("SessionData")),
            "modules": modules}


def abnormal(state):
    """The office's own test: crashed, or recovery data that is not a saved session."""
    return state["crashed"] or (bool(state["modules"]) and not state["session"])


def crash_facts(state):
    """(diagnostics.crash text, app) from the recovery state; the app is known when all open documents share it."""
    apps = sorted({app_of_module(module) for module in state["modules"]})
    lines = ["Previous session: ended abnormally (detected at the next start)",
             "Emergency save ran: %s" % ("yes" if state["crashed"] else "no"),
             "Documents open at exit: %d%s" % (len(state["modules"]), (" (%s)" % ", ".join(apps)) if apps else ""),
             "Document recovery offered: %s" % ("yes" if state["modules"] and not state["session"] else "no")]
    return "\n".join(lines), apps[0] if len(apps) == 1 else "unknown"


def ask_enabled(ctx):
    try:
        return bool(_node(ctx, SETTINGS).getPropertyValue("AskAfterCrash"))
    except Exception:  # noqa: BLE001 - schema missing: behave like the default
        return True


def capture(ctx):
    """OnStartApp: remember an abnormal previous exit before recovery runs."""
    state = recovery_state(ctx)
    if abnormal(state) and ask_enabled(ctx):
        STATE["pending"] = state


def ask(ctx, frame=None, show=None, open_report=None):
    """The question; returns "send", "no" or "never". `show`/`open_report` are replaced by tests."""
    state, STATE["pending"] = STATE["pending"], None
    if state is None:
        return None
    if state["crashed"]:
        try:
            _write(ctx, RECOVERY + "/RecoveryInfo", "Crashed", False)  # asked once per exit
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    if frame is None:
        frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    answer = (show or _question)(ctx, frame.getContainerWindow() if frame is not None else None)
    if answer == "never":
        _write(ctx, SETTINGS, "AskAfterCrash", False)
    elif answer == "send":
        text, app = crash_facts(state)
        if open_report is None:
            from .error_report_dialog import run as open_report
        open_report(ctx, frame, "crash", text, app)
    return answer


def _question(ctx, parent_peer):
    """Gửi… / Không / Không hỏi lại; Không has the focus, Enter and Esc mean Không."""
    from .dialogs import Dialog, palette
    dialog = Dialog(ctx, TEXT["crash_title"], 280, 62)
    dialog.label("question", TEXT["crash_question"], 8, 8, 264, 18, wrap=True)
    note = dialog.label("note", TEXT["crash_note"], 8, 26, 264, 10)
    note.TextColor = palette(ctx)["muted"]
    chosen = ["no"]

    def pick(answer):
        chosen[0] = answer
        dialog.end(1)
    # inserted in tab order: the first control, Không, gets the focus
    dialog.button("no", TEXT["crash_no"], 280 - 8 - 50, 42, 50, kind=2, default=True)
    dialog.button("send", TEXT["crash_send"], 280 - 8 - 50 - 4 - 50, 42, 50, callback=lambda: pick("send"))
    dialog.button("never", TEXT["crash_never"], 8, 42, 70, callback=lambda: pick("never"))
    dialog.execute(parent_peer)
    return chosen[0]


def _event(arguments):
    for argument in arguments or ():
        if argument.Name == "Environment":
            for item in argument.Value:
                if item.Name == "EventName":
                    return item.Value
    return ""


class CrashReportJob(unohelper.Base, XServiceInfo, XJob):
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
            event = _event(arguments)
            if event == "OnStartApp":
                capture(self.ctx)
            elif event == "onFirstVisibleTask" and STATE["pending"] is not None:
                from .welcome_job import run_later
                run_later(self.ctx, lambda: ask(self.ctx))
        except Exception:  # noqa: BLE001 - never block or break start-up
            traceback.print_exc()
        return None
