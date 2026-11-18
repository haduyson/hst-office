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


class Frames:
    def __init__(self, frames):
        self.frames = frames

    def getCount(self):
        return len(self.frames)

    def getByIndex(self, index):
        return self.frames[index]


class Desktop:
    def __init__(self, frames=()):
        self.frames, self.listeners, self.terminated, self.loaded = list(frames), [], False, []

    def getFrames(self):
        return Frames(self.frames)

    def addTerminateListener(self, listener):
        self.listeners.append(listener)

    def removeTerminateListener(self, listener):
        self.listeners.remove(listener)

    def terminate(self):
        self.terminated = True


class Decision(unittest.TestCase):
    def test_a_new_window_or_document_means_the_request_opened_files(self):
        start, doc = Frame(), Frame()
        before = [(start, "start-center")]
        self.assertFalse(pdf_open.opened_since(before, [(start, "start-center")]))
        self.assertTrue(pdf_open.opened_since(before, [(start, "start-center"), (doc, "ctrl")]))
        self.assertTrue(pdf_open.opened_since(before, [(start, "pdf viewer")]))
        self.assertFalse(pdf_open.opened_since([], []))
        self.assertTrue(pdf_open.opened_since([], [(doc, "ctrl")]))


class Run(unittest.TestCase):
    def go(self, desktop, before, picked):
        hold = object()
        desktop.listeners.append(hold)
        asked = []

        def choose(_ctx, language):
            asked.append(language)
            return picked
        with mock.patch.object(pdf_open, "open_in_viewer", side_effect=lambda d, urls: d.loaded.extend(urls) or
                               d.frames.append(Frame("viewer"))):
            outcome = pdf_open.run(None, desktop, before, hold, choose, "vi")
        self.assertEqual(desktop.listeners, [])  # the start-up hold is always released
        return outcome, asked

    def test_cold_start_without_files_asks_and_quits_on_cancel(self):
        desktop = Desktop()
        outcome, asked = self.go(desktop, [], [])
        self.assertEqual((outcome, asked, desktop.terminated), ("cancelled", ["vi"], True))  # no Start Center

    def test_cold_start_opens_the_chosen_files_in_the_viewer(self):
        desktop = Desktop()
        outcome, _asked = self.go(desktop, [], ["file:///a.pdf", "file:///b.pdf"])
        self.assertEqual((outcome, desktop.loaded, desktop.terminated), ("chosen", ["file:///a.pdf", "file:///b.pdf"],
                                                                         False))

    def test_files_on_the_command_line_need_no_dialog(self):
        desktop = Desktop()
        desktop.frames.append(Frame("viewer"))  # opened by the same request after trigger()
        outcome, asked = self.go(desktop, [], ["never"])
        self.assertEqual((outcome, asked, desktop.terminated), ("opened", [], False))

    def test_running_office_keeps_its_windows_on_cancel(self):
        doc = Frame("ctrl")
        desktop = Desktop([doc])
        outcome, asked = self.go(desktop, [(doc, "ctrl")], [])
        self.assertEqual((outcome, asked, desktop.terminated), ("cancelled", ["vi"], False))

    def test_the_hold_refuses_termination(self):
        from com.sun.star.frame import TerminationVetoException
        with self.assertRaises(TerminationVetoException):
            pdf_open._HoldStart().queryTermination(None)

    def test_texts(self):
        self.assertIn("PDF", pdf_open.TEXTS["vi"]["title"])
        self.assertEqual(set(pdf_open.TEXTS), {"vi", "en"})


if __name__ == "__main__":
    unittest.main()
