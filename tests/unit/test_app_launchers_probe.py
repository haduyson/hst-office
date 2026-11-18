# SPDX-License-Identifier: AGPL-3.0-only
"""The macOS launcher probe (scripts/macos/app-launchers-probe.{sh,py}): its profile seeding, document counting, the
.odb fixture and what the probe covers of the launchers HST Office copies to /Applications."""
import importlib.util
from pathlib import Path
import unittest
import zipfile

import _paths  # noqa: F401 - hst_office importable

ROOT = Path(__file__).resolve().parents[2]
MACOS = ROOT / "scripts" / "macos"
_spec = importlib.util.spec_from_file_location("app_launchers_probe", MACOS / "app-launchers-probe.py")
PROBE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROBE)


class ProbeHelper(unittest.TestCase):
    XCU = ('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry">\n'
           '<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>false</value>'
           '</prop></item>\n</oor:items>\n')

    def test_seed_sets_each_value_once(self):
        text = PROBE.seed_text(PROBE.seed_text(self.XCU))
        self.assertEqual(text.count('oor:path="/org.hasontech.hstoffice.Welcome"'), 1)
        self.assertIn("<value>true</value>", text)
        self.assertIn("pipe,name=hst-launcher-probe;urp;", text)
        self.assertEqual(text.count("ooSetupConnectionURL"), 1)
        with self.assertRaises(ValueError):
            PROBE.seed_text("<x/>")

    def test_documents_are_counted_by_kind(self):
        class Doc:
            def __init__(self, service):
                self.service = service

            def supportsService(self, name):
                if self.service is None:
                    raise RuntimeError("no model")
                return name == self.service
        docs = [Doc(PROBE.KINDS["writer"]), Doc(PROBE.KINDS["calc"]), Doc(PROBE.KINDS["writer"]), Doc(None), Doc("x")]
        self.assertEqual(PROBE.kinds_of(docs), {"writer": 2, "calc": 1})

    def test_odb_fixture_is_a_portable_database_document(self):
        # The product no longer creates databases, so the probe opens this committed file instead.
        with zipfile.ZipFile(ROOT / "tests" / "fixtures" / "base" / "probe.odb") as odb:
            first = odb.infolist()[0]
            self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))
            self.assertEqual(odb.read("mimetype"), b"application/vnd.oasis.opendocument.base")
            self.assertNotIn("meta.xml", odb.namelist())  # no author or machine details
            content = odb.read("content.xml").decode()
        self.assertIn('xlink:href="../probe-tables/"', content)  # beside the copy, on any machine
        self.assertIn('db:media-type="application/dbase"', content)
        script = (MACOS / "app-launchers-probe.sh").read_text()
        self.assertIn('tests/fixtures/base/probe.odb" "$out/probe.odb"', script)
        self.assertIn('mkdir -p "$out/probe-tables"', script)

    def test_probe_covers_the_installed_copies(self):
        script = (MACOS / "app-launchers-probe.sh").read_text(encoding="utf-8")
        self.assertIn('names=("HST Writer" "HST Sheets" "HST Slides" "HST Draw" "HST PDF")', script)
        for needed in ("HST Office from the .dmg copied no launcher", "the one-time notice is shown",
                       "copies_are 5 0", "copies_are 4 0", "kMDItemCFBundleIdentifier == '$bundle_id.launcher.*'",
                       "uno icons remove", "uno icons add", "Chuyển vào Thùng rác", "pdf_opens", "one_office"):
            self.assertIn(needed, script)
        from hst_office import mac_app_launchers_ui
        self.assertIn('"Biểu tượng ứng dụng"', script)
        self.assertEqual(mac_app_launchers_ui.TEXTS["vi"]["title"], "Biểu tượng ứng dụng")

    def test_office_commands_live_beside_the_probe(self):
        office = (MACOS / "app_launchers_probe_office.py").read_text(encoding="utf-8")
        for command in ("def title(", "def window(", "def icons(", "def frames(", "def template(", "def window_gone(",
                        "def no_base_menu("):
            self.assertIn(command, office)
        self.assertEqual(PROBE.KINDS["draw"], "com.sun.star.drawing.DrawingDocument")


if __name__ == "__main__":
    unittest.main()
