# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""windows_modal_safe: a wait on a dialog is reported as such, never as a product hang.

The 1.0.2 smoke on HST3 reported an embedded-Calc .docx as hanging: the load ran on the UNO bridge thread while the
HST start-up question was up (later a stale lock file's "Document in Use"), in the user's real profile, on a file
name reused after a killed office. These tests pin the parts that prevent each of those, on any platform."""
import os
import sys
import tempfile
import unittest

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
sys.path.insert(0, RUNTIME)

import windows_modal_safe as safe  # noqa: E402

PROFILE = "file:///D:/hst-test/run/profile"


class FreshCopyTests(unittest.TestCase):
    def test_every_copy_has_a_new_name_and_keeps_the_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            src = os.path.join(folder, "embedded-calc.docx")
            with open(src, "wb") as handle:
                handle.write(b"x")
            names = {os.path.basename(safe.fresh_copy(src, os.path.join(folder, "open"), "v")) for _ in range(20)}
            self.assertEqual(len(names), 20)
            self.assertTrue(all(n.startswith("embedded-calc-v-") and n.endswith(".docx") for n in names))


class OwnLockTests(unittest.TestCase):
    def write_lock(self, document, owner):
        with open(safe.lock_path(document), "w", encoding="utf-8") as handle:
            handle.write(",U2U-SEO3/kiemtra,U2U-SEO3,15.11.2026 23:56,%s;" % owner)

    def test_lock_path_is_the_office_lock_name(self):
        self.assertEqual(safe.lock_path(os.path.join("d", "a.docx")), os.path.join("d", ".~lock.a.docx#"))

    def test_only_locks_of_our_profile_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            ours, theirs, unlocked = (os.path.join(folder, n) for n in ("ours.docx", "theirs.docx", "none.docx"))
            self.write_lock(ours, "file:///d:/hst-test/run/profile/")
            self.write_lock(theirs, "file:///D:/hst-test/other/profile")
            removed = safe.remove_own_locks([ours, theirs, unlocked], PROFILE)
            self.assertEqual(removed, [safe.lock_path(ours)])
            self.assertTrue(os.path.exists(safe.lock_path(theirs)))

    def test_an_unreadable_lock_text_is_left_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = os.path.join(folder, "a.docx")
            with open(safe.lock_path(doc), "w") as handle:
                handle.write("garbage")
            self.assertEqual(safe.remove_own_locks([doc], PROFILE), [])


class SeedTests(unittest.TestCase):
    def test_quiet_seed_found_only_when_every_item_is_there(self):
        items = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % i
                        for i in safe.QUIET)
        self.assertTrue(safe.registry_has("<oor:items>%s</oor:items>" % items, safe.QUIET))
        self.assertFalse(safe.registry_has("<oor:items>%s</oor:items>" % items.split("\n")[0], safe.QUIET))

    def test_quiet_answers_both_start_up_questions(self):
        nodes = {(node, name): value for node, name, value in safe.QUIET}
        self.assertEqual(nodes[("/org.hasontech.hstoffice.Welcome", "Shown")], "true")
        self.assertEqual(nodes[("/org.hasontech.hstoffice.DefaultApps", "Ask")], "false")


class VerdictTests(unittest.TestCase):
    ROWS = [(1, "SALFRAME", "embedded-calc.docx - HST Writer", True, 0),
            (2, "SALSUBFRAME", "HST Office chào đón bạn", True, 1),
            (3, "SALSUBFRAME", "", True, 1), (4, "SALSUBFRAME", "Tài liệu đang được dùng", False, 1),
            (5, "SALTMPSUBFRAME", "VCL ImplGetDefaultWindow", True, 0)]

    def test_modal_titles_are_visible_owned_titled_dialogs(self):
        self.assertEqual(safe.modal_titles(self.ROWS), ["HST Office chào đón bạn"])

    def test_verdict(self):
        self.assertEqual(safe.verdict(True, []), "done")
        self.assertEqual(safe.verdict(False, ["Tài liệu đang được dùng"]), "waiting-on-dialog")
        self.assertEqual(safe.verdict(False, []), "hang")

    def test_bounded_reads_titles_only_when_the_call_did_not_return(self):
        asked = []
        state, value, titles = safe.bounded(lambda: 7, 5, PROFILE, titles_of=lambda url: asked.append(url) or ["x"])
        self.assertEqual((state, value, titles, asked), ("done", 7, [], []))
        import threading
        never = threading.Event()
        state, value, titles = safe.bounded(never.wait, 0.2, PROFILE, titles_of=lambda url: ["HST Office chào đón bạn"])
        self.assertEqual((state, titles), ("waiting-on-dialog", ["HST Office chào đón bạn"]))
        never.set()

    def test_bounded_returns_the_exception_of_the_call(self):
        state, value, _ = safe.bounded(lambda: 1 / 0, 5, PROFILE, titles_of=lambda url: [])
        self.assertEqual(state, "done")
        self.assertIsInstance(value, ZeroDivisionError)

    def test_close_veto_reports_the_modal(self):
        class Vetoing:
            def close(self, _deliver):
                raise RuntimeError("Controller disagree ...")

        class Closing:
            def close(self, _deliver):
                pass
        self.assertIsNone(safe.close_or_report(Closing(), PROFILE, titles_of=lambda url: []))
        report = safe.close_or_report(Vetoing(), PROFILE, titles_of=lambda url: ["HST Office"])
        self.assertEqual(report["modal"], ["HST Office"])


class EmbeddedRoundtripCheckTests(unittest.TestCase):
    def test_the_check_loads_through_the_main_thread_and_the_quiet_profile(self):
        text = open(os.path.join(RUNTIME, "check-windows-embedded-calc-roundtrip.py"), encoding="utf-8").read()
        self.assertNotIn("loadComponentFromURL(", text)
        self.assertIn("office.load(", text)  # WinOffice.load -> uno_main_thread_load (OnMainThread=True)
        for name in ("quiet_profile", "fresh_copy", "bounded", "close_or_report", "remove_own_locks"):
            self.assertIn("safe.%s(" % name, text)


if __name__ == "__main__":
    unittest.main()
