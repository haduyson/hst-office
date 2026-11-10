# SPDX-License-Identifier: AGPL-3.0-only
"""hst-hide-base-launchers.patch: HST Base is offered nowhere (Windows Start menu, File ▸ New and the menus built from
it, Linux app menus and the HST Office launcher's actions) while .odb files still open with it.

Offline: what the patch removes and adds; no other HST launcher (Windows desktop, macOS) is made for Base. With
HST_LO_SRC set to a patched tree, that tree is checked as a whole."""
import importlib.util
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
PATCH = PATCHES / "hst-hide-base-launchers.patch"
SCP = "scp2/source/base/folderitem_base.scp"
XCU = "officecfg/registry/data/org/openoffice/Office/Common.xcu"
BASE_DESKTOP, START_DESKTOP = "sysui/desktop/menus/base.desktop", "sysui/desktop/menus/startcenter.desktop"


def changes(patch):
    out, current = {}, None
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current[0].append(line[1:])
        elif current is not None and line.startswith("+"):
            current[1].append(line[1:])
    return out


class HideBase(unittest.TestCase):
    def setUp(self):
        self.changes = changes(PATCH)

    def test_in_the_series_after_the_desktop_shortcuts(self):
        series = (PATCHES / "series").read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, series)
        self.assertLess(series.index("hst-msi-app-desktop-shortcuts.patch"), series.index(PATCH.name))

    def test_start_menu_entry_removed(self):
        removed, added = self.changes[SCP]
        self.assertIn("FolderItem gid_Folderitem_Sbase", removed)
        self.assertIn('    Name = "HST Base";', removed)
        self.assertIn("FolderItemProperty gid_Fip_Sbase_AppID", removed)
        self.assertFalse([line for line in added if re.match(r"\s*(FolderItem|File)\b", line)])

    def test_file_new_has_no_database(self):
        removed, added = self.changes[XCU]
        self.assertIn("          <value>private:factory/sdatabase?Interactive</value>", removed)
        self.assertEqual(added, [])

    def test_linux_launcher_hidden_and_no_base_action(self):
        self.assertEqual(self.changes[BASE_DESKTOP], ([], ["NoDisplay=true"]))
        removed, added = self.changes[START_DESKTOP]
        self.assertIn("[Desktop Action Base]", removed)
        self.assertEqual(added, ["Actions=Writer;Calc;Impress;Draw;Math;"])

    def test_no_new_base_launcher_anywhere(self):
        desktop = (PATCHES / "hst-msi-app-desktop-shortcuts.patch").read_text(encoding="utf-8")
        self.assertNotIn("Sbase", desktop)
        self.assertNotIn("HST Base", desktop)
        spec = importlib.util.spec_from_file_location("make_app_launchers", ROOT / "scripts/macos/make-app-launchers.py")
        make = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make)
        self.assertNotIn("base", [module for module, *_ in make.LAUNCHERS])


@unittest.skipUnless(os.environ.get("HST_LO_SRC"), "HST_LO_SRC (a patched tree) not set")
class PatchedTree(unittest.TestCase):
    def setUp(self):
        self.tree = Path(os.environ["HST_LO_SRC"])

    def read(self, rel):
        return (self.tree / rel).read_text(encoding="utf-8")

    def test_no_base_entry_point(self):
        self.assertNotIn("FolderItem ", self.read(SCP))
        menus = self.read(XCU)
        new_menu = menus[menus.index('<node oor:name="New">'):menus.index('<node oor:name="Wizard">')]
        self.assertNotIn("sdatabase", new_menu)
        self.assertIn("private:factory/swriter", new_menu)
        base = self.read(BASE_DESKTOP)
        self.assertIn("\nNoDisplay=true\n", base)
        self.assertIn("application/vnd.oasis.opendocument.base;", base)
        start = self.read(START_DESKTOP)
        self.assertNotIn("Base", re.search(r"^Actions=(.*)$", start, re.M).group(1).split(";"))
        self.assertNotIn("--base", start)


if __name__ == "__main__":
    unittest.main()
