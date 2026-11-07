# SPDX-License-Identifier: AGPL-3.0-only
"""Check dependent patch prefixes without modifying the upstream tree."""
from difflib import unified_diff
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ApplyPatchesCheckTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "upstream"
        self.source.mkdir()
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.script = scripts / "apply-patches.sh"
        shutil.copyfile(ROOT / "scripts/apply-patches.sh", self.script)
        self.patches = self.root / "patches/libreoffice"
        self.patches.mkdir(parents=True)
        self.names = ["A.patch", "B.patch", "C.patch"]
        (self.patches / "series").write_text("\n".join(self.names) + "\n", encoding="utf-8")

        base = {"marker.txt": "original\n", "dependency.txt": "header\n",
                "tail.txt": "tail original\n"}
        after_a = {**base, "marker.txt": "A applied\n"}
        after_b = {**after_a, "dependency.txt": "header\nB added\n"}
        # C needs B's added line. Repeated text lets two hunks reverse on [A],
        # corrupting A and making B look applied, while the tail hunk fails.
        after_c = {"marker.txt": "A applied\nA applied\n",
                   "dependency.txt": "header\nheader\n", "tail.txt": "C updated\n"}
        states = [base, after_a, after_b, after_c]
        for name, before, after in zip(self.names, states, states[1:]):
            patch = "".join(
                "".join(unified_diff(before[path].splitlines(keepends=True),
                                     after[path].splitlines(keepends=True),
                                     fromfile=f"a/{path}", tofile=f"b/{path}", n=0))
                for path in base
            )
            (self.patches / name).write_text(patch, encoding="utf-8")
        for name, content in {**base, "untouched.txt": "keep me\n"}.items():
            (self.source / name).write_text(content, encoding="utf-8")

    def apply(self, *names):
        for name in names:
            result = subprocess.run(
                ["patch", "-d", str(self.source), "-p1", "-s", "-f", "--fuzz=0"],
                input=(self.patches / name).read_text(encoding="utf-8"),
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def snapshot(self):
        return {
            path.relative_to(self.source): (path.read_bytes() if path.is_file() else None,
                                            path.stat().st_mode, path.stat().st_mtime_ns)
            for path in [self.source, *self.source.rglob("*")]
        }

    def check(self, expected_code, expected_lines):
        before = self.snapshot()
        result = subprocess.run(
            ["bash", str(self.script), "--check"],
            env={**os.environ, "HST_LO_SRC": str(self.source)},
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(self.snapshot(), before, "--check changed the upstream tree")
        self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), expected_lines)
        self.assertEqual(result.stderr, "")

    def test_prefix_a_with_dependent_tail(self):
        self.apply("A.patch")
        self.check(0, ["already applied: A.patch", "applies cleanly: B.patch",
                       "applies cleanly: C.patch"])

    def test_prefix_a_b(self):
        self.apply("A.patch", "B.patch")
        self.check(0, ["already applied: A.patch", "already applied: B.patch",
                       "applies cleanly: C.patch"])

    def test_complete_series(self):
        self.apply(*self.names)
        self.check(0, [f"already applied: {name}" for name in self.names])

    def test_b_without_a_is_inconsistent(self):
        self.apply("B.patch")
        self.check(1, ["inconsistent tree: A.patch is not applied but a later patch is"])


if __name__ == "__main__":
    unittest.main()
