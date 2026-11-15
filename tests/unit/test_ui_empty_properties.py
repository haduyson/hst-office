# SPDX-License-Identifier: AGPL-3.0-only
"""No empty <property> in a .ui file of the patch series (hst-backstage-page-allocation.patch).

VclBuilder (Windows, macOS, gen) mis-nests the siblings after an object with a self-closing property such as
<property name="label"/>: the File panel's pages ended up inside its hidden Home page and showed blank. Upstream .ui
files have none, so what the series adds minus what it removes must be zero for every .ui file."""
import os
import re
import unittest

from _paths import ROOT
from patch_sections import sections

EMPTY = re.compile(r'<property name="[^"]*"\s*/>')
SERIES = os.path.join(ROOT, "patches", "libreoffice", "series")


def series():
    with open(SERIES, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


class EmptyProperties(unittest.TestCase):
    def test_no_empty_property_left(self):
        balance = {}
        for name in series():
            for path, lines in sections(name).items():
                if not path.endswith(".ui"):
                    continue
                for line in lines:
                    if line[:1] in "+-" and EMPTY.search(line):
                        balance[path] = balance.get(path, 0) + (1 if line[0] == "+" else -1)
        self.assertEqual({path: count for path, count in balance.items() if count}, {})

    def test_backstage_fix_is_in_the_series(self):
        self.assertIn("hst-backstage-page-allocation.patch", series())


if __name__ == "__main__":
    unittest.main()
