# SPDX-License-Identifier: AGPL-3.0-only
"""hst-document-tab-switch-present-first.patch: on Windows a tab switch shows the new tab window cloaked until it is
painted and presented, then uncloaks it and only then hides the previous tab (no blank frame, no desktop).
GUI: tests/runtime/check-windows-tab-switch-flash.py (every presented frame, DXGI Desktop Duplication)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-document-tab-switch-present-first.patch"


def added():
    return [line[1:].strip() for line in PATCH.read_text(encoding="utf-8").splitlines()
            if line.startswith("+") and not line.startswith("+++")]


class PresentFirst(unittest.TestCase):
    def test_in_series_after_the_no_flash_patch(self):
        names = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        self.assertGreater(names.index(PATCH.name), names.index("hst-document-tab-switch-no-flash.patch"))

    def test_cloak_then_present_then_park(self):
        lines = added()
        self.assertIn("pSet(pData->hWnd, 13 /* DWMWA_CLOAK */, &bValue, sizeof(bValue));", lines)
        start = lines.index("if (VclPtr<vcl::Window> pCloaked = std::move(m_pCloaked))")
        self.assertEqual(lines[start + 2:start + 6], ["lcl_paintNow(pCloaked);", "lcl_waitForComposition();",
                                                      "lcl_cloak(pCloaked, false);", "lcl_waitForComposition();"])
        self.assertIn("lcl_cloak(pTargetWindow, true);", lines)
        self.assertIn("lcl_cloak(pPending, false);", lines)

    def test_windows_only(self):
        text = PATCH.read_text(encoding="utf-8")
        self.assertIn("+#ifdef _WIN32", text)
        self.assertIn("+    (void)bCloak;", text)


if __name__ == "__main__":
    unittest.main()
