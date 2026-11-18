# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF started on its own: the PDF file dialog when the request opened nothing, nothing more when it opened files
("Open with HST PDF"), and no office left without a window after Cancel. The office is stubbed."""
import unittest
from unittest import mock

import sys

import _paths  # noqa: F401
import uno_stubs  # pdf_open imports unohelper and the frame/task interfaces
_frame = sys.modules.setdefault("com.sun.star.frame", uno_stubs._StubModule("com.sun.star.frame"))
if isinstance(_frame, uno_stubs._StubModule):  # the veto must be raisable without an office
    _frame.TerminationVetoException = type("TerminationVetoException", (Exception,), {})
from hst_office import pdf_open  # noqa: E402


class Frame:
    def __init__(self, controller="ctrl"):
        self.controller = controller

    def getController(self):
        return self.controller


class Items:
    def __init__(self, items):
        self.items = list(items)

    def getCount(self):
        return len(self.items)

    def getByIndex(self, index):
        return self.items[index]

    def createEnumeration(self):
        return self

    def hasMoreElements(self):
        return bool(self.items)

    def nextElement(self):
        return self.items.pop(0)


class Desktop:
    def __init__(self, frames=(), docs=()):
        self.frames, self.docs, self.listeners, self.terminated, self.loaded = list(frames), list(docs), [], False, []

    def getFrames(self):
        return Items(self.frames)

    def getComponents(self):
        return Items(self.docs)

    def addTerminateListener(self, listener):
        self.listeners.append(listener)

    def removeTerminateListener(self, listener):
        self.listeners.remove(listener)

    def terminate(self):
        self.terminated = True

    def open(self, controller="viewer", doc="pdf"):
        self.frames.append(Frame(controller))
        self.docs.append(doc)


class Decision(unittest.TestCase):
    def test_a_new_window_document_or_tab_means_something_was_opened(self):
        start, doc = Frame(), Frame()
        before = ([(start, "start-center")], [])
        self.assertFalse(pdf_open.opened_since(before, ([(start, "start-center")], [])))
        self.assertTrue(pdf_open.opened_since(before, ([(start, "start-center"), (doc, "ctrl")], ["d"])))
        self.assertTrue(pdf_open.opened_since(before, ([(start, "pdf viewer")], ["d"])))
        self.assertTrue(pdf_open.opened_since(([(doc, "ctrl")], ["a"]), ([(doc, "ctrl")], ["a", "b"])))  # a tab
        self.assertFalse(pdf_open.opened_since(([], []), ([], [])))


class Run(unittest.TestCase):
    def go(self, desktop, before, picked):
        hold = object()
        desktop.listeners.append(hold)
        asked = []

        def choose(_ctx, language):
            asked.append(language)
            return picked
        with mock.patch.object(pdf_open, "open_in_viewer", side_effect=lambda d, urls: d.loaded.extend(urls) or
                               d.open()):
            outcome = pdf_open.run(None, desktop, before, hold, choose, "vi")
        self.assertEqual(desktop.listeners, [])  # the hold is always released
        return outcome, asked

    def test_cold_start_without_files_asks_and_quits_on_cancel(self):
        desktop = Desktop()
        outcome, asked = self.go(desktop, ([], []), [])
        self.assertEqual((outcome, asked, desktop.terminated), ("cancelled", ["vi"], True))  # no Start Center

    def test_the_chosen_files_open_in_the_viewer(self):
        desktop = Desktop()
        outcome, _asked = self.go(desktop, ([], []), ["file:///a.pdf", "file:///b.pdf"])
        self.assertEqual((outcome, desktop.loaded, desktop.terminated),
                         ("chosen", ["file:///a.pdf", "file:///b.pdf"], False))

    def test_running_office_keeps_its_windows_on_cancel(self):
        doc = Frame("ctrl")
        desktop = Desktop([doc], ["d"])
        outcome, asked = self.go(desktop, ([(doc, "ctrl")], ["d"]), [])
        self.assertEqual((outcome, asked, desktop.terminated), ("cancelled", ["vi"], False))

    def test_the_hold_refuses_termination(self):
        from com.sun.star.frame import TerminationVetoException
        with self.assertRaises(TerminationVetoException):
            pdf_open._HoldStart().queryTermination(None)


class CommandLine(unittest.TestCase):
    """The launcher's arguments as the office handles them: begin, the files (loaded in turn), then the dialog step."""

    def launch(self, desktop, files):
        posted = []
        pdf_open.handle(None, desktop, "begin", posted.append)
        for _url in files:
            desktop.open()
        pdf_open.handle(None, desktop, "", posted.append)
        self.assertEqual(len(posted), 1)
        asked = []
        with mock.patch.object(pdf_open, "choose", side_effect=lambda _c, lang: asked.append(lang) or []), \
                mock.patch("hst_office.update_texts.ui_language", return_value="vi"):
            posted[0]()
        return asked

    def test_files_from_the_file_manager_need_no_dialog(self):
        desktop = Desktop()
        self.assertEqual(self.launch(desktop, ["file:///a.pdf"]), [])
        self.assertFalse(desktop.terminated)

    def test_the_bare_launcher_asks(self):
        desktop = Desktop()
        self.assertEqual(self.launch(desktop, []), ["vi"])
        self.assertTrue(desktop.terminated)

    def test_without_begin_the_state_is_taken_at_the_dialog_step(self):
        desktop, posted = Desktop([Frame("ctrl")], ["d"]), []
        pdf_open.handle(None, desktop, "", posted.append)
        self.assertEqual(desktop.listeners[0].__class__.__name__, "_HoldStart")
        self.assertEqual(pdf_open._noted, [])

    def test_texts(self):
        self.assertIn("PDF", pdf_open.TEXTS["vi"]["title"])
        self.assertEqual(set(pdf_open.TEXTS), {"vi", "en"})


if __name__ == "__main__":
    unittest.main()
