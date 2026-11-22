# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-recovery-first-copy-registered-modified.patch: a document already modified when AutoRecovery registers it gets
its first copy 30 s later, like one changed after registration (runtime: tests/runtime/check-recovery-first-copy.py)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
NAME = "hst-recovery-first-copy-registered-modified.patch"


def added(path):
    lines, current = [], False
    for line in (PATCHES / NAME).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            current = line == "+++ b/" + path
        elif current and line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


class FirstCopyOfARegisteredModifiedDocument(unittest.TestCase):
    def test_in_the_series_after_the_first_copy_rule(self):
        series = (PATCHES / "series").read_text(encoding="utf-8").split()
        self.assertIn(NAME, series)
        self.assertLess(series.index("hst-recovery-durability.patch"), series.index(NAME))

    def test_registering_a_modified_document_updates_the_timer(self):
        code = added("framework/source/services/autorecovery.cxx")
        self.assertIn("if ((aInfo.DocumentState & DocState::Modified) == DocState::Modified)", code)
        self.assertIn("implts_updateTimer();", code)
        self.assertLess(code.index("DocState::Modified"), code.index("implts_updateTimer();"))


if __name__ == "__main__":
    unittest.main()
