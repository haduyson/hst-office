# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/check-msi-coexist.py: the Registry-table rules for names HST Office must not share with LibreOffice."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_msi_coexist", ROOT / "scripts/check-msi-coexist.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def row(key, value="", name=""):
    return {"Registry": "r", "Root": "0", "Key": key, "Name": name, "Value": value, "Component_": "c"}


class Rules(unittest.TestCase):
    def rules(self, *rows):
        return sorted({rule for rule, _ in check.violations(list(rows))})

    def test_hst_names_pass(self):
        self.assertEqual(self.rules(
            row(r"HSTOffice.StarWriterDocument.6\shell\open\command", r'"[INSTALLLOCATION]program\soffice.exe" -o "%1"'),
            row(".odt", "HSTOffice.WriterDocument.1"), row("HSTOffice.Extension.1"), row("HSTOffice.OfficeURI"),
            row(r"CLSID\{BC84498F-C467-4BD6-9876-D44924DA54D0}\InprocServer32", r"[INSTALLLOCATION]program\shlxthdl\shlxthdl.dll"),
            row(r"Software\HASON TECH\Layers\URE\1", r"[INSTALLLOCATION]URE\\", "UREINSTALLLOCATION"),
            # kept on purpose: OLE embedding class and automation names
            row(r"CLSID\{30A2652A-DDF7-45e7-ACA6-3EAB26FC8A4E}\LocalServer32"), row(r"AppID\soffice.exe"),
            row(r"com.sun.star.ServiceManager\CLSID"), row(r"Writer.Application\CLSID")), [])

    def test_each_shared_name_fails(self):
        cases = {
            "App Paths entry": row(r"Software\Microsoft\Windows\CurrentVersion\App Paths\soffice.exe"),
            "LibreOffice URI scheme": row(r"vnd.libreoffice.command\shell\open\command"),
            "LibreOffice ProgID": row(".sxw", "soffice.StarWriterDocument.6"),
            "LibreOffice Explorer extension class id": row(r".odt\shellex\{BB2E617C-0920-11D1-9A0B-00C04FC2D6C1}",
                                                           "{3B092F0C-7696-40E3-A80F-68D74DA84210}"),
            "key under Software\\LibreOffice": row(r"Software\LibreOffice\Layers\URE\1"),
            "LibreOffice publisher or link": row(r"Software\Microsoft\Windows\CurrentVersion\Uninstall\x",
                                                 "The Document Foundation for the LibreOffice Community", "Publisher"),
        }
        for rule, r in cases.items():
            self.assertIn(rule, self.rules(r), rule)
        self.assertEqual(self.rules(row("office.Extension.1")), ["LibreOffice ProgID"])
        self.assertEqual(self.rules(row("LibreOffice.Docx")), ["LibreOffice ProgID"])

    def test_patch_series_adds_no_shared_name(self):
        rows = check.series_rows()
        self.assertGreater(len(rows), 500)
        self.assertEqual(check.violations(rows), [])

    def test_empty_or_unreadable_msi_fails(self):
        self.assertEqual(check.main(["--msi", str(ROOT / "does-not-exist.msi")]), 1)


if __name__ == "__main__":
    unittest.main()
