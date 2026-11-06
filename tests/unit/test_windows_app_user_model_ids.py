# SPDX-License-Identifier: AGPL-3.0-only
"""hst-windows-app-user-model-ids.patch: HST Office's own Windows AppUserModelIDs (taskbar groups, pinned shortcuts,
jump lists), so no TheDocumentFoundation.LibreOffice.<Module> id is left in the patched tree.

Offline (CI): every occurrence in the pinned 26.8.1.1 sources (UPSTREAM, counted in a tree with the earlier patches
applied) is removed by the patch and replaced one-for-one. With HST_LO_SRC set to a patched tree, that tree is
scanned as well; scripts/windows/check-app-user-model-ids.ps1 checks an installed MSI in windows-smoke."""
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-windows-app-user-model-ids.patch"
OLD, NEW = "TheDocumentFoundation.LibreOffice.", "HASONTECH.HSTOffice."
MODULES = {"Writer", "Calc", "Impress", "Draw", "Math", "Base", "Startcenter", "SafeMode"}
# file -> lines holding OLD in the pinned sources (no earlier HST patch adds or removes one)
UPSTREAM = {
    "framework/source/helper/titlebarupdate.cxx": 1, "scp2/inc/macros.inc": 1,
    "scp2/source/base/folderitem_base.scp": 1, "scp2/source/base/registryitem_base.scp": 1,
    "scp2/source/calc/folderitem_calc.scp": 1, "scp2/source/calc/registryitem_calc.scp": 4,
    "scp2/source/draw/folderitem_draw.scp": 1, "scp2/source/draw/registryitem_draw.scp": 4,
    "scp2/source/impress/folderitem_impress.scp": 1, "scp2/source/impress/registryitem_impress.scp": 4,
    "scp2/source/math/folderitem_math.scp": 1, "scp2/source/math/registryitem_math.scp": 2,
    "scp2/source/ooo/folderitem_ooo.scp": 3, "scp2/source/writer/folderitem_writer.scp": 1,
    "scp2/source/writer/registryitem_writer.scp": 7, "shell/source/win32/jumplist/JumpList.cxx": 3,
    "vcl/win/app/salinst.cxx": 1,
}
SCANNED = (".cxx", ".hxx", ".c", ".h", ".scp", ".inc", ".pm", ".py", ".mk")


def hunks():
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current[0].append(line[1:])
        elif current is not None and line.startswith("+"):
            current[1].append(line[1:])
    return out


class AppUserModelIds(unittest.TestCase):
    def test_appended_to_the_series(self):
        series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, series)

    def test_every_upstream_id_is_replaced_one_for_one(self):
        patched = hunks()
        self.assertEqual(set(patched), set(UPSTREAM))
        for path, (removed, added) in patched.items():
            self.assertEqual(sum(OLD in line for line in removed), UPSTREAM[path], path)
            self.assertFalse(any(OLD in line for line in added), path)
            self.assertEqual([line.replace(OLD, NEW) for line in removed], added, path)

    def test_ids_name_known_modules(self):
        ids = set()
        for _removed, added in hunks().values():
            for line in added:
                ids |= set(re.findall(r'HASONTECH\.HSTOffice\.([A-Za-z]+)"', line))
        self.assertTrue(ids <= MODULES, ids)
        self.assertTrue({"Writer", "Calc", "Impress", "Startcenter"} <= ids, ids)

    @unittest.skipUnless(os.environ.get("HST_LO_SRC"), "HST_LO_SRC (a patched tree) not set")
    def test_patched_tree_has_no_shared_id(self):
        tree = Path(os.environ["HST_LO_SRC"])
        left = []
        for directory, dirs, files in os.walk(tree):
            dirs[:] = [d for d in dirs if d not in ("workdir", "instdir", "external", "translations", "qa", ".git")]
            for name in files:
                if name.endswith(SCANNED):
                    path = Path(directory) / name
                    if OLD in path.read_text(encoding="utf-8", errors="replace"):
                        left.append(str(path.relative_to(tree)))
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
