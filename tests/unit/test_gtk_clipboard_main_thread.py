# SPDX-License-Identifier: AGPL-3.0-only
"""hst-gtk-clipboard-main-thread.patch: gtk3 clipboard queries off the main thread run on the main thread.

A UNO-driven office hung for good when a Paste state built on the request thread called
gtk_clipboard_wait_for_targets there. GUI proof: tests/runtime/check-ui-mode-cycle-stress.py (no hang)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-gtk-clipboard-main-thread.patch"


class GtkClipboardMainThread(unittest.TestCase):
    def test_in_series(self):
        self.assertIn(PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())

    def test_both_queries_hand_over_to_the_main_thread(self):
        text = PATCH.read_text(encoding="utf-8")
        added = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        self.assertEqual(added.count("if (!Application::IsMainThread())"), 2)
        self.assertEqual(added.count("vcl::solarthread::syncExecute("), 2)
        self.assertEqual(added.count("SolarMutexGuard aGuard;"), 2)
        self.assertIn("return getTransferData(rFlavor);", added)
        self.assertIn("return getTransferDataFlavorsAsVector();", added)
        self.assertIn("#include <vcl/threadex.hxx>", added)


if __name__ == "__main__":
    unittest.main()
