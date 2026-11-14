# SPDX-License-Identifier: AGPL-3.0-only
"""hst-gtk-clipboard-main-thread.patch: gtk3 clipboard queries never wait for gtk off the main thread.

A UNO-driven office hung for good when a Paste state built on the request thread called
gtk_clipboard_wait_for_targets there. GUI proof: tests/runtime/check-ui-mode-cycle-stress.py (no hang)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-gtk-clipboard-main-thread.patch"


class GtkClipboardMainThread(unittest.TestCase):
    def test_in_series(self):
        self.assertIn(PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())

    def test_targets_off_the_main_thread_come_from_the_cache(self):
        text = PATCH.read_text(encoding="utf-8")
        added = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        # no Paste state waits for gtk or releases the SolarMutex, on any thread
        self.assertIn("// HST: on every thread, see HstClipboardTargets", added)
        self.assertIn("return rTargets.aFlavors;", added)
        self.assertIn("m_aMimeTypeToGtkType = rTargets.aTypes;", added)
        self.assertEqual(added.count("vcl::solarthread::syncExecute("), 1)  # the data of a paste only
        self.assertIn("return getTransferData(rFlavor);", added)
        self.assertNotIn("return getTransferDataFlavorsAsVector();", added)
        # kept fresh from the main thread without a nested loop
        self.assertIn("gtk_clipboard_request_targets(", added)
        self.assertIn("g_idle_add_full(", added)
        self.assertNotIn("gtk_clipboard_wait_for_targets(", added)
        self.assertIn("hstRequestTargets(GetSelectionType());", added)
        removed = "\n".join(line[1:] for line in text.splitlines() if line.startswith("-") and not line.startswith("---"))
        self.assertIn("if (gtk_clipboard_wait_for_targets(clipboard, &targets, &n_targets))", removed)


if __name__ == "__main__":
    unittest.main()
