# SPDX-License-Identifier: AGPL-3.0-only
"""A later macOS commit may change the workflow checker, which spans check-workflows.py and its rules module."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/release/macos-commit-paths.sh"


def allowed(paths):
    return subprocess.run(["bash", str(SCRIPT)], input="\n".join(paths) + "\n", text=True,
                          capture_output=True, check=False).returncode == 0


class CheckerPathTests(unittest.TestCase):
    def test_both_checker_modules_are_ci_definitions(self):
        self.assertTrue(allowed(["scripts/check-workflows.py", "scripts/workflow_build_rules.py"]))

    def test_only_the_exact_rules_module_is_admitted(self):
        for path in ("scripts/workflow_build_rules.pyc", "scripts/workflow_build_rules.py.bak",
                     "scripts/extension_package_files.py"):
            with self.subTest(path=path):
                self.assertFalse(allowed(["docs/CI.md", path]))


if __name__ == "__main__":
    unittest.main()
