# SPDX-License-Identifier: AGPL-3.0-only
"""Every LibreOffice patch file is listed in the series, and every series entry exists."""
from pathlib import Path
import unittest


PATCHES = Path(__file__).resolve().parents[2] / "patches/libreoffice"


class PatchSeriesCompleteTest(unittest.TestCase):
    def setUp(self):
        lines = (PATCHES / "series").read_text(encoding="utf-8").splitlines()
        self.series = [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    def test_every_patch_file_is_applied(self):
        # apply-patches.sh reads only the series: an unlisted patch is silently left out of the build
        files = {path.name for path in PATCHES.glob("*.patch")}
        self.assertEqual(sorted(files - set(self.series)), [])

    def test_every_series_entry_exists(self):
        self.assertEqual([name for name in self.series if not (PATCHES / name).is_file()], [])

    def test_no_entry_is_listed_twice(self):
        self.assertEqual(sorted({n for n in self.series if self.series.count(n) > 1}), [])


if __name__ == "__main__":
    unittest.main()
