# SPDX-License-Identifier: AGPL-3.0-only
"""How the extension registers "Phiên bản trước" (job events, command in the File menu, schema, options page), the
3-minute AutoRecovery default, and the Vietnamese texts with their size and time formats."""
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

import test_version_config
from install_id_support import DLG, EXT, OOR
from hst_office import version_config as config
from hst_office import version_options as opts
from hst_office import version_texts as T


class Registration(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(EXT, name), encoding="utf-8") as handle:
            return handle.read()

    def test_job_runs_on_modify_save_and_unload(self):
        root = ET.fromstring(self.read("Jobs.xcu"))
        events = {n.get(OOR + "name") for n in root.iter("node")
                  if any(c.get(OOR + "name") == "org.hst.office.vi.PreviousVersionsJob" for c in n.iter("node"))
                  and n.get(OOR + "name") not in ("Events", "Jobs", "JobList", "org.hst.office.vi.PreviousVersionsJob")}
        self.assertEqual(events, {"OnModifyChanged", "OnSave", "OnUnload"})
        component = self.read(os.path.join("python", "hst_office_component.py"))
        self.assertIn('("version_job", "PreviousVersionsJob", "org.hst.office.vi.PreviousVersionsJob", JOB)', component)
        self.assertIn('("version_options", "PreviousVersionsOptionsHandler", "%s"' % opts.HANDLER_NAME, component)

    def test_file_menu_entry_in_writer_sheets_and_slides(self):
        addons = self.read("Addons.xcu")
        self.assertIn("<value>.uno:PickList\\.uno:VersionDialog</value>", addons)
        self.assertIn("<value>org.hst.office.vi:PreviousVersions</value>", addons)
        block = addons[addons.index("OfficeMenuBarMerging"):addons.index("OfficeHelp")]
        for module in ("TextDocument", "SpreadsheetDocument", "PresentationDocument"):
            self.assertIn(module, block)
        from hst_office import dispatch
        self.assertIn("PreviousVersions", dispatch.ACTION_COMMANDS)  # needs a document, like the other tools
        self.assertIn('"PreviousVersions": previous_versions,', self.read(os.path.join("python", "hst_office",
                                                                                       "actions.py")))
        for code in ("vi", "en"):
            self.assertEqual(json.loads(self.read(os.path.join("locales", code + ".json")))["menu"]["previousVersions"],
                             "Phiên bản trước")
        self.assertIn("org.hst.office.vi:PreviousVersions", self.read("FeatureSearch.xcu"))

    def test_schema_default_and_manifest(self):
        schema = ET.fromstring(self.read("previousversions.xcs"))
        self.assertEqual((schema.get(OOR + "name"), schema.get(OOR + "package")),
                         ("PreviousVersions", "org.hasontech.hstoffice"))
        prop = next(p for p in schema.iter("prop") if p.get(OOR + "name") == "Enabled")
        self.assertEqual(prop.find("value").text, "true")
        self.assertEqual(config.PATH, "/org.hasontech.hstoffice.PreviousVersions")
        manifest = self.read(os.path.join("META-INF", "manifest.xml"))
        self.assertIn('full-path="previousversions.xcs"', manifest)
        self.assertIn('full-path="RecoveryDefaults.xcu"', manifest)

    def test_autorecovery_every_three_minutes_without_saving_the_users_file(self):
        root = ET.fromstring(self.read("RecoveryDefaults.xcu"))
        self.assertEqual((root.get(OOR + "name"), root.get(OOR + "package")), ("Recovery", "org.openoffice.Office"))
        props = {p.get(OOR + "name"): p.find("value").text for p in root.iter("prop")}
        self.assertEqual(props, {"TimeIntervall": "3", "UserAutoSaveEnabled": "false"})

    def test_user_texts_are_vietnamese_and_name_no_other_product(self):
        texts = [v for k, v in vars(T).items() if k.isupper() and isinstance(v, str)] + list(T.ERRORS.values())
        texts += [c.get(DLG + "value") or "" for c in test_version_config.OptionsPage.controls(self).values()]
        joined = " ".join(texts)
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint|LibreOffice|OpenOffice", joined))
        self.assertIn("Khôi phục", joined)


class Formatting(unittest.TestCase):
    def test_sizes_and_times(self):
        self.assertEqual(T.format_size(512), "512 byte")
        self.assertEqual(T.format_size(1536), "1,5 KB")
        self.assertEqual(T.format_size(1024 * 1024), "1 MB")
        self.assertEqual(T.format_size(int(1.25 * 1024 * 1024)), "1,2 MB")
        self.assertEqual(T.format_size(150 * 1024 * 1024), "150 MB")
        self.assertEqual(T.format_size(2 * 1024 ** 3), "2 GB")
        import time
        self.assertEqual(T.format_time(0, time.gmtime), "01/01/1970 00:00:00")
        self.assertEqual(T.usage_label(0, 0, 0), "Chưa có phiên bản nào được lưu.")


if __name__ == "__main__":
    unittest.main()
