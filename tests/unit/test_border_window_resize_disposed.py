# SPDX-License-Identifier: AGPL-3.0-only
"""hst-border-window-resize-disposed.patch: a border window that is being disposed ignores Resize.

Closing a Writer document over UNO crashed in ImplBorderWindow::Resize: dispose() resets the border view, then the
ribbon banner's dispose joins its workers with the SolarMutex released and the main thread runs a posted event that
resizes the half-disposed border window (null border view). GUI check under CPU load:
tests/runtime/check-nd30-insertion-point.py (read_only scenario: store, then close). Offline: the patch hunk."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-border-window-resize-disposed.patch"
SERIES = ROOT / "patches/libreoffice/series"


def hunk(path):
    for part in PATCH.read_text(encoding="utf-8").split("\n--- a/")[1:]:
        lines = part.splitlines()
        if lines[0] == path:
            return lines[1:]
    raise AssertionError(f"no hunk for {path}")


class BorderWindowResizeDisposed(unittest.TestCase):
    def test_patch_in_series_after_the_banner_patch(self):
        names = SERIES.read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, names)
        self.assertGreater(names.index(PATCH.name), names.index("hst-banner-always-visible.patch"))

    def test_resize_returns_first_when_disposed(self):
        lines = hunk("vcl/source/window/brdwin.cxx")
        start = lines.index(" void ImplBorderWindow::Resize()")
        body = [line[1:].strip() for line in lines[start + 2:] if line.startswith(("+", " "))]
        code = [line for line in body if line and not line.startswith("//")]
        self.assertEqual(code[:2], ["if (isDisposed())", "return;"])
        self.assertEqual(code[2], "Size aSize = GetOutputSizePixel();")

    def test_only_additions(self):
        lines = hunk("vcl/source/window/brdwin.cxx")
        self.assertFalse([line for line in lines if line.startswith("-") and not line.startswith("---")])


if __name__ == "__main__":
    unittest.main()
