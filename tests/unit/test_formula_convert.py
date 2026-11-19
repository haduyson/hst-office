# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức conversion: OLE data of objects Windows has started, one undo step, few progress bar updates."""
import unittest

import _paths  # noqa: F401

from hst_office import formula_convert


class FakeEmbedded:
    """An OLE object that stores its data only when loaded, like a running MathType object without its server."""
    def __init__(self, state, unloads=True):
        self.state, self.unloads = state, unloads

    def getCurrentState(self):
        return self.state

    def changeState(self, state):
        if not self.unloads:
            raise RuntimeError("cannot unload")
        self.state = state


class OleDataTest(unittest.TestCase):
    def setUp(self):
        stored = formula_convert._stored
        self.addCleanup(setattr, formula_convert, "_stored", stored)
        formula_convert._stored = lambda ctx, obj: b"ole" if obj.state == formula_convert.LOADED else b""

    def test_running_object_is_unloaded_and_stored(self):
        obj = FakeEmbedded(state=1)  # RUNNING: Windows started it to show it
        self.assertEqual(b"ole", formula_convert.ole_data(None, obj))
        self.assertEqual(formula_convert.LOADED, obj.state)

    def test_loaded_or_stuck_object_is_left_alone(self):
        self.assertEqual(b"ole", formula_convert.ole_data(None, FakeEmbedded(state=0)))
        formula_convert._stored = lambda ctx, obj: b""
        self.assertEqual(b"", formula_convert.ole_data(None, FakeEmbedded(state=0)))
        self.assertEqual(b"", formula_convert.ole_data(None, FakeEmbedded(state=1, unloads=False)))


class FakeUndoDoc:
    """A document that records the undo contexts, view locks and progress bar updates of convert_all."""
    def __init__(self):
        self.calls, self.titles = [], []

    def getUndoManager(self):
        return self

    def getAllUndoActionTitles(self):
        return tuple(self.titles)

    def enterUndoContext(self, title):
        self.calls.append("enter")

    def leaveUndoContext(self):
        self.calls.append("leave")
        self.titles.append("step")

    def lockControllers(self):
        self.calls.append("lock")

    def unlockControllers(self):
        self.calls.append("unlock")

    def setValue(self, value):
        self.calls.append(value)

    def end(self):
        self.calls.append("end")


class ConvertAllTest(unittest.TestCase):
    def test_one_undo_step_and_few_progress_updates(self):
        doc, clock = FakeUndoDoc(), [0.0]
        saved = {n: getattr(formula_convert, n) for n in ("candidates", "convert_one", "_progress", "_settle")}
        self.addCleanup(lambda: [setattr(formula_convert, n, f) for n, f in saved.items()])
        monotonic = formula_convert.time.monotonic
        self.addCleanup(setattr, formula_convert.time, "monotonic", monotonic)
        formula_convert.time.monotonic = lambda: clock[0]

        def convert(ctx, d, container, obj):
            clock[0] += 0.02  # 454 equations at 20 ms each
            return obj % 10 != 0  # every tenth one stays an OLE object
        formula_convert.candidates = lambda d: [(None, i) for i in range(1, 455)]
        formula_convert.convert_one = convert
        formula_convert._progress = lambda d, text, count: d
        formula_convert._settle = lambda ctx: doc.calls.append("settle")
        self.assertEqual((409, 45), formula_convert.convert_all(None, doc, "Chuyển công thức"))
        self.assertEqual(["step"], doc.titles)
        words = [c for c in doc.calls if isinstance(c, str)]
        self.assertEqual(["enter", "lock", "unlock", "settle", "leave", "end"], words)
        updates = [c for c in doc.calls if isinstance(c, int)]
        # each update lets the office lay out and repaint: about one per PROGRESS_SECONDS, not one per equation
        self.assertTrue(10 <= len(updates) <= 20, updates)


if __name__ == "__main__":
    unittest.main()
