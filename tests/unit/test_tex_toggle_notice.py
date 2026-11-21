# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức reports on the status bar, never in a modal box: the line for converted, failed and mixed
runs, and the line going away on the timer or the next key press or click without consuming the event."""
import sys
import types
import unittest
from collections import namedtuple

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.awt.Key",
              "com.sun.star.lang", "com.sun.star.util", "com.sun.star.util.MeasureUnit"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import tex_toggle_action, tex_toggle_notice, tex_toggle_writer  # noqa: E402
from hst_office.tex_toggle_texts import TEXTS  # noqa: E402

Result = namedtuple("Result", "converted failed reverted kept")


class Indicator:
    def __init__(self):
        self.started, self.ended = [], 0

    def start(self, text, count):
        self.started.append((text, count))

    def end(self):
        self.ended += 1


class Controller:
    def __init__(self):
        self.keys, self.clicks = [], []

    def addKeyHandler(self, handler):
        self.keys.append(handler)

    def removeKeyHandler(self, handler):
        self.keys.remove(handler)

    def addMouseClickHandler(self, handler):
        self.clicks.append(handler)

    def removeMouseClickHandler(self, handler):
        self.clicks.remove(handler)


class Frame:
    def __init__(self):
        self.indicator, self.controller = Indicator(), Controller()

    def createStatusIndicator(self):
        return self.indicator

    def getController(self):
        return self.controller


class MainThread:
    """com.sun.star.awt.AsyncCallback stand-in: callbacks run when the test drains the queue."""

    def __init__(self):
        self.queue = []
        self.ServiceManager = types.SimpleNamespace(createInstanceWithContext=lambda name, ctx: self)

    def addCallback(self, callback, data):
        self.queue.append(callback)

    def drain(self):
        while self.queue:
            self.queue.pop(0).notify(None)


class Host:
    def __init__(self, ctx, writer=True):
        self.ctx, self.frame, self.peer = ctx, Frame(), object()
        self.doc, self.controller, self.writer = object(), self.frame.controller, writer

    def is_writer(self):
        return self.writer


class ActionTest(unittest.TestCase):
    def setUp(self):
        self.boxes, self.timers, self.ctx = [], [], MainThread()
        self.saved = (tex_toggle_action.message_box, tex_toggle_writer.toggle, tex_toggle_notice._daemon_timer)
        tex_toggle_action.message_box = lambda *args: self.boxes.append(args)
        tex_toggle_notice._daemon_timer = lambda delay, action: self.timers.append((delay, action))

    def tearDown(self):
        tex_toggle_action.message_box, tex_toggle_writer.toggle, tex_toggle_notice._daemon_timer = self.saved

    def run_with(self, result):
        tex_toggle_writer.toggle = lambda ctx, doc, controller, title: result
        host = Host(self.ctx)
        tex_toggle_action.run(host)
        self.assertEqual(self.boxes, [], "no modal message box after the toggle")
        self.assertEqual(len(host.frame.indicator.started), 1)
        text, count = host.frame.indicator.started[0]
        self.assertEqual(count, 0)
        self.assertNotIn("\n", text)
        return host, text

    def test_converted(self):
        _, text = self.run_with(Result(3, 0, 0, 0))
        self.assertEqual(text, TEXTS["converted"] % 3)
        self.assertEqual(text, "Đã chuyển 3 công thức LaTeX thành công thức (Hoàn tác: Ctrl+Z).")

    def test_failed_says_how_many_and_yellow(self):
        _, text = self.run_with(Result(0, 2, 0, 0))
        self.assertEqual(text, TEXTS["failed"] % 2)
        self.assertIn("2 công thức LaTeX không chuyển được", text)
        self.assertIn("tô vàng", text)

    def test_mixed_on_one_line(self):
        _, text = self.run_with(Result(40, 2, 1, 1))
        self.assertEqual(text, " ".join([TEXTS["converted"] % 40, TEXTS["failed"] % 2, TEXTS["reverted"] % 1,
                                         TEXTS["kept"] % 1]))

    def test_reverted(self):
        _, text = self.run_with(Result(0, 0, 1, 0))
        self.assertEqual(text, "Đã chuyển 1 công thức về mã LaTeX.")

    def test_nothing_found(self):
        _, text = self.run_with(Result(0, 0, 0, 0))
        self.assertEqual(text, TEXTS["none"])

    def test_line_goes_after_the_timer(self):
        host, _ = self.run_with(Result(1, 0, 0, 0))
        self.assertEqual([delay for delay, _ in self.timers], [tex_toggle_notice.NOTICE_SECONDS])
        self.assertAlmostEqual(tex_toggle_notice.NOTICE_SECONDS, 5.0)
        self.timers[0][1]()  # the timer thread only posts to the main thread
        self.assertEqual(host.frame.indicator.ended, 0)
        self.ctx.drain()
        self.assertEqual(host.frame.indicator.ended, 1)
        self.assertEqual((host.controller.keys, host.controller.clicks), ([], []))

    def test_next_key_or_click_clears_without_consuming(self):
        for event in ("keyPressed", "mousePressed"):
            host, _ = self.run_with(Result(1, 0, 0, 0))
            self.boxes, self.timers = [], []
            handler = host.controller.keys[0]
            self.assertIs(host.controller.clicks[0], handler)
            self.assertFalse(getattr(handler, event)(object()), "the event goes on to the document")
            self.ctx.drain()
            self.assertEqual(host.frame.indicator.ended, 1)
            self.assertEqual((host.controller.keys, host.controller.clicks), ([], []))
            handler.close_later()  # the timer after the key: nothing left to clear
            self.ctx.drain()
            self.assertEqual(host.frame.indicator.ended, 1)

    def test_releases_are_not_consumed(self):
        host, _ = self.run_with(Result(1, 0, 0, 0))
        handler = host.controller.keys[0]
        self.assertFalse(handler.keyReleased(object()))
        self.assertFalse(handler.mouseReleased(object()))
        self.assertEqual(host.frame.indicator.ended, 0)

    def test_frame_without_indicator_is_quiet(self):
        tex_toggle_writer.toggle = lambda ctx, doc, controller, title: Result(1, 0, 0, 0)
        host = Host(self.ctx)

        def no_indicator():
            raise RuntimeError("hidden document")
        host.frame.createStatusIndicator = no_indicator
        tex_toggle_action.run(host)
        self.assertEqual(self.boxes, [])
        self.assertEqual(self.timers, [])

    def test_outside_writer_still_explains(self):
        host = Host(self.ctx, writer=False)
        tex_toggle_action.run(host)
        self.assertEqual(len(self.boxes), 1)
        self.assertEqual(self.boxes[0][3], TEXTS["writerOnly"])


if __name__ == "__main__":
    unittest.main()
