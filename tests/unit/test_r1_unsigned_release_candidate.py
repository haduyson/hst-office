# SPDX-License-Identifier: AGPL-3.0-only
"""R1 on a release candidate: signing runs on main only, so an unsigned dmg skips the Gatekeeper items (M1-M3) as
needing a signed build and still gates the rest; a signed dmg that fails Gatekeeper, or an unsigned main build,
fails the run."""
from pathlib import Path
import sys
import unittest

from _paths import ROOT

sys.path.insert(0, str(Path(ROOT) / "tests/runtime"))
from r1auto import results  # noqa: E402

R1 = Path(ROOT) / "tests" / "runtime" / "r1auto"
WORKFLOW = Path(ROOT) / ".github" / "workflows" / "r1-auto-macos.yml"


def passed(item):
    return results.row(item, "PASS", "Đạt", f"{item}.png")


class UnsignedGate(unittest.TestCase):
    def rows(self):
        return [results.needs_signed_row(item) for item in results.NEEDS_SIGNED] + \
            [passed(f"M{i}") for i in range(4, 9)]

    def test_unsigned_candidate_passes_with_only_the_gatekeeper_items_skipped(self):
        self.assertTrue(results.gate(self.rows(), unsigned=True))

    def test_signed_package_never_skips_them(self):
        self.assertFalse(results.gate(self.rows()))
        self.assertFalse(results.gate(self.rows(), unsigned=False))

    def test_only_marked_gatekeeper_skips_count(self):
        plain = [results.row("M1", "SKIP", "Bỏ qua")] + self.rows()[1:]
        self.assertFalse(results.gate(plain, unsigned=True))
        other = self.rows()[:-1] + [results.needs_signed_row("M8")]
        self.assertFalse(results.gate(other, unsigned=True))
        failed = [results.row("M1", "FAIL", "Lỗi")] + self.rows()[1:]
        self.assertFalse(results.gate(failed, unsigned=True))

    def test_summary_says_it_is_not_a_release_result(self):
        report = dict(run_id="1", platform="macos", package=dict(signed=False), results=self.rows(), owner_review=[])
        self.assertIn("không phải kết quả phát hành", results.summary(report))
        report["package"]["signed"] = True
        self.assertNotIn("không phải kết quả phát hành", results.summary(report))


class Wiring(unittest.TestCase):
    def test_install_skips_the_first_start_only_for_an_unsigned_package(self):
        prepare = (R1 / "prepare.py").read_text(encoding="utf-8")
        self.assertIn('results.report["package"]["signed"] = os.environ.get("R1_SIGNED") == "true"', prepare)
        self.assertIn("install_without_quarantine(args, package, destination)\n        return destination, None, None",
                      prepare)
        run = (R1 / "run.py").read_text(encoding="utf-8")
        self.assertIn('item == "M3" and startup_ok is None', run)
        self.assertIn('gate(results.report["results"], unsigned)', run)

    def test_workflow_refuses_a_bad_signature_and_an_unsigned_main_build(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('echo "R1_SIGNED=true" >> "$GITHUB_ENV"; else echo "R1_SIGNED=false"', text)
        self.assertIn('echo "R1_SOURCE_BRANCH=$branch" >> "$GITHUB_ENV"', text)
        self.assertIn('if [ "$R1_SIGNED" = true ] && [ "$rc" -ne 0 ]; then', text)
        self.assertIn('if [ "$R1_SIGNED" != true ] && [ "$R1_SOURCE_BRANCH" = main ]; then', text)


if __name__ == "__main__":
    unittest.main()
