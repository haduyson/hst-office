# SPDX-License-Identifier: AGPL-3.0-only
"""A modal HST dialog must never run off screen (macOS freeze report, HST Office 1.0.2).

HST > "Văn bản hành chính" from a Sheets tab opened a new Writer tab and the ND 30 wizard inside the same menu command.
On macOS a dialog is a child window of its parent: when the tab group parked that parent tab (another tab opened in the
window), the running wizard went off screen with it while it still held the office modal (probe run 44842914015).
Covered here without an office (UNO modules stubbed, windows and frames are fakes):
- the dialog gets a shown parent (a hidden requested parent falls back to the shown current frame / active window),
  is centred over it, logged, and brought to the front shortly after it opened and whenever its parent is hidden;
- never in front of a dialog it opened itself (only the innermost HST dialog, never over another active dialog);
- dispatch runs a command that first had to open a new document only once that document's tab is shown and loaded;
- macOS only: a document opened while the dialog runs over a parent in native full screen shows in a Space of its
  own, so the dialog moves onto that document's window (probe run 44924218348); a plain window keeps the dialog
  where it is, and on Windows and Linux nothing is watched.
"""
import importlib.abc
import importlib.machinery
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    __path__ = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


class _UnoStubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if name in ("uno", "unohelper") or name == "com" or name.startswith("com."):
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        pass


_FINDER = _UnoStubs()
sys.meta_path.insert(0, _FINDER)
for _name, _module in list(sys.modules.items()):
    if (_name == "com" or _name.startswith("com.")) and not hasattr(_module, "__path__"):
        _module.__path__ = []
from hst_office import dialog_on_screen, dialog_registry, dialogs, dispatch  # noqa: E402
from hst_office import actions  # noqa: E402,F401 - dispatch imports it on first use; it needs the stubs too

sys.meta_path.remove(_FINDER)


class Rect:
    def __init__(self, x, y, w, h):
        self.X, self.Y, self.Width, self.Height = x, y, w, h


class Window:
    def __init__(self, visible=True, rect=(0, 0, 1000, 800)):
        self.visible, self.rect, self.listeners, self.moved_to = visible, Rect(*rect), [], None

    def isVisible(self):  # noqa: N802 - UNO method names
        return self.visible

    def getPosSize(self):  # noqa: N802
        return self.rect

    def setPosSize(self, x, y, w, h, flags):  # noqa: N802
        self.moved_to = (x, y, flags)

    def addWindowListener(self, listener):  # noqa: N802
        self.listeners.append(listener)

    def removeWindowListener(self, listener):  # noqa: N802
        self.listeners.remove(listener)

    def hide(self):
        self.visible = False
        for listener in list(self.listeners):
            listener.windowHidden(None)


class Frame:
    def __init__(self, window, locked=False, model=None):
        self.window, self.locked, self.model = window, locked, model

    def getContainerWindow(self):  # noqa: N802
        return self.window

    def isActionLocked(self):  # noqa: N802
        return self.locked

    def getController(self):  # noqa: N802
        return type("Controller", (), {"getModel": lambda _self: self.model})()


class Frames:
    def __init__(self, frames):
        self.frames = frames

    def getCount(self):  # noqa: N802
        return len(self.frames)

    def getByIndex(self, index):  # noqa: N802
        return self.frames[index]


class Office:
    """ctx and ServiceManager in one: Desktop, Toolkit and AsyncCallback fakes (callbacks run when pump() is called)."""

    def __init__(self, current=None, active=None, frames=()):
        self.current, self.active, self.all_frames, self.queue = current, active, list(frames), []
        self.ServiceManager = self

    def createInstanceWithContext(self, name, ctx):  # noqa: N802
        office = self

        class Service:
            def getCurrentFrame(self):  # noqa: N802
                return office.current

            def getFrames(self):  # noqa: N802
                return Frames(office.all_frames)

            def getActiveTopWindow(self):  # noqa: N802
                return office.active

            def addCallback(self, callback, data):  # noqa: N802
                office.queue.append(callback)
        return Service()

    def pump(self):
        while self.queue:
            self.queue.pop(0).notify(None)


class Timers:
    """Collects timer actions; fire() runs them like the timer threads would."""

    def __init__(self):
        self.pending = []

    def __call__(self, delay, action):
        self.pending.append((delay, action))

    def fire(self):
        pending, self.pending = self.pending, []
        for _delay, action in pending:
            action()


class UnoDialog:
    def __init__(self):
        self.peer, self.fronted, self.parent_used, self.executed = Window(), 0, "unset", False

    def getPeer(self):  # noqa: N802
        return self.peer

    def toFront(self):  # noqa: N802
        self.fronted += 1

    def getPosSize(self):  # noqa: N802
        return Rect(0, 0, 600, 400)

    def setPosSize(self, x, y, w, h, flags):  # noqa: N802
        self.moved_to = (x, y, flags)


class ParentTests(unittest.TestCase):
    def test_a_shown_requested_parent_is_kept(self):
        requested = Window(True)
        self.assertEqual(dialog_on_screen.parent(Office(), requested), (requested, "requested"))

    def test_a_hidden_requested_parent_falls_back_to_the_shown_current_frame(self):
        shown = Window(True)
        office = Office(current=Frame(shown))
        self.assertEqual(dialog_on_screen.parent(office, Window(False)), (shown, "current-frame"))

    def test_then_the_active_top_window_then_nothing(self):
        active = Window(True)
        self.assertEqual(dialog_on_screen.parent(Office(current=Frame(Window(False)), active=active), Window(False)),
                         (active, "active-window"))
        self.assertEqual(dialog_on_screen.parent(Office(), None), (None, "none"))
        self.assertEqual(dialog_on_screen.parent(Office(), Window(False)), (None, "none-requested-hidden"))

    def test_centred_over_the_parent_never_above_or_left_of_it(self):
        dialog = UnoDialog()
        dialog_on_screen.centre(dialog, Window(True, (50, 60, 1000, 800)))
        self.assertEqual(dialog.moved_to, (200, 200, 3))  # relative to the parent; 3 = PosSize.POS
        dialog_on_screen.centre(dialog, Window(True, (0, 0, 500, 300)))
        self.assertEqual(dialog.moved_to, (0, 0, 3))


class FrontTests(unittest.TestCase):
    def setUp(self):
        self.dialog = UnoDialog()
        dialog_registry.OPEN.append(self.dialog)
        self.addCleanup(dialog_registry.OPEN.remove, self.dialog)

    def test_brought_to_front_after_it_opened_while_it_runs(self):
        office, timers = Office(), Timers()
        dialog_on_screen.keep_in_front(office, self.dialog, lambda: True, delays=(0.3, 1.0), timer=timers)
        self.assertEqual([d for d, _ in timers.pending], [0.3, 1.0])
        timers.fire()
        office.pump()
        self.assertEqual(self.dialog.fronted, 2)

    def test_not_after_it_ended(self):
        office, timers = Office(), Timers()
        dialog_on_screen.keep_in_front(office, self.dialog, lambda: False, delays=(0.3,), timer=timers)
        timers.fire()
        office.pump()
        self.assertEqual(self.dialog.fronted, 0)

    def test_a_hidden_parent_brings_the_running_dialog_back_and_stops_after_execute(self):
        office, timers, parent = Office(), Timers(), Window(True)
        stop = dialog_on_screen.watch_parent(office, parent, self.dialog, lambda: True, timer=timers)
        parent.hide()  # the tab group parks the tab that owns the dialog
        timers.fire()
        office.pump()
        self.assertEqual(self.dialog.fronted, len(dialog_on_screen.FRONT_DELAYS))
        stop()
        self.assertEqual(parent.listeners, [])

    def test_only_the_innermost_dialog_and_never_over_another_dialog(self):
        document = Window(True)
        office = Office(active=document, frames=[Frame(document)])
        self.assertTrue(dialog_on_screen.is_front_candidate(office, self.dialog))  # a document window is active
        office.active = self.dialog.getPeer()
        self.assertTrue(dialog_on_screen.is_front_candidate(office, self.dialog))
        office.active = Window(True)  # a message box or file picker the dialog opened
        self.assertFalse(dialog_on_screen.is_front_candidate(office, self.dialog))
        inner = UnoDialog()
        dialog_registry.OPEN.append(inner)
        self.addCleanup(dialog_registry.OPEN.remove, inner)
        office.active = None
        self.assertFalse(dialog_on_screen.is_front_candidate(office, self.dialog))
        self.assertTrue(dialog_on_screen.is_front_candidate(office, inner))


class Broadcaster:
    def __init__(self):
        self.listeners = []

    def addDocumentEventListener(self, listener):  # noqa: N802
        self.listeners.append(listener)

    def removeDocumentEventListener(self, listener):  # noqa: N802
        self.listeners.remove(listener)

    def fire(self, name, window):
        frame = Frame(window)
        controller = type("Controller", (), {"getFrame": lambda _self: frame})()
        source = type("Model", (), {"getCurrentController": lambda _self: controller})()
        event = type("Event", (), {"EventName": name, "Source": source})()
        for listener in list(self.listeners):
            listener.documentEventOccured(event)


class DisplayOffice(Office):
    """Office with a 1024x768 display (Toolkit.getWorkArea) and a global event broadcaster."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.broadcaster = Broadcaster()

    def createInstanceWithContext(self, name, ctx):  # noqa: N802
        service = super().createInstanceWithContext(name, ctx)
        service.getWorkArea = lambda: Rect(0, 0, 1024, 768)
        return service

    def getValueByName(self, name):  # noqa: N802
        assert name == "/singletons/com.sun.star.frame.theGlobalEventBroadcaster"
        return self.broadcaster


FULL_SCREEN, PLAIN = (0, 0, 1024, 768), (130, 121, 1024, 656)


class NewDocumentWhileOpenTests(unittest.TestCase):
    def watch(self, parent_rect, platform="darwin", is_open=lambda: True):
        self.office, self.timers, self.moved = DisplayOffice(), Timers(), []
        self.parent, self.document = Window(True, parent_rect), Window(True, (0, 28, 1024, 740))
        return dialog_on_screen.watch_new_documents(self.office, self.parent, is_open, self.moved.append,
                                                    timer=self.timers, platform=platform)

    def run_pending(self):
        self.timers.fire()
        self.office.pump()

    def test_mac_full_screen_parent_moves_the_dialog_onto_the_new_document(self):
        stop = self.watch(FULL_SCREEN)
        self.office.broadcaster.fire("OnTitleChanged", self.document)  # not an opened document
        self.assertEqual(self.timers.pending, [])
        self.office.broadcaster.fire("OnNew", self.document)
        self.assertEqual([d for d, _ in self.timers.pending], [dialog_on_screen.MOVE_DELAY])
        self.run_pending()
        self.assertEqual(self.moved, [self.document])
        stop()
        self.assertEqual(self.office.broadcaster.listeners, [])

    def test_mac_plain_window_parent_keeps_the_dialog(self):
        self.watch(PLAIN)
        self.office.broadcaster.fire("OnNew", self.document)
        self.run_pending()
        self.assertEqual(self.moved, [])

    def test_mac_not_when_the_dialog_ended_the_document_is_hidden_or_is_the_parent(self):
        self.watch(FULL_SCREEN, is_open=lambda: False)
        self.office.broadcaster.fire("OnViewCreated", self.document)
        self.run_pending()
        self.watch(FULL_SCREEN)
        self.document.visible = False
        self.office.broadcaster.fire("OnLoad", self.document)
        self.office.broadcaster.fire("OnViewCreated", self.parent)
        self.run_pending()
        self.assertEqual(self.moved, [])

    def test_windows_and_linux_watch_nothing(self):
        for platform in ("win32", "linux"):
            stop = self.watch(FULL_SCREEN, platform=platform)
            self.assertEqual(self.office.broadcaster.listeners, [])
            stop()


class DialogExecuteTests(unittest.TestCase):
    """dialogs.Dialog.execute with a parked (hidden) parent: shown parent, centred, logged, watched while it runs."""

    def test_hidden_parent_replaced_logged_and_unwatched_after_execute(self):
        shown, hidden = Window(True), Window(False)
        office = Office(current=Frame(shown))
        dialog = dialogs.Dialog.__new__(dialogs.Dialog)
        uno_dialog = UnoDialog()
        uno_dialog.createPeer = lambda toolkit, parent: setattr(uno_dialog, "parent_used", parent)
        uno_dialog.setVisible = lambda value: None
        uno_dialog.dispose = lambda: None
        dialog.ctx = dialog.smgr = office
        dialog.dialog, dialog.model = uno_dialog, type("Model", (), {"Title": "Văn bản hành chính"})()
        dialog._listeners, dialog._watchers, dialog.result = [], [], 1
        dialog.on_oversize = dialog.on_ready = dialog.on_closed = None
        seen = {}

        def run(d):
            seen["listeners_while_open"] = len(shown.listeners)
            return 1
        uno_dialog.execute = lambda: run(uno_dialog)
        dialog_on_screen.set_origin("Nd30Wizard")
        self.addCleanup(dialog_on_screen.set_origin, None)
        with mock.patch.object(dialogs.dialog_edit_heights, "fit_edits"), \
                mock.patch.object(dialog_on_screen, "_daemon_timer"), \
                mock.patch.object(dialog_on_screen.diag_log, "info") as info:
            self.assertEqual(dialog.execute(hidden), 1)
        self.assertIs(uno_dialog.parent_used, shown)
        self.assertEqual(uno_dialog.moved_to, (200, 200, 3))
        info.assert_called_once_with("dialog", "modal 'Văn bản hành chính' from Nd30Wizard, parent current-frame")
        self.assertEqual(seen["listeners_while_open"], 1)
        self.assertEqual(shown.listeners, [])

    def test_moved_dialog_runs_again_on_the_new_parent_with_the_same_model(self):
        """macOS full screen: a document opened while the dialog runs; the dialog ends its modal loop there and runs
        again as a new control on the document's window, with the same model, and is disposed once at the end."""
        parent, document = Window(True, FULL_SCREEN), Window(True)
        office, timers, runs, closed = DisplayOffice(current=Frame(parent)), Timers(), [], []
        model = type("Model", (), {"Title": "Văn bản hành chính"})()

        def uno_dialog():
            d = UnoDialog()
            d.createPeer = lambda toolkit, p: setattr(d, "parent_used", p)
            d.setVisible = d.endExecute = lambda *args: None
            d.disposed = 0
            d.dispose = lambda: setattr(d, "disposed", d.disposed + 1)
            d.setModel = lambda m: setattr(d, "model", m)
            d.execute = lambda: run(d)
            return d

        def run(d):
            runs.append(d)
            if len(runs) == 1:
                office.broadcaster.fire("OnNew", document)
                timers.fire()
                office.pump()  # main thread: the move ends this modal loop
            elif len(runs) == 2:
                office.broadcaster.fire("OnViewCreated", document)  # the same document again: no second move
                timers.fire()
                office.pump()
            return 1
        create = office.createInstanceWithContext
        office.createInstanceWithContext = lambda name, ctx: (
            uno_dialog() if name == "com.sun.star.awt.UnoControlDialog" else create(name, ctx))
        dialog = dialogs.Dialog.__new__(dialogs.Dialog)
        dialog.ctx = dialog.smgr = office
        dialog.dialog, dialog.model = uno_dialog(), model
        dialog._listeners, dialog._watchers, dialog.result = [], [], 1
        dialog.on_oversize = dialog.on_ready = None
        dialog.on_closed = lambda: closed.append(True)
        first = dialog.dialog
        real_watch = dialog_on_screen.watch_new_documents
        with mock.patch.object(dialogs.dialog_edit_heights, "fit_edits"), \
                mock.patch.object(dialog_on_screen, "_daemon_timer"), \
                mock.patch.object(dialog_on_screen, "watch_new_documents",
                                  lambda ctx, p, is_open, move: real_watch(ctx, p, is_open, move, timer=timers,
                                                                           platform="darwin")), \
                mock.patch.object(dialog_on_screen.diag_log, "info") as info:
            self.assertEqual(dialog.execute(parent), 1)
        second = dialog.dialog
        self.assertEqual(runs, [first, second])
        self.assertEqual((first.parent_used, first.disposed), (parent, 1))
        self.assertEqual((second.parent_used, second.model, second.disposed), (document, model, 1))
        self.assertEqual(closed, [True])
        self.assertEqual(office.broadcaster.listeners, [])
        self.assertEqual(info.call_args_list[-1],
                         mock.call("dialog", "modal 'Văn bản hành chính' from -, parent moved-to-new-document"))


class DispatchAfterNewDocumentTests(unittest.TestCase):
    """HST > Văn bản hành chính from a Sheets tab: the wizard opens after the new Writer tab is up, not inside the
    menu command that opened it."""

    def test_the_command_waits_until_the_new_tab_is_shown_and_loaded(self):
        writer_window = Window(False)
        writer = Frame(writer_window, locked=True, model=object())
        sheets = Frame(Window(True), model=type("Model", (), {"supportsService": lambda _s, n: False})())
        office, timers, command = Office(), Timers(), mock.Mock()
        handler = dispatch.Handler(office)
        handler.initialize((sheets,))
        url = type("URL", (), {"Protocol": dispatch.PROTOCOL, "Path": "Nd30Wizard"})
        real = dialog_on_screen.run_when_settled
        with mock.patch.object(handler, "_frame_for", return_value=(writer, True)), \
                mock.patch.dict(dispatch.COMMANDS, {"Nd30Wizard": command}), mock.patch.object(dispatch, "Host"), \
                mock.patch.object(dispatch.dialog_on_screen, "run_when_settled",
                                  lambda ctx, frame, fn: real(ctx, frame, fn, tries=5, delay=0.25, timer=timers)):
            handler.dispatch(url, ())
            command.assert_not_called()  # not inside the menu command
            timers.fire()
            office.pump()
            command.assert_not_called()  # the tab is not shown yet and its loader still holds it
            writer_window.visible, writer.locked = True, False
            timers.fire()
            office.pump()
        command.assert_called_once()
        self.assertIsNone(dialog_on_screen.origin())

    def test_a_document_of_the_right_kind_runs_at_once(self):
        office, command = Office(), mock.Mock()
        writer = Frame(Window(True), model=type("Model", (), {"supportsService": lambda _s, n: True})())
        handler = dispatch.Handler(office)
        handler.initialize((writer,))
        url = type("URL", (), {"Protocol": dispatch.PROTOCOL, "Path": "Nd30Wizard"})
        with mock.patch.dict(dispatch.COMMANDS, {"Nd30Wizard": command}), mock.patch.object(dispatch, "Host"):
            handler.dispatch(url, ())
        command.assert_called_once()


if __name__ == "__main__":
    unittest.main()
