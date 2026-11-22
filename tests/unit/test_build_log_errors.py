# SPDX-License-Identifier: AGPL-3.0-only
"""A failed build keeps its real error lines (scripts/build_infra/build_log_errors.py): compiler/linker errors and
make's `Error N` with context, not only the tail of warnings; local-build.sh prints the block before the tail, and
`build-queue.sh wait|status` show it for a failed job (also for older logs without the block)."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_queue_fixtures import ROOT, QueueTestCase, bq
from build_infra import build_log_errors as ble  # noqa: E402

LO = "/data/hst-office-build/src/lo"
WARNINGS = "".join(f"{LO}/include/o3tl/sorted_vector.hxx:{n}:14: warning: 'get_temporary_buffer' is deprecated\n"
                   f"  {n} |         std::stable_sort(m_vector.begin(), m_vector.end(), Compare());\n"
                   for n in range(200, 260))
FAILED_LOG = (
    "[build CXX] sw/source/core/text/error.cxx\n"
    + WARNINGS[:2000]
    + f"{LO}/sw/source/uibase/uno/hstmailmergetermination.cxx:42:47: error: implicit instantiation of undefined "
      "template 'rtl::Reference<hst::sw::MailMergeTerminationGuard>'\n"
      "   42 |     rtl::Reference<MailMergeTerminationGuard> xKeepAlive(this);\n"
      "      |                                               ^\n"
      f"{LO}/include/vcl/svapp.hxx:74:55: note: template is declared here\n"
      "1 error generated.\n"
      f"make[1]: *** [{LO}/solenv/gbuild/LinkTarget.mk:335: {LO}/workdir/CxxObject/sw/source/uibase/uno/"
      "hstmailmergetermination.o] Error 1\n"
    + WARNINGS
    + "make: *** [Makefile:137: sw.build] Error 2\n")


class ErrorLinesTest(unittest.TestCase):
    def test_the_compile_error_and_its_context_survive_a_tail_full_of_warnings(self):
        tail = "\n".join(FAILED_LOG.splitlines()[-60:])
        self.assertNotIn("error:", tail)                       # what the queue used to keep
        block = ble.error_block(FAILED_LOG)
        self.assertTrue(block.startswith(ble.HEADER))
        self.assertIn("hstmailmergetermination.cxx:42:47: error: implicit instantiation", block)
        self.assertIn("xKeepAlive(this);", block)              # the source line after the error
        self.assertIn("note: template is declared here", block)
        self.assertIn("hstmailmergetermination.o] Error 1", block)
        self.assertIn("sw.build] Error 2", block)
        self.assertNotIn("[build CXX]", block)                 # progress lines are not errors

    def test_linker_fatal_and_msvc_errors_and_the_cap(self):
        text = ("a\nb\n/usr/bin/ld: libsw.so: undefined reference to `Foo::bar()'\nc\n"
                "x.cxx:1:10: fatal error: rtl/ref.hxx: No such file or directory\n"
                r"D:\hst-build\lo\sc\source\ui\c.cxx(40): error C2065: 'y': undeclared identifier" "\n"
                "xmlsecurity/uiconfig/ui/a.ui:631 FATAL WARNING: 'GtkImage' has no label\n")
        found = "\n".join(ble.error_lines(text, before=0, after=0))
        for needle in ("undefined reference", "fatal error", "error C2065", "FATAL WARNING"):
            self.assertIn(needle, found)
        many = "\n".join(f"f{i}.cxx:1:1: error: e{i}\nctx" for i in range(500))
        capped = ble.error_lines(many, before=0, after=1, max_lines=50)
        self.assertEqual(len(capped), 51)
        self.assertRegex(capped[-1], r"^\.\.\. \d+ more error lines$")
        self.assertEqual(ble.error_block("all good\nwarning: x\n"), "")

    def test_the_script_runs_standalone_on_a_build_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp, "build.log")
            log.write_text(FAILED_LOG)
            done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/build_infra/build_log_errors.py"),
                                   str(log)], capture_output=True, text=True, cwd=tmp, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("error: implicit instantiation", done.stdout)
        script = (ROOT / "scripts/linux/local-build.sh").read_text()
        call = 'python3 -I "$SELF_REPO/scripts/build_infra/build_log_errors.py" "$BUILD_LOG"'
        self.assertIn(call, script)
        self.assertLess(script.index(call), script.index('tail -60 "$BUILD_LOG"'))   # errors first, then the tail


class LocalBuildPackageWithTestsTest(unittest.TestCase):
    def test_package_flag_keeps_packaging_after_tests_but_not_with_modules(self):
        script = (ROOT / "scripts/linux/local-build.sh").read_text()
        self.assertIn("--package) PACKAGE_WITH_TESTS=1", script)
        self.assertIn('[ "$PACKAGE_WITH_TESTS" -eq 1 ] || PACKAGE=0', script)   # --test alone: no package
        self.assertIn('die "--package cannot be combined with --modules"', script)
        # Packaging runs after the tests and the test results are copied after it (it recreates the output dir).
        self.assertLess(script.index("timed tests run_tests"), script.index("timed package do_package"))
        self.assertLess(script.index("timed package do_package"), script.index('cp -r "$TEST_OUT/." "$DEST/"'))


class FailedJobOutputTest(QueueTestCase):
    def failed(self, log_text):
        job, _ = self.submit(modules=["sw"])
        Path(job["log"]).parent.mkdir(parents=True, exist_ok=True)
        Path(job["log"]).write_text(log_text)
        return self.store.update(job["id"], state="failed", error="local-build.sh exit 2")

    def test_wait_shows_the_block_local_build_printed(self):
        job = self.failed("[2026-11-19] slot 4: building\n" + ble.error_block(FAILED_LOG) + WARNINGS)
        out = io.StringIO()
        self.assertEqual(bq.wait(self.store, job["id"], out=out), 1)
        text = out.getvalue()
        self.assertIn("hstmailmergetermination.cxx:42:47: error:", text)
        self.assertLess(text.index(ble.HEADER), text.index(ble.FOOTER))

    def test_wait_finds_the_errors_in_an_older_log_without_the_block(self):
        job = self.failed(FAILED_LOG)
        out = io.StringIO()
        bq.wait(self.store, job["id"], out=out)
        self.assertIn("error: implicit instantiation", out.getvalue())
        self.assertEqual(bq.failure_errors(os.path.join(self.store.root, "missing.log")), "")


if __name__ == "__main__":
    unittest.main()
