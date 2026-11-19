# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/check-msi-pdf-preview.py: the MSI registers the HST PDF preview/thumbnail handlers without taking
another PDF program's slot."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_msi_pdf_preview", ROOT / "scripts/check-msi-pdf-preview.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXT = "registry_g_m_o_winexplorerext_hstoffice10"
SHLX_DIR = "HSTOf_progr_shlxt_e42305068"


def good_tables():
    registry = [{"Registry": f"r{i}", "Root": root, "Key": key, "Name": name, "Value": value, "Component_": EXT}
                for i, (root, key, name, value) in enumerate(check.required_rows())]
    components = [{"Component": EXT, "Directory_": "INSTALLLOCATION", "Condition": "WRITE_REGISTRY=1"},
                  {"Component": "dll_shlxthdl", "Directory_": SHLX_DIR, "Condition": ""},
                  {"Component": "dll_pdfpreview", "Directory_": SHLX_DIR, "Condition": ""}]
    searches, locators, properties = [], [], []
    for slot, clsid_property, clsid, signature, iid in check.SLOTS:
        component = f"registry_{slot.lower()}"
        registry.append({"Registry": slot, "Root": "0", "Key": check.SFA + iid, "Name": "", "Value": clsid,
                         "Component_": component})
        components.append({"Component": component, "Directory_": "INSTALLLOCATION",
                           "Condition": f"(NOT {slot} OR {slot}={clsid_property}) AND (WRITE_REGISTRY=1)"})
        searches.append({"Property": slot, "Signature_": signature})
        locators.append({"Signature_": signature, "Root": "2", "Key": f"SOFTWARE\\Classes\\{check.SFA}{iid}",
                         "Name": "", "Type": "18"})
        properties.append({"Property": clsid_property, "Value": clsid})
    files = [{"File": "f1", "Component_": "dll_shlxthdl", "FileName": "shlxthdl.dll"},
             {"File": "f2", "Component_": "dll_pdfpreview", "FileName": "HSTPDF~1.DLL|hstpdfpreview.dll"}]
    return {"File": files, "Component": components, "Registry": registry, "AppSearch": searches,
            "RegLocator": locators, "Property": properties}


class PdfPreviewMsi(unittest.TestCase):
    def test_complete_registration_passes(self):
        self.assertEqual(check.msi_errors(good_tables()), [])

    def test_missing_dll_fails(self):
        tables = good_tables()
        tables["File"] = tables["File"][:1]
        self.assertIn("hstpdfpreview.dll is not in the File table", check.msi_errors(tables))

    def test_dll_outside_shlxthdl_fails(self):
        tables = good_tables()
        tables["Component"][2]["Directory_"] = "INSTALLLOCATION"
        self.assertTrue(any("next to shlxthdl.dll" in e for e in check.msi_errors(tables)))

    def test_each_required_value_is_checked(self):
        for index in range(len(check.required_rows())):
            with self.subTest(index=index):
                tables = good_tables()
                del tables["Registry"][index]
                self.assertTrue(any(e.startswith("missing registry value") for e in check.msi_errors(tables)))

    def test_unconditional_fallback_slot_fails(self):
        for i, (slot, *_rest) in enumerate(check.SLOTS):
            with self.subTest(slot=slot):
                tables = good_tables()
                tables["Component"][3 + i]["Condition"] = "WRITE_REGISTRY=1"
                self.assertTrue(any("could be overwritten" in e for e in check.msi_errors(tables)))

    def test_slot_condition_must_not_gate_other_values(self):
        tables = good_tables()
        tables["Registry"][0]["Component_"] = "registry_hstpdfpreviewslot"
        errors = check.msi_errors(tables)
        self.assertTrue(any("slot condition" in e for e in errors), errors)
        self.assertTrue(any("gates more than" in e for e in errors), errors)

    def test_appsearch_locator_and_property_are_checked(self):
        for table in ("AppSearch", "RegLocator", "Property"):
            with self.subTest(table=table):
                tables = good_tables()
                tables[table] = []
                self.assertGreaterEqual(len(check.msi_errors(tables)), 2)
        tables = good_tables()
        tables["RegLocator"][0]["Type"] = "2"  # 32-bit view: would miss the 64-bit Explorer's slot
        self.assertTrue(any("RegLocator HstPdfPreviewSlot" in e for e in check.msi_errors(tables)))

    def test_pdf_extension_key_is_never_written(self):
        for key in (".pdf\\ShellEx\\" + check.PREVIEW_IID, "MSEdgePDF\\ShellEx\\" + check.THUMBNAIL_IID):
            with self.subTest(key=key):
                tables = copy.deepcopy(good_tables())
                tables["Registry"].append({"Registry": "x", "Root": "0", "Key": key, "Name": "",
                                           "Value": check.PREVIEW_CLSID, "Component_": EXT})
                self.assertTrue(any("belongs to the user's PDF program" in e for e in check.msi_errors(tables)))


if __name__ == "__main__":
    unittest.main()
