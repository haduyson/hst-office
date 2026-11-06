# SPDX-License-Identifier: AGPL-3.0-only
"""check-msi-file-versions.py: no executable listed at or below beta 1-4's version, so the upgrade keeps it."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_msi_file_versions", ROOT / "scripts/check-msi-file-versions.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def f(component, name, version):
    return {"File": name, "Component_": component, "FileName": name, "Version": version}


class Rules(unittest.TestCase):
    def test_series_sets_a_floor_above_the_betas(self):
        self.assertEqual(MOD.floor_errors(MOD.PATCH.read_text(encoding="utf-8")), [])
        self.assertIn(MOD.PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())
        for bad in ("", "+            FILEVERSIONFLOOR 26.8.1.1\n", "+            FILEVERSIONFLOOR 1.0.0.500\n"):
            self.assertTrue(MOD.floor_errors(bad), bad)

    def test_executables_at_or_below_the_betas_are_reported(self):
        # The beta.5 candidates listed soffice.com at 1.0.0.500 while beta.4 left 26.8.1.1 on disk.
        files = [f("c1", "SOFFICE.COM|soffice.com", "1.0.0.500"), f("c2", "python.exe", "3.13.15150.1013"),
                 f("c3", "sc.dll", "26.8.1.2"), f("c4", "font.ttf", "2.37.0.0"), f("c5", "readme.txt", "")]
        self.assertEqual(MOD.below_floor(files), ["python.exe", "soffice.com"])

    def test_merge_module_files_are_not_ours(self):
        files = [f("vcruntime140.dll_system_amd64.X", "vcruntime140.dll", "14.44.35211.0"), f("c1", "a.dll", "26.8.1.2")]
        self.assertEqual(MOD.below_floor(MOD.own_files(files, {"vcruntime140.dll_system_amd64.X"})), [])

    def test_versions_going_down_against_an_older_msi(self):
        old = [f("c1", "soffice.com", "26.8.1.1"), f("c2", "x.dll", "3.0.0.0")]
        new = [f("c1", "soffice.com", "1.0.0.500"), f("c2", "x.dll", "3.0.0.0")]
        self.assertEqual(MOD.downgraded(new, old), ["soffice.com 26.8.1.1 -> 1.0.0.500"])
        floored = [f("c1", "soffice.com", "26.8.1.2"), f("c2", "x.dll", "26.8.1.2")]
        self.assertEqual(MOD.downgraded(floored, old), [])

    def test_version_keys_pad_missing_fields(self):
        self.assertLess(MOD.key("26.8.1.1"), MOD.key("26.8.1.2"))
        self.assertEqual(MOD.key("1.0"), (1, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
