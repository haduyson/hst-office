# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST PDF started on its own (Windows shortcut, Linux launcher): a file dialog limited to PDF files.

Windows runs `soffice --nodefault service:org.hst.office.vi.PdfOpen`. Linux runs
`hst-office1.0 --nodefault "service:org.hst.office.vi.PdfOpen?begin" %U service:org.hst.office.vi.PdfOpen`, so the
one launcher also opens the files a file manager passes. The office handles the arguments of one command line in
order, each file loaded before the next argument, and creates this service for each "service:" argument:
  - trigger("begin") notes the open windows and documents;
  - trigger("") (the last argument) compares with that note (or with now, without "begin") on the main loop: when the
    command line opened something, nothing more; otherwise the PDF dialog, whose files open in HST PDF
    (HSTPdfOpenInViewer, as "Mở trong HST PDF").
Cancel opens nothing. When no window is left then, the office quits instead of waiting windowless: --nodefault kept the
Start Center away. Until the dialog has run, a terminate listener keeps the office from quitting under it. macOS has a
native launcher with its own panel (scripts/macos/hst-app-launcher.m) and never runs this.
"""
import unohelper
from com.sun.star.frame import XTerminateListener
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJobExecutor

from . import diag_log

SERVICE = "org.hst.office.vi.PdfOpen"
BEGIN = "begin"
VIEWER_FLAG = "HSTPdfOpenInViewer"
TEXTS = {"vi": {"title": "HST PDF — Mở tệp PDF", "filter": "Tệp PDF"},
         "en": {"title": "HST PDF — Open PDF file", "filter": "PDF files"}}
_noted = []  # the "begin" note of the command line being handled: [(windows, documents)]


def windows(desktop):
    """[(frame, controller)] of the desktop now."""
    frames = desktop.getFrames()
    return [(f, f.getController()) for f in (frames.getByIndex(i) for i in range(frames.getCount()))]


def documents(desktop):
    """The open documents (models), tabs of a window included."""
    found, items = [], desktop.getComponents().createEnumeration()
    while items.hasMoreElements():
        found.append(items.nextElement())
    return found


def state(desktop):
    return windows(desktop), documents(desktop)


def opened_since(before, now):
    """True when, from state `before` to `now`, a window appeared, a window got another document or a document was
    opened (UNO equality only)."""
    (old_windows, old_docs), (new_windows, new_docs) = before, now
    for frame, controller in new_windows:
        old = [c for f, c in old_windows if f == frame]
        if not old:
            return True
        if controller is not None and not (old[0] is not None and old[0] == controller):
            return True
    return any(not any(doc == known for known in old_docs) for doc in new_docs)


def choose(ctx, language):
    """File URLs picked in the office's file dialog (several allowed), [] on Cancel."""
    picker = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    picker.initialize((0,))  # FILEOPEN_SIMPLE
    try:
        text = TEXTS[language]
        name = "%s (*.pdf)" % text["filter"]
        picker.setTitle(text["title"])
        picker.appendFilter(name, "*.pdf;*.PDF")
        picker.setCurrentFilter(name)
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
    """Refuses to let the office quit while the dialog is still to come."""

    def queryTermination(self, event):
        from com.sun.star.frame import TerminationVetoException
        raise TerminationVetoException()

    def notifyTermination(self, event):
        pass

    def disposing(self, source):
        pass


def run(ctx, desktop, before, hold, choose_files=None, language=None):
    """The main-loop part: the dialog when the command line opened nothing; quit when no window is left."""
    try:
        if opened_since(before, state(desktop)):
            return "opened"
        if language is None:
            from .update_texts import ui_language
            language = ui_language(ctx)
        urls = (choose_files or choose)(ctx, language)
        if urls:
            open_in_viewer(desktop, urls)
            return "chosen"
        return "cancelled"
    finally:
        desktop.removeTerminateListener(hold)
        if desktop.getFrames().getCount() == 0:
            desktop.terminate()


def handle(ctx, desktop, argument, post):
    """trigger(): note the state on "begin"; otherwise post the dialog step (`post(fn)` runs fn on the main loop)."""
    if argument == BEGIN:
        _noted[:] = [state(desktop)]
        return
    before = _noted.pop() if _noted else state(desktop)
    hold = _HoldStart()
    desktop.addTerminateListener(hold)
    post(lambda: _guarded(ctx, desktop, before, hold))


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
            from .update_ui import on_main_thread
            desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            handle(self.ctx, desktop, argument, lambda fn: on_main_thread(self.ctx, fn))
        except Exception:  # noqa: BLE001 - never raise into the command-line dispatch
            diag_log.exception("pdf_open")


def _guarded(ctx, desktop, before, hold):
    try:
        run(ctx, desktop, before, hold)
    except Exception:  # noqa: BLE001 - logged; run() released the listener
        diag_log.exception("pdf_open")
