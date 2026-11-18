# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF started on its own (Windows shortcut, Linux launcher): a file dialog limited to PDF files.

The launchers run `soffice --nodefault "service:org.hst.office.vi.PdfOpen" [files]`. The office creates this
service for the "service:" request and calls trigger(); "Open with HST PDF" passes the files after it in the same
request. trigger() only notes the open windows and posts the rest to the main loop, which runs once the whole request
has been handled:
  - the request opened files (a new window or document since trigger()): nothing more;
  - otherwise the PDF dialog; the chosen files open in HST PDF (HSTPdfOpenInViewer, as "Mở trong HST PDF").
Cancel opens nothing. When no window is left then, the office quits, as it does after a command line that opened
nothing: no Start Center (--nodefault). Between trigger() and the dialog a terminate listener keeps the office from
quitting first, since it quits at once when a start-up request leaves no window. macOS has a native launcher with its
own panel (scripts/macos/hst-app-launcher.m) and never runs this.
"""
import unohelper
from com.sun.star.frame import XTerminateListener
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJobExecutor

from . import diag_log

SERVICE = "org.hst.office.vi.PdfOpen"
VIEWER_FLAG = "HSTPdfOpenInViewer"
TEXTS = {"vi": {"title": "HST PDF — Mở tệp PDF", "filter": "Tệp PDF"},
         "en": {"title": "HST PDF — Open PDF file", "filter": "PDF files"}}


def windows(desktop):
    """[(frame, controller)] of the desktop now."""
    frames = desktop.getFrames()
    return [(f, f.getController()) for f in (frames.getByIndex(i) for i in range(frames.getCount()))]


def opened_since(before, now):
    """True when a window appeared or a window got another document since `before` (pure apart from UNO equality)."""
    for frame, controller in now:
        old = [c for f, c in before if f == frame]
        if not old:
            return True
        if controller is not None and not (old[0] is not None and old[0] == controller):
            return True
    return False


def choose(ctx, language):
    """File URLs picked in the office's file dialog (several allowed), [] on Cancel."""
    picker = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    picker.initialize((0,))  # FILEOPEN_SIMPLE
    try:
        text = TEXTS[language]
        picker.setTitle(text["title"])
        picker.appendFilter("%s (*.pdf)" % text["filter"], "*.pdf;*.PDF")
        picker.setCurrentFilter("%s (*.pdf)" % text["filter"])
        picker.setMultiSelectionMode(True)
        if picker.execute() != 1:
            return []
        return list(picker.getSelectedFiles())
    finally:
        picker.dispose()


def open_in_viewer(desktop, urls):
    import uno
    force = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    force.Name, force.Value = VIEWER_FLAG, True
    for url in urls:
        desktop.loadComponentFromURL(url, "_default", 0, (force,))


class _HoldStart(unohelper.Base, XTerminateListener):
    """Refuses the start-up "nothing opened, quit" until the dialog has run."""

    def queryTermination(self, event):
        from com.sun.star.frame import TerminationVetoException
        raise TerminationVetoException()

    def notifyTermination(self, event):
        pass

    def disposing(self, source):
        pass


def run(ctx, desktop, before, hold, choose_files=choose, language=None):
    """The posted part: dialog when the request opened nothing; quit when nothing is open afterwards."""
    try:
        if opened_since(before, windows(desktop)):
            return "opened"
        if language is None:
            from .update_texts import ui_language
            language = ui_language(ctx)
        urls = choose_files(ctx, language)
        if urls:
            open_in_viewer(desktop, urls)
            return "chosen"
        return "cancelled"
    finally:
        desktop.removeTerminateListener(hold)
        if desktop.getFrames().getCount() == 0:
            desktop.terminate()


class PdfOpenJob(unohelper.Base, XServiceInfo, XJobExecutor):
    def __init__(self, ctx, *args):
        self.ctx = ctx

    def getImplementationName(self):
        return SERVICE

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (SERVICE,)

    def trigger(self, argument):
        try:
            desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            before, hold = windows(desktop), _HoldStart()
            desktop.addTerminateListener(hold)
            from .update_ui import on_main_thread
            on_main_thread(self.ctx, lambda: _guarded(self.ctx, desktop, before, hold))
        except Exception:  # noqa: BLE001 - never raise into the dispatch
            diag_log.exception("pdf_open")


def _guarded(ctx, desktop, before, hold):
    try:
        run(ctx, desktop, before, hold)
    except Exception:  # noqa: BLE001 - logged; the listener is removed in run()
        diag_log.exception("pdf_open")
