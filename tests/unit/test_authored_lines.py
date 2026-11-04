# SPDX-License-Identifier: AGPL-3.0-only
"""The authoring gate covers committed, edited and newly created Python, including tests/scripts."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _paths import ROOT


class AuthoredLinesTests(unittest.TestCase):
    def test_branch_and_worktree_changes_are_checked_without_gating_untouched_legacy(self):
        spec = importlib.util.spec_from_file_location("authored_lines", Path(ROOT) / "scripts/check-authored-lines.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
            git("init")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "legacy.py").write_text("# old\n" * 200)
            (root / "edited.py").write_text("# old\n")
            git("add", ".")
            git("commit", "-m", "test: base")
            base = git("rev-parse", "HEAD")
            (root / "committed.py").write_text("# new\n" * 199)
            git("add", ".")
            git("commit", "-m", "test: branch")
            self.assertTrue(gate.check(root, base))
            with patch.dict(os.environ, {"HST_AUTHORING_BASE": base}):
                self.assertTrue(gate.check(root))
            (root / "committed.py").write_text("# new\n" * 198)
            self.assertFalse(gate.check(root, base))
            (root / "edited.py").write_text("# edited\n" * 199)
            self.assertTrue(gate.check(root, base))
            (root / "edited.py").write_text("# edited\n")
            (root / "untracked.py").write_text("# new\n" * 199)
            self.assertTrue(gate.check(root, base))
            self.assertEqual(gate.changed(root, base), ["committed.py", "edited.py", "untracked.py"])
