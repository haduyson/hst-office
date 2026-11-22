# SPDX-License-Identifier: AGPL-3.0-only
"""Pre-submit patch lint (scripts/build_infra/queue_patch_lint.py): `diff --git` headers need a/ and b/, `---`/`+++`
paths must land under a LibreOffice module with `patch -p1`, hunk content that looks like a header is ignored;
`submit` and `train add` refuse such a commit, the integrator can force it."""
import io
import os
import tempfile
import unittest

from build_queue_fixtures import QueueTestCase, bq
from build_infra import queue_patch_lint as lint  # noqa: E402

DIRS, ROOT_FILES = {"sw", "sc", "solenv"}, {"Makefile.in", "configure.ac"}
GOOD = ("From 1 Mon Sep 17 00:00:00 2001\nSubject: [PATCH] x\n---\n sw/source/a.cxx | 2 +-\n\n"
        "diff --git a/sw/source/a.cxx b/sw/source/a.cxx\n--- a/sw/source/a.cxx\n+++ b/sw/source/a.cxx\n"
        "@@ -1,3 +1,3 @@\n ctx\n--- removed line that starts with two dashes\n+++ added line with plus signs\n ctx\n"
        "\\ No newline at end of file\n"
        "diff --git a/sw/qa/new.cxx b/sw/qa/new.cxx\nnew file mode 100644\n--- /dev/null\n+++ b/sw/qa/new.cxx\n"
        "@@ -0,0 +1 @@\n+int x;\n"
        "diff --git a/configure.ac b/configure.ac\n--- a/configure.ac\n+++ b/configure.ac\n@@ -1 +1 @@\n-a\n+b\n")
BARE = ("diff --git sw/CppunitTest_sw_x.mk sw/CppunitTest_sw_x.mk\nnew file mode 100644\n--- /dev/null\n"
        "+++ sw/CppunitTest_sw_x.mk\n@@ -0,0 +1 @@\n+x\n")


class LintPatchTest(unittest.TestCase):
    def test_a_well_formed_patch_passes_even_with_header_like_hunk_lines(self):
        self.assertEqual(lint.lint_patch("good.patch", GOOD, DIRS, ROOT_FILES), [])

    def test_bare_paths_are_reported_with_their_line(self):
        problems = lint.lint_patch("bad.patch", BARE, DIRS, ROOT_FILES)
        self.assertEqual(len(problems), 2)
        self.assertRegex(problems[0], r"^bad\.patch:1: .*lacks the a/ and b/ prefixes")
        self.assertRegex(problems[1], r"^bad\.patch:4: .*'sw/CppunitTest_sw_x.mk' lacks the b/ prefix")

    def test_paths_must_land_under_a_module_or_on_an_existing_root_file(self):
        root_new = ("diff --git a/CppunitTest_sw_x.mk b/CppunitTest_sw_x.mk\n--- /dev/null\n+++ b/CppunitTest_sw_x.mk\n"
                    "@@ -0,0 +1 @@\n+x\n")
        unknown_dir = "diff --git a/qa/extras/x.cxx b/qa/extras/x.cxx\n--- a/qa/extras/x.cxx\n+++ b/qa/extras/x.cxx\n"
        self.assertIn("lands at the source root", lint.lint_patch("r.patch", root_new, DIRS, ROOT_FILES)[0])
        self.assertIn("qa/, which the tree does not have", lint.lint_patch("q.patch", unknown_dir, DIRS, ROOT_FILES)[0])
        self.assertEqual(lint.lint_patch("q.patch", unknown_dir), [])   # no reference tree: prefixes only

    def test_a_new_file_may_start_a_new_hst_module_but_an_edit_may_not(self):
        new_module = ("diff --git a/hst/source/core.cxx b/hst/source/core.cxx\nnew file mode 100644\n--- /dev/null\n"
                      "+++ b/hst/source/core.cxx\n@@ -0,0 +1 @@\n+int x;\n")
        edit_unknown = ("diff --git a/hst/source/core.cxx b/hst/source/core.cxx\n--- a/hst/source/core.cxx\n"
                        "+++ b/hst/source/core.cxx\n@@ -1 +1 @@\n-a\n+b\n")
        self.assertEqual(lint.lint_patch("n.patch", new_module, DIRS, ROOT_FILES), [])
        self.assertEqual(len(lint.lint_patch("e.patch", edit_unknown, DIRS, ROOT_FILES)), 2)

    def test_tree_layout(self):
        with tempfile.TemporaryDirectory() as tree:
            os.mkdir(os.path.join(tree, "sw"))
            open(os.path.join(tree, "configure.ac"), "w").close()
            self.assertEqual(lint.tree_layout(tree), ({"sw"}, {"configure.ac"}))
        self.assertEqual(lint.tree_layout("/nonexistent/lo"), (None, None))


class SubmitLintTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.git.tips["rc/1.0.2-batch5"] = "f" * 40
        self.git.bases[("f" * 40, self.shas["feat/x"])] = "e" * 40
        self.git.patch_files = ["patches/libreoffice/hst-x.patch"]

    def test_submit_refuses_a_bad_patch_and_the_integrator_can_force(self):
        self.git.patch_texts = {"patches/libreoffice/hst-x.patch": BARE}
        with self.assertRaisesRegex(bq.QueueError, r"patch lint failed.*\n  hst-x\.patch:1: "):
            self.submit(ref="feat/x", err=io.StringIO())
        self.assertEqual(self.store.all(), [])
        job, _ = self.submit(ref="feat/x", force=True, integrator=True, err=io.StringIO())
        self.assertEqual(job["state"], "queued")
        self.git.patch_texts = {"patches/libreoffice/hst-x.patch": GOOD}
        job, _ = self.submit(ref="feat/x", tests=["CppunitTest_a"], err=io.StringIO())
        self.assertEqual(job["state"], "queued")


if __name__ == "__main__":
    unittest.main()
