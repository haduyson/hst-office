# SPDX-License-Identifier: AGPL-3.0-only
"""A launcher's own new blank document (HST Writer, HST Sheets, ... on macOS, Windows and Linux: --writer and the
like) is no work of the user: the first-start questions (welcome, default apps, the launcher notice) come as on a plain
start. A file, a closed document window or a change still counts (test_startup_prompts_after_work.py)."""
import unittest

from test_startup_prompts_after_work import _Controller, _Desktop, _Frame, _Model, _ctx, activity


class LauncherStart(unittest.TestCase):
    def setUp(self):
        self.start_center = _Frame(_Controller())  # StartModule: no model
        self.desktop = _Desktop([self.start_center])
        self.ctx = _ctx(self.desktop)
        self.before = activity.snapshot(self.ctx)

    def test_a_launchers_new_blank_document_in_the_start_center_window_is_no_work(self):
        """HST Writer / --writer on macOS, Windows and Linux: the first window shows the Start Center, then the
        launcher's new document takes it; the first-start questions must come as on a plain start."""
        self.start_center.controller = _Controller(_Model(url=""))
        self.assertFalse(activity.started_working(self.ctx, self.before))

    def test_a_launchers_new_blank_document_in_a_window_of_its_own_is_no_work(self):
        self.desktop.frames.append(_Frame(_Controller(_Model(url=""))))
        self.assertFalse(activity.started_working(self.ctx, self.before))
        self.desktop.frames.remove(self.start_center)  # the Start Center window gave way to it
        self.assertFalse(activity.started_working(self.ctx, self.before))

    def test_typing_into_the_new_blank_document_counts(self):
        self.start_center.controller = _Controller(_Model(url="", modified=True))
        self.assertTrue(activity.started_working(self.ctx, self.before))
        self.desktop.frames.append(_Frame(_Controller(_Model(url="", modified=True))))
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_a_blank_document_replacing_another_document_counts(self):
        doc = _Frame(_Controller(_Model()))
        self.desktop.frames = [doc]
        before = activity.snapshot(self.ctx)
        doc.controller = _Controller(_Model(url=""))
        self.assertTrue(activity.started_working(self.ctx, before))

    def test_closing_a_document_window_counts(self):
        doc = _Frame(_Controller(_Model(url="")))
        self.desktop.frames.append(doc)
        before = activity.snapshot(self.ctx)
        self.desktop.frames.remove(doc)
        self.assertTrue(activity.started_working(self.ctx, before))


if __name__ == "__main__":
    unittest.main()
