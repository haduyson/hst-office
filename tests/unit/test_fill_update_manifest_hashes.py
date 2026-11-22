# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""fill-update-manifest-hashes.py: the 1.0.2 feed draft becomes signed-ready feeds only with the real installers."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from _paths import ROOT
from hst_office import update_logic

SCRIPT = Path(ROOT) / "scripts" / "release" / "fill-update-manifest-hashes.py"
DRAFT = Path(ROOT) / "docs" / "releases" / "v1.0.2-update-draft"
SPEC = importlib.util.spec_from_file_location("fill_update_manifest_hashes", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
NAMES = ("HSTOffice_1.0.2_Win_x86-64_en-US_vi.msi", "HSTOffice_1.0.2_macOS_arm64.dmg",
         "HSTOffice_1.0.2_macOS_x86_64.dmg", "HSTOffice_1.0.2_Linux_x86-64.deb",
         "HSTOffice_1.0.2_Linux_x86-64.rpm", "HSTOffice_1.0.2_Linux_x86-64.AppImage")


class FillUpdateManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.assets = self.tmp / "assets"
        self.assets.mkdir()
        for index, name in enumerate(NAMES):
            (self.assets / name).write_bytes(("installer %d %s" % (index, name)).encode() * (index + 1))
        self.out = self.tmp / "out"
        # The 1.0.2 draft as the generator writes it now: latest-2.json without the Windows installer (its Windows
        # readers, up to 1.0.1, cannot run the updater).
        self.draft = self.tmp / "draft-1.0.2"
        shutil.copytree(DRAFT, self.draft)
        legacy = json.loads((self.draft / "latest-2.json").read_text(encoding="utf-8"))
        for release in legacy["channels"].values():
            if release:
                release.get("installers", {}).pop("windows", None)
        (self.draft / "latest-2.json").write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")

    def test_draft_is_the_1_0_2_stable_release_with_placeholders(self):
        version, names = MOD.draft_installers(DRAFT)
        self.assertEqual(version, "1.0.2")
        self.assertEqual(sorted(names), sorted(NAMES))
        notes = json.loads((DRAFT / "latest-2.json").read_text(encoding="utf-8"))["channels"]["stable"]["notes"]
        self.assertEqual(notes, "https://office.hasontech.vn/diem-moi/#v1.0.2")

    def test_fills_every_installer_and_keeps_the_rest_of_the_draft(self):
        outputs = MOD.fill(self.draft, self.assets, self.out)
        self.assertEqual([p.name for p in outputs], ["latest-3.json", "latest-2.json", "latest.json"])
        for path in outputs:
            data = path.read_bytes()
            update_logic.parse_manifest(data)  # what installed clients accept
            doc = json.loads(data)
            self.assertEqual(MOD.blank(doc), json.loads((self.draft / path.name).read_text(encoding="utf-8")))
            for entry in doc["channels"]["stable"].get("installers", {}).values():
                body = (self.assets / entry["url"].rsplit("/", 1)[-1]).read_bytes()
                self.assertEqual(entry["sha256"], hashlib.sha256(body).hexdigest())
                self.assertEqual(entry["size"], len(body))
        sums = (self.out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sorted(line.split("  ")[1] for line in sums), sorted(NAMES))

    def test_missing_installer_is_refused(self):
        os.remove(self.assets / NAMES[2])
        with self.assertRaisesRegex(MOD.FillError, "missing installer"):
            MOD.fill(self.draft, self.assets, self.out)

    def test_build_checksum_disagreeing_with_the_file_is_refused(self):
        (self.assets / "SHA256SUMS").write_text("%s  %s\n" % ("0" * 64, NAMES[0]), encoding="utf-8")
        with self.assertRaisesRegex(MOD.FillError, "differs from the file"):
            MOD.fill(self.draft, self.assets, self.out)

    def test_wrong_release_name_is_refused(self):
        os.rename(self.assets / NAMES[3], self.assets / "HSTOffice_1.0.1_Linux_x86-64.deb")
        with self.assertRaises(MOD.FillError):
            MOD.fill(self.draft, self.assets, self.out)

    def test_draft_edited_after_review_is_refused(self):
        draft = self.tmp / "draft"
        shutil.copytree(self.draft, draft)
        doc = json.loads((draft / "latest.json").read_text(encoding="utf-8"))
        doc["channels"]["stable"]["downloads"]["linux"] = "https://office.hasontech.vn/#tai-ve"
        (draft / "latest.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MOD.FillError, "differs from the reviewed draft"):
            MOD.fill(draft, self.assets, self.out)

    def test_filled_draft_is_not_accepted_as_a_draft(self):
        draft = self.tmp / "draft"
        shutil.copytree(self.draft, draft)
        doc = json.loads((draft / "latest-2.json").read_text(encoding="utf-8"))
        doc["channels"]["stable"]["installers"]["linux"]["size"] = 5
        (draft / "latest-2.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MOD.FillError, "not a placeholder"):
            MOD.draft_installers(draft)

    def test_draft_cannot_be_published_unfilled(self):
        with self.assertRaises(update_logic.ManifestError):
            update_logic.parse_manifest((DRAFT / "latest-2.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
