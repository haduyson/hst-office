# SPDX-License-Identifier: AGPL-3.0-only
"""hst-menubar-parked-tab.patch: after .uno:ToolbarMode applied a mode without a ribbon, every frame of the module
shows its menubar again (a tab parked while its module went through ribbon modes came back without it).
GUI: tests/runtime/check-ui-mode-tabs.py (menubar judged on every tab)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-menubar-parked-tab.patch"
SCENARIO = ROOT / "tests/runtime/ui_mode_tabs_scenario.py"


class MenubarParkedTab(unittest.TestCase):
    def test_in_series(self):
        self.assertIn(PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())

    def test_toolbar_mode_shows_the_module_menubars(self):
        text = PATCH.read_text(encoding="utf-8")
        self.assertIn("+++ b/sfx2/source/appl/appserv.cxx", text)
        added = [line[1:].strip() for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")]
        self.assertIn("if (xCurrentFrame.is() && !sfx2::SfxNotebookBar::IsActiveFor(xCurrentFrame))", added)
        self.assertIn("sfx2::SfxNotebookBar::ShowMenubarForModuleOf(xCurrentFrame, true);", added)

    def test_scenario_judges_the_menubar_everywhere(self):
        text = SCENARIO.read_text(encoding="utf-8")
        self.assertNotIn("menubar=(", text)
        self.assertNotIn("dict(state, menubar=True)", text)


if __name__ == "__main__":
    unittest.main()
