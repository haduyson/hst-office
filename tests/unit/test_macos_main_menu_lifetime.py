# SPDX-License-Identifier: AGPL-3.0-only
"""macOS: the application's main menu lives as long as the application (hst-macos-main-menu-lifetime.patch).

Headless, closing the last document over UNO restored the default menu on a deallocated SalNSMainMenu (Signal 11 in
AquaSalMenu::setDefaultMenu). The runtime check is tests/runtime/check-close-last-doc.py in the macOS save replace
probe; these tests keep the patch, its place in the series and the probe step from going away."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches" / "libreoffice"
PATCH = PATCHES / "hst-macos-main-menu-lifetime.patch"
PROBE = ROOT / ".github" / "workflows" / "macos-save-replace-probe.yml"


class MainMenuLifetime(unittest.TestCase):
    def test_patch_is_in_the_series(self):
        series = [line.split()[0] for line in (PATCHES / "series").read_text().splitlines()
                  if line.strip() and not line.startswith("#")]
        self.assertIn(PATCH.name, series)

    def test_main_menu_is_not_autoreleased(self):
        text = PATCH.read_text()
        self.assertIn("+++ b/vcl/osx/salmenu.cxx", text)
        added = [l for l in text.splitlines() if l.startswith("+") and "SalNSMainMenu alloc" in l]
        removed = [l for l in text.splitlines() if l.startswith("-") and "SalNSMainMenu alloc" in l]
        self.assertEqual(len(added), 1)
        self.assertNotIn("autorelease", added[0])
        self.assertEqual(len(removed), 1)
        self.assertIn("autorelease", removed[0])

    def test_probe_runs_the_close_check(self):
        text = PROBE.read_text()
        self.assertIn("tests/runtime/check-close-last-doc.py", text)
        self.assertTrue((ROOT / "tests" / "runtime" / "check-close-last-doc.py").is_file())
        # a failure of the save check must not skip the close check
        step = re.search(r"- name: Check closing the last document\n(.*?)\n      - name:", text, re.S)
        self.assertIsNotNone(step)
        self.assertIn("always()", step.group(1))

    def test_close_check_closes_the_only_document_first(self):
        text = (ROOT / "tests" / "runtime" / "check-close-last-doc.py").read_text()
        self.assertRegex(text, r'CASES = \[\n    \("Writer, close\(True\)", "private:factory/swriter", "close"\)')
        self.assertIn("doc.close(True)", text)


if __name__ == "__main__":
    unittest.main()
