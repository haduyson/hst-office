# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese text helpers (BODAU, TACHHO, TACHTEN, name order), the Sheets utilities' decisions, and the add-in
contract: CalcAddIns.xcu, the IDL, the compiled type library and the package manifest agree."""
import os
import re
import time
import unittest
import xml.etree.ElementTree as ET

import _paths

from hst_office import vietnamese_calc_logic as logic
from hst_office import vietnamese_text as vt

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR = "{http://openoffice.org/2001/registry}"


class Text(unittest.TestCase):
    def test_remove_diacritics(self):
        self.assertEqual(vt.remove_diacritics("Nguyễn Văn Đức"), "Nguyen Van Duc")
        self.assertEqual(vt.remove_diacritics("ĐẶNG THỊ HOÀ, hoá 123"), "DANG THI HOA, hoa 123")
        self.assertEqual(vt.remove_diacritics(""), "")
        self.assertEqual(vt.remove_diacritics("Ưu tiên ở Hà Nội"), "Uu tien o Ha Noi")

    def test_split_name(self):
        self.assertEqual(vt.split_name("  Nguyễn  Thị Minh   Khai "), ("Nguyễn Thị Minh", "Khai"))
        self.assertEqual(vt.split_name("Lan"), ("", "Lan"))
        self.assertEqual(vt.split_name(""), ("", ""))
        self.assertEqual(vt.family_name("Trần Văn An"), "Trần Văn")
        self.assertEqual(vt.given_name("Trần Văn An"), "An")

    def test_vietnamese_order(self):
        self.assertEqual(sorted(["b", "ạ", "â", "á", "ă", "a", "à", "ả", "ã", "đ", "d", "e"], key=vt.sort_key),
                         ["a", "à", "ả", "ã", "á", "ạ", "ă", "â", "b", "d", "đ", "e"])
        self.assertEqual(sorted(["Ơn", "Ôn", "On", "Ưa", "Ua", "Va"], key=vt.sort_key), ["On", "Ôn", "Ơn", "Ua", "Ưa", "Va"])
        self.assertLess(vt.sort_key("An"), vt.sort_key("An Bình"))

    def test_names_by_given_name_then_family(self):
        names = ["Trần Văn Bình", "Lê Văn An", "Nguyễn An", "Đỗ Ân", "Vũ Dung", "Hoàng Đào", "Lê Ánh"]
        self.assertEqual(sorted(names, key=vt.name_sort_key),
                         ["Lê Văn An", "Nguyễn An", "Lê Ánh", "Đỗ Ân", "Trần Văn Bình", "Vũ Dung", "Hoàng Đào"])


class Logic(unittest.TestCase):
    def test_blank_runs(self):
        self.assertEqual(logic.blank_runs(0, 9, [(0, 1), (4, 4), (7, 7)]), [(2, 2), (5, 2), (8, 2)])
        self.assertEqual(logic.blank_runs(0, 4, []), [(0, 5)])
        self.assertEqual(logic.blank_runs(0, 4, [(0, 4)]), [])
        self.assertEqual(logic.blank_runs(5, 9, [(0, 6), (3, 3), (12, 20)]), [(7, 3)])
        self.assertEqual(logic.blank_runs(0, 5, [(2, 3), (0, 0), (2, 2)]), [(1, 1), (4, 2)])

    def test_blank_runs_50k_rows(self):
        content = [(row, row) for row in range(0, 50000, 2)]  # every other row blank: the worst case
        start = time.perf_counter()
        runs = logic.blank_runs(0, 49999, content)
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertEqual(len(runs), 25000)
        self.assertEqual(sum(count for _, count in runs), 25000)

    def test_name_columns(self):
        self.assertEqual(logic.name_columns([("STT", "Họ và tên", "Lớp"), (1.0, "Lê An", "6A")]), (True, 1, None))
        self.assertEqual(logic.name_columns([("STT", "Họ đệm", "Tên"), (1.0, "Lê", "An")]), (True, None, (1, 2)))
        self.assertEqual(logic.name_columns([(1.0, "Lê An"), (2.0, "Trần Bình")]), (False, 1, None))
        self.assertEqual(logic.name_columns([(1.0, 2.0)]), (False, None, None))
        self.assertEqual(logic.name_columns([("Full name",), ("An",)]), (True, 0, None))

    def test_sort_order(self):
        rows = [("Trần Bình",), ("Lê An",), ("Nguyễn An",)]
        self.assertEqual(logic.sort_order(rows, 0), [1, 2, 0])
        self.assertEqual(logic.sort_order([("Trần", "Bình"), ("Lê", "An")], parts=(0, 1)), [1, 0])

    def test_split_and_strip_rows(self):
        self.assertEqual(logic.split_rows(["Lê Văn An", 5.0, ""]), (("Lê Văn", "An"), ("", ""), ("", "")))
        self.assertEqual(logic.strip_rows((("Đức", 1.0), ("abc", "Hà"))), ((("Duc", 1.0), ("abc", "Ha")), 2))

    def test_functions_used(self):
        self.assertEqual(logic.functions_used(["=DOCTIEN(A1)&BODAU(B1)", "=SUM(A1)", None]), ["DOCTIEN", "BODAU"])
        self.assertEqual(logic.functions_used(["=ORG.HST.OFFICE.VI.CALCFUNCTIONS.DOCSO(A1)"]), ["DOCSO"])
        self.assertEqual(logic.functions_used(["=MYDOCSO(A1)", "=docso (1)"]), ["DOCSO"])


def idl_methods():
    """{method: [parameter names]} of idl/XCalcFunctions.idl."""
    text = open(os.path.join(EXT, "idl", "XCalcFunctions.idl"), encoding="utf-8").read()
    return {m: re.findall(r"\[in\]\s+\w+\s+(\w+)", params)
            for m, params in re.findall(r"string\s+(\w+)\s*\(([^)]*)\)", text)}


class AddInContract(unittest.TestCase):
    def test_config_matches_idl(self):
        root = ET.parse(os.path.join(EXT, "CalcAddIns.xcu")).getroot()
        service = next(n for n in root.iter("node") if n.get(OOR + "name") == "org.hst.office.vi.CalcFunctions")
        functions = next(n for n in service if n.get(OOR + "name") == "AddInFunctions")
        config = {}
        for function in functions:
            params = next(n for n in function if n.get(OOR + "name") == "Parameters")
            config[function.get(OOR + "name")] = [p.get(OOR + "name") for p in params]
            props = {p.get(OOR + "name"): p for p in function.findall("prop")}
            self.assertEqual(props["Category"].find("value").text, "Vietnamese")
            name = function.get(OOR + "name").upper()
            self.assertEqual(props["CompatibilityName"].find("value").text, name)
            self.assertEqual({v.text for v in props["DisplayName"].findall("value")}, {name})
        methods = idl_methods()
        self.assertEqual(config, methods)
        self.assertEqual(sorted(m.upper() for m in methods), sorted(logic.FUNCTION_NAMES))
        for params in methods.values():
            # configmgr returns set nodes by name length, then name: that must be the IDL order
            self.assertEqual(params, sorted(params, key=lambda n: (len(n), n)))

    def test_type_library_is_built_from_the_idl(self):
        rdb = open(os.path.join(EXT, "types", "hst-calc-functions.rdb"), "rb").read()
        self.assertTrue(rdb.startswith(b"UNOIDL"))
        for method, params in idl_methods().items():
            for name in [method, "XCalcFunctions"] + params:
                self.assertIn(name.encode(), rdb)

    def test_manifest_registers_types_and_functions(self):
        manifest = open(os.path.join(EXT, "META-INF", "manifest.xml"), encoding="utf-8").read()
        self.assertIn('"types/hst-calc-functions.rdb" manifest:media-type="application/vnd.sun.star.uno-typelibrary;type=RDB"', manifest)
        self.assertLess(manifest.index("hst-calc-functions.rdb"), manifest.index("hst_office_component.py"))
        self.assertIn('"CalcAddIns.xcu"', manifest)


if __name__ == "__main__":
    unittest.main()
