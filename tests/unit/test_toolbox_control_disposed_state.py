# SPDX-License-Identifier: AGPL-3.0-only
"""hst-toolbox-control-disposed-state.patch: a toolbar control ignores a state that arrives after it and its toolbox
were disposed.

Cycling the user interface modes crashed in ToolBox::GetItemRect: the paste control's first state (asked from the
toolbar's delayed controller update) waits for the system clipboard with the SolarMutex released, a mode switch on
the UNO request thread destroys the toolbar meanwhile, and the state then reached the disposed control. GUI stress:
tests/runtime/check-ui-mode-cycle-stress.py. Offline: the patch hunk."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-toolbox-control-disposed-state.patch"
SERIES = ROOT / "patches/libreoffice/series"
STRESS = ROOT / "tests/runtime/check-ui-mode-cycle-stress.py"


def hunks():
    """{path: lines of its hunk}"""
    out = {}
    for part in PATCH.read_text(encoding="utf-8").split("\n--- a/")[1:]:
        lines = part.splitlines()
        out[lines[0]] = lines[1:]
    return out


def added(lines):
    return [line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")]


class ToolboxControlDisposedState(unittest.TestCase):
    def test_patch_in_series_after_the_ui_mode_patches(self):
        names = SERIES.read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, names)
        self.assertGreater(names.index(PATCH.name), names.index("hst-ui-mode-per-tab.patch"))

    def test_status_changed_returns_for_a_disposed_control_or_toolbox(self):
        lines = hunks()["sfx2/source/toolbox/tbxitem.cxx"]
        new = added(lines)
        guard = [line for line in new if line.strip().startswith("if (")]
        self.assertEqual(len(guard), 1)
        for part in ("m_bDisposed", "!pImpl->pBox", "pImpl->pBox->isDisposed()"):
            self.assertIn(part, guard[0])
        self.assertIn("return;", new[new.index(guard[0]) + 1])
        # the guard sits right after the SolarMutexGuard of statusChanged, before any use of the toolbox or frame
        context = [line for line in lines if line.startswith(" ")]
        self.assertTrue(any("SolarMutexGuard aGuard;" in line for line in context))
        self.assertFalse([line for line in lines if line.startswith("-") and not line.startswith("---")])

    def test_update_controllers_walks_a_copy_of_the_controllers(self):
        lines = hunks()["framework/source/uielement/toolbarmanager.cxx"]
        removed = [line[1:] for line in lines if line.startswith("-") and not line.startswith("---")]
        self.assertIn("        for (auto const& controller : m_aControllerMap)", removed)
        new = "\n".join(added(lines))
        self.assertIn("aControllers(\n            m_aControllerMap.begin(), m_aControllerMap.end() );", new)
        self.assertIn("for (auto const& controller : aControllers)", new)
        self.assertIn("m_aControllerMap.find( controller.first )", new)
        self.assertIn("pCurrent->second != controller.second", new)
        self.assertIn("m_bDisposed", new)

    def test_stress_check_runs_at_least_twenty_rounds(self):
        text = STRESS.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--rounds", type=int, default=20)', text)
        self.assertIn("NextDocumentTab", text)


if __name__ == "__main__":
    unittest.main()
