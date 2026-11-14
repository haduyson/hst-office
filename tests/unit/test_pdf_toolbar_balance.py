# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF's two toolbar rows beside the banner are one grid (hst-pdf-toolbar-balance.patch): both rows share
the group columns, the separators and the menu button run across both rows, so the rows end together."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCH = "hst-pdf-toolbar-balance.patch"
UI = "xmlsecurity/uiconfig/ui/hstpdfviewer.ui"


def grid_children(ui):
    """[(id, left, top, height)] of the toolbar grid's direct children."""
    grid = ui[ui.index('<object class="GtkGrid" id="toolbar">'):]
    grid = grid[:grid.index("\n          </object>\n")]  # the grid's own children only
    result = []
    for match in re.finditer(r'(?ms)^ {12}<child>\n {14}<object class="[^"]+" id="([^"]+)">.*?^ {14}<packing>(.*?)</packing>',
                             grid):
        packing = match.group(2)
        number = lambda name, default=0: int(re.search(rf'"{name}">(\d+)<', packing).group(1)) \
            if re.search(rf'"{name}">', packing) else default
        result.append((match.group(1), number("left-attach"), number("top-attach"), number("height", 1)))
    return result


def ui_after_series():
    """The .ui file as the series builds it: every patch's section of it, applied in series order."""
    patches = os.path.join(ROOT, "patches", "libreoffice")
    names = [n.strip() for n in open(os.path.join(patches, "series"), encoding="utf-8")
             if n.strip() and not n.startswith("#")]
    with tempfile.TemporaryDirectory() as tree:
        for name in names[:names.index(PATCH) + 1]:
            text = open(os.path.join(patches, name), encoding="utf-8").read()
            sections = re.split(r"(?m)^(?=--- (?:a/|/dev/null))", text)
            part = "".join(x for x in sections if re.search(r"(?m)^\+\+\+ b/" + re.escape(UI) + r"\s*$", x))
            if part:
                run = subprocess.run(["patch", "-d", tree, "-p1", "-s", "-f"], input=part, capture_output=True,
                                     text=True)
                if run.returncode:
                    raise AssertionError(f"{name}: {run.stdout}{run.stderr}")
        return open(os.path.join(tree, UI), encoding="utf-8").read()


@unittest.skipUnless(shutil.which("patch"), "no patch tool")
class PdfToolbarGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = ui_after_series()

    def setUp(self):
        self.children = grid_children(self.ui)

    def test_columns_hold_one_group_per_row(self):
        cells = {(left, top): ident for ident, left, top, height in self.children if height == 1}
        self.assertEqual(cells, {(0, 0): "toolfile", (0, 1): "toolpages", (2, 0): "toolzoom", (2, 1): "toolfind",
                                 (4, 0): "tooledit", (4, 1): "toolsign"})

    def test_separators_and_menu_span_both_rows(self):
        spanning = {ident: left for ident, left, top, height in self.children if height == 2}
        self.assertEqual(spanning, {"sep1": 1, "sep2": 3, "sep3": 5, "menu": 6})

    def test_every_control_kept_once(self):
        for ident in ("open", "print", "savecopy", "zoomout", "zoom", "zoomin", "fitpage", "fitwidth", "rotate",
                      "prevpage", "pagelabel", "page", "pagecount", "nextpage", "search", "findprev", "findnext",
                      "edit", "sign", "menu"):
            self.assertEqual(self.ui.count(f'id="{ident}"'), 1, ident)
        self.assertNotIn('id="toolrow1"', self.ui)

    def test_shorter_row_fills_its_column(self):
        for box, control in (("toolfind", "search"), ("toolpages", "page"), ("toolsign", "sign")):
            part = self.ui[self.ui.index(f'id="{box}"'):]
            block = part[part.index(f'id="{control}"'):]
            self.assertRegex(block[:block.index("</packing>")], r'"expand">True<', control)


if __name__ == "__main__":
    unittest.main()
