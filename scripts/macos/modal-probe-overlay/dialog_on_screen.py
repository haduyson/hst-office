# SPDX-License-Identifier: AGPL-3.0-only
"""Keeps the extension's modal dialogs (dialogs.Dialog.execute) reachable: shown parent, centred, in front, logged.

A modal dialog blocks the input of every document window while its modal loop runs. When its own window is not on
screen, the office looks frozen and only Force Quit ends it: user report on HST Office 1.0.2 for macOS (HST >
"Văn bản hành chính" run from a Sheets tab opened a new Writer tab and the ND 30 wizard inside the same menu command,
while the tab group was still switching tabs). Here:
- parent(): the window a dialog is attached to must be shown; a hidden one (a parked document tab, a frame that is
  not shown yet) is replaced by the shown window of the desktop's current frame, else the active top window.
- centre(): the dialog is centred over that parent (a code-built dialog otherwise sits at the parent's top left
  corner, or at the screen corner when the parent has no position yet).
- keep_in_front(): from inside the modal loop, the dialog is brought to the front (XTopWindow.toFront) a few times
  shortly after it opened, after the tab group has finished its own window work, and again whenever its parent
  window is hidden while it runs (macOS orders a child window out with its parent: a tab parked behind a new tab
  took its running dialog off screen, probe run 44842914015).
- watch_new_documents(): macOS only. A document opened while the dialog runs (the "+" menu, File > New, Finder, a
  launcher) gets a window of its own; when the parent is in native full screen, that window joins the parent's native
  tab group and is selected, which hides the parent window and its dialog, unknown to vcl (no windowHidden; probe run
  44922182163). The parent window is brought to the front again (selects its tab), then the dialog; once the dialog
  has ended, the newest such document comes to the front.
- log_open(): one local diagnostics line per modal dialog (title, command that opened it, parent kind).
"""
import sys
import threading

import unohelper
from com.sun.star.awt import XCallback, XWindowListener
from com.sun.star.document import XDocumentEventListener

from . import diag_log

FRONT_DELAYS = (0.3, 1.0, 2.5)  # seconds after the modal loop started at which the dialog is brought to the front
_ORIGIN = threading.local()


def set_origin(command):
    """Remember the command (e.g. "Nd30Wizard") whose dialogs follow on this thread; None to clear it."""
    _ORIGIN.command = command


def origin():
    return getattr(_ORIGIN, "command", None)


def _shown(window):
    try:
        return window is not None and bool(window.isVisible())
    except Exception:  # noqa: BLE001 - a disposed window counts as not shown
        return False


def parent(ctx, requested):
    """(window, kind): `requested` when shown, else a shown fallback; kind says which one was taken (for the log)."""
    if _shown(requested):
        return requested, "requested"
    smgr = ctx.ServiceManager
    try:
        frame = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
        window = frame.getContainerWindow() if frame is not None else None
        if _shown(window):
            return window, "current-frame"
    except Exception:  # noqa: BLE001 - no desktop frame: try the toolkit
        pass
    try:
        window = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).getActiveTopWindow()
        if _shown(window):
            return window, "active-window"
    except Exception:  # noqa: BLE001
        pass
    return None, "none" if requested is None else "none-requested-hidden"


def centre(dialog_window, parent_window):
    """Centre the created dialog over its parent (positions of a dialog are relative to its parent window)."""
    if parent_window is None:
        return
    try:
        outer, own = parent_window.getPosSize(), dialog_window.getPosSize()
        x = max(0, (outer.Width - own.Width) // 2)
        y = max(0, (outer.Height - own.Height) // 2)
        dialog_window.setPosSize(x, y, 0, 0, 3)  # com.sun.star.awt.PosSize.POS
    except Exception:  # noqa: BLE001 - unknown geometry: keep the toolkit's position
        pass


class _Front(unohelper.Base, XCallback):
    """Runs on the main thread (AsyncCallback, so from inside the modal loop): brings the dialog to the front."""

    def __init__(self, dialog, is_open):
        self.dialog, self.is_open = dialog, is_open

    def notify(self, data):
        try:
            if self.is_open():
                self.dialog.toFront()
        except Exception:  # noqa: BLE001 - the dialog ended meanwhile
            pass


def is_front_candidate(ctx, dialog):
    """True while `dialog` is the innermost open HST dialog and no other dialog is active (a message box or file
    picker it opened must never go behind it): the active top window is the dialog itself, a document window or none."""
    from . import dialog_registry
    if not dialog_registry.OPEN or dialog_registry.OPEN[-1] is not dialog:
        return False
    try:
        smgr = ctx.ServiceManager
        active = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).getActiveTopWindow()
        if active is None or active == dialog.getPeer():
            return True
        frames = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getFrames()
        return any(active == frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount()))
    except Exception:  # noqa: BLE001 - unknown state: leave the windows alone
        return False


def keep_in_front(ctx, dialog, is_open, delays=FRONT_DELAYS, timer=None):
    """Bring `dialog` to the front at each delay while is_open() (posted from timer threads to the main thread)."""
    def post():
        try:
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(
                _Front(dialog, is_open), None)
        except Exception:  # noqa: BLE001 - office shutting down
            pass
    start = timer or (lambda delay, action: _daemon_timer(delay, action))
    for delay in delays:
        start(delay, post)


class _ParentHidden(unohelper.Base, XWindowListener):
    """The parent window of a running dialog was hidden (e.g. its document tab parked): bring the dialog back."""

    def __init__(self, on_hidden):
        self.on_hidden = on_hidden

    def windowHidden(self, event):  # noqa: N802 - UNO method name
        self.on_hidden()

    def windowShown(self, event):  # noqa: N802
        pass

    def windowResized(self, event):  # noqa: N802
        pass

    def windowMoved(self, event):  # noqa: N802
        pass

    def disposing(self, event):
        pass


def watch_parent(ctx, parent_window, dialog, is_open, timer=None):
    """While the dialog runs, a hidden parent brings it to the front again. Returns the function that stops watching."""
    if parent_window is None:
        return lambda: None
    listener = _ParentHidden(lambda: keep_in_front(ctx, dialog, is_open, timer=timer))
    try:
        parent_window.addWindowListener(listener)
    except Exception:  # noqa: BLE001 - a window without listeners: nothing to watch
        return lambda: None

    def stop():
        try:
            parent_window.removeWindowListener(listener)
        except Exception:  # noqa: BLE001 - parent already disposed
            pass
    return stop


NEW_DOCUMENT_EVENTS = ("OnNew", "OnLoad", "OnViewCreated")


class _ParentAndDialogToFront(unohelper.Base, XCallback):
    """Main thread: the parent window to the front (macOS: selects it again in its native tab group), then the dialog."""

    def __init__(self, parent_window, dialog, is_open):
        self.parent_window, self.dialog, self.is_open = parent_window, dialog, is_open

    def notify(self, data):
        try:
            if self.is_open():
                self.parent_window.toFront()
                self.dialog.toFront()
        except Exception:  # noqa: BLE001 - the dialog or its parent ended meanwhile
            pass


class _DocumentToFront(unohelper.Base, XCallback):
    """Main thread, after the dialog has ended: the window of a document opened meanwhile to the front, focused."""

    def __init__(self, window):
        self.window = window

    def notify(self, data):
        try:
            self.window.toFront()
            self.window.setFocus()
        except Exception:  # noqa: BLE001 - the document was closed meanwhile
            pass


class _NewDocument(unohelper.Base, XDocumentEventListener):
    """A document opened or got a view while a dialog runs."""

    def __init__(self, on_new):
        self.on_new = on_new

    def documentEventOccured(self, event):  # noqa: N802 - UNO method name (sic)
        if getattr(event, "EventName", "") in NEW_DOCUMENT_EVENTS:
            self.on_new(event)

    def disposing(self, event):
        pass


def _document_window(event):
    try:
        return event.Source.getCurrentController().getFrame().getContainerWindow()
    except Exception:  # noqa: BLE001 - no view yet (OnNew/OnLoad before OnViewCreated) or closed
        return None


def watch_new_documents(ctx, parent_window, dialog, is_open, timer=None, platform=None):
    """macOS only (elsewhere a no-op): while the dialog runs, a document opened meanwhile brings the parent window and
    the dialog back to the front; the returned stop function ends watching and, if such a document opened, brings
    its window to the front after the dialog has closed."""
    if (platform or sys.platform) != "darwin" or parent_window is None:
        return lambda: None
    start = timer or _daemon_timer
    opened = []

    def on_new(event):
        window = _document_window(event)
        if window is not None and window != parent_window:
            if window in opened:
                opened.remove(window)
            opened.append(window)
        for delay in FRONT_DELAYS:
            start(delay, lambda: _post(ctx, _ParentAndDialogToFront(parent_window, dialog, is_open)))

    listener = _NewDocument(on_new)
    try:
        broadcaster = ctx.getValueByName("/singletons/com.sun.star.frame.theGlobalEventBroadcaster")
        broadcaster.addDocumentEventListener(listener)
    except Exception:  # noqa: BLE001 - no broadcaster: nothing to watch
        return lambda: None

    def stop():
        try:
            broadcaster.removeDocumentEventListener(listener)
        except Exception:  # noqa: BLE001 - office shutting down
            pass
        if opened:
            latest = opened[-1]
            start(FRONT_DELAYS[0], lambda: _post(ctx, _DocumentToFront(latest)))
    return stop


def _daemon_timer(delay, action):
    t = threading.Timer(delay, action)
    t.daemon = True
    t.start()


def log_open(title, kind):
    """One line in the local diagnostics log before a modal dialog runs (no document text: title and command only)."""
    diag_log.info("dialog", "modal %r from %s, parent %s" % (title, origin() or "-", kind))


class _WhenSettled(unohelper.Base, XCallback):
    """Runs `fn` on the main thread once `frame` is shown and no longer locked by its loader (polled from timers)."""

    def __init__(self, ctx, frame, fn, tries, delay, timer):
        self.ctx, self.frame, self.fn, self.tries, self.delay, self.timer = ctx, frame, fn, tries, delay, timer

    def notify(self, data):
        try:
            settled = _shown(self.frame.getContainerWindow()) and not (
                hasattr(self.frame, "isActionLocked") and self.frame.isActionLocked())
        except Exception:  # noqa: BLE001 - frame closed meanwhile: run anyway, the command reports what is missing
            settled = True
        if settled or self.tries <= 0:
            self.fn()
            return
        self.tries -= 1
        self.timer(self.delay, lambda: _post(self.ctx, self))


def _post(ctx, callback):
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(callback, None)


def run_when_settled(ctx, frame, fn, tries=20, delay=0.25, timer=None):
    """Run fn() from the main loop, not inside the command that opened `frame`: first after `delay` seconds (the tab
    group shows the new tab and parks the previous one from its own idle handler), then until the frame is shown and
    loaded, at most `tries` more polls."""
    timer = timer or _daemon_timer
    timer(delay, lambda: _post(ctx, _WhenSettled(ctx, frame, fn, tries, delay, timer)))
