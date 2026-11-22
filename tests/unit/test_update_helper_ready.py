# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""macOS: the office waits for the helper's ready mark (update-ready) before it quits."""
import os
import tempfile
import threading
import unittest
from pathlib import Path

import _paths  # noqa: F401
from hst_office import update_helper_ready as ready


class FakeProc:
    def __init__(self, pid=4321, code=None):
        self.pid, self.code = pid, code

    def poll(self):
        return self.code


class Wait(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.cache, ignore_errors=True))
        self.stop = threading.Event()

    def mark(self, text):
        Path(ready.path(self.cache)).write_text(text, encoding="ascii")

    def wait(self, proc=None, limit=60):
        clock = iter(range(0, 10000, 10))
        return ready.wait(proc or FakeProc(), self.cache, self.stop, limit=limit, clock=lambda: next(clock), sleep=lambda s: None)

    def test_ready_and_failed_marks_of_this_helper(self):
        self.mark("4321 0 install\n")
        self.assertEqual(self.wait(), ("ready", None))
        self.mark("4321 1 verify\n")
        self.assertEqual(self.wait(), ("failed", "verify"))

    def test_mark_of_another_helper_or_broken_mark_is_ignored(self):
        for text in ("999 0 install\n", "4321 x install\n", "4321 0\n", ""):
            with self.subTest(text=text):
                self.mark(text)
                self.assertEqual(self.wait(limit=30), ("timeout", None))

    def test_helper_gone_cancel_and_timeout(self):
        self.assertEqual(self.wait(FakeProc(code=1)), ("exited", None))
        self.stop.set()
        self.assertEqual(self.wait(), ("cancelled", None))
        self.stop.clear()
        self.assertEqual(self.wait(limit=30), ("timeout", None))

    def test_discard_and_message_keys(self):
        self.mark("4321 0 install\n")
        ready.discard(self.cache)
        ready.discard(self.cache)
        self.assertFalse(os.path.exists(ready.path(self.cache)))
        self.assertEqual([ready.message_key(c) for c in ("verify", "readonly", "install", "wait")],
                         ["err_verify", "err_readonly", "err_prepare", "err_prepare"])


if __name__ == "__main__":
    unittest.main()
