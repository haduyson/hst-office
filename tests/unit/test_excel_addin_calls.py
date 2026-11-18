# SPDX-License-Identifier: AGPL-3.0-only
"""VND()/USD() called through a Vietnamese number-words add-in become the HST functions after a load: the formula
text rules, the job's registration, and that other external references stay as they were."""
import os
import re
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

import _paths  # noqa: F401

from hst_office.excel_addin_calls import (PROGRAMMATIC, document_file_name, external_link_files, macro_defined_functions,
                                         rewrite)

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import excel_addin_fixtures as fx  # noqa: E402

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR = "{http://openoffice.org/2001/registry}"
VNTOOLS = "'file:///C:/Program%20Files%20(x86)/vnTools/Ufunctions.xlam'"
VND, USD = PROGRAMMATIC + "VND", PROGRAMMATIC + "USD"


class Rewrite(unittest.TestCase):
    def test_addin_workbook_external_names(self):
        cases = {
            "=%s#VND(A1)" % VNTOOLS: "=%s(A1)" % VND,
            "=%s#VND(A1;TRUE())" % VNTOOLS: "=%s(A1;TRUE())" % VND,
            "=%s#USD(A1;TRUE())" % VNTOOLS: "=%s(A1;TRUE())" % USD,
            '=%s#VND(F10;TRUE();1;"đồng";"xu")' % VNTOOLS: '=%s(F10;TRUE();1;"đồng";"xu")' % VND,
            "=LEN(%s#vnd(A1))&%s#Usd(B1)" % (VNTOOLS, VNTOOLS): "=LEN(%s(A1))&%s(B1)" % (VND, USD),
            "='file:///D:/Tools/UFUNCTIONS.XLA'#VND(A1)": "=%s(A1)" % VND,
            "='C:\\Program Files\\BluesOfts\\AccHelper\\AccHelper.xll'#USD(A1;\"VND\")": "=%s(A1;\"VND\")" % USD,
            "=%s#VND (A1)" % VNTOOLS: "=%s (A1)" % VND,
            "='file:///C:/Users/a/AppData/Roaming/Microsoft/AddIns/AccHelperEx.xla'#VND(A1;3)": "=%s(A1;3)" % VND,
        }
        for formula, expected in cases.items():
            self.assertEqual(rewrite(formula), expected, formula)

    def test_xll_prefix_and_xll_files(self):
        # the XLL add-in always reads the unit: its one-argument calls get TRUE()
        cases = {
            "=_xll.VND(A1)": "=%s(A1;TRUE())" % VND,
            "=_XLL.usd(A1)&_xll.VND(2;3)": "=%s(A1;TRUE())&%s(2;3)" % (USD, VND),
            "=IF(A1>0;_xll.VND(A1);\"\")": "=IF(A1>0;%s(A1;TRUE());\"\")" % VND,
            "=_xll.USD(SUM(A1;B1))&_xll.VND(\"a)\")": "=%s(SUM(A1;B1);TRUE())&%s(\"a)\";TRUE())" % (USD, VND),
            "=_xll.VND(_xll.USD(A1))": "=%s(%s(A1;TRUE());TRUE())" % (VND, USD),
            "=_xll.VND(A1;;;;;TRUE())": "=%s(A1;;;;;TRUE())" % VND,
            "='file:///C:/a/AccHelper.xll'#VND(A1)": "=%s(A1;TRUE())" % VND,
            "=_xll.VND()": "=%s()" % VND,
        }
        for formula, expected in cases.items():
            self.assertEqual(rewrite(formula), expected, formula)

    def test_numbered_links_need_the_package_names(self):
        links = {1: "ufunctions.xlam", 2: "other.xlam", 3: "acchelperex.xla"}
        self.assertEqual(rewrite("=[1]!VND(A1)&[2]!VND(A1)&[3]!USD(A1)", links),
                         "=%s(A1)&[2]!VND(A1)&%s(A1;TRUE())" % (VND, USD))
        self.assertEqual(rewrite("=[1]!VND(A1)"), "=[1]!VND(A1)")

    def test_plain_names_only_when_asked(self):
        self.assertEqual(rewrite("=vnd(1234)&USD (2)", plain=True), "=%s(1234)&%s (2)" % (VND, USD))
        self.assertEqual(rewrite("=vnd(1234)"), "=vnd(1234)")
        for formula in ("=%s(1)" % VND, "=Sheet1!VND(1)", "=\"VND(\"&A1", "=MYVND(1)"):
            self.assertEqual(rewrite(formula, plain=True), formula)

    def test_everything_else_is_left_alone(self):
        for formula in (
            "='file:///C:/x/Other.xlam'#VND(A1)",               # VND of another add-in workbook
            "=%s#DOCSO(A1)" % VNTOOLS,                           # another function of the add-in workbook
            "='file:///C:/x/Book.xlsx'#$Sheet1.A1",              # an external cell reference
            "=%s#VND" % VNTOOLS,                                 # the name, not called
            "=_xll.BDP(A1;\"PX_LAST\")",                         # another XLL function
            "=\"'x.xlam'#VND(1) _xll.VND(2)\"&A1",              # text in a string literal
            "='Ufunctions.xlam''#VND(A1)'!B2",                   # a quoted sheet name that only looks like one
            "=my_xll.VND(A1)", "=SUM(A1:A3)", "", None,
        ):
            self.assertEqual(rewrite(formula), formula, formula)

    def test_document_file_name(self):
        self.assertEqual(document_file_name("file:///C:/Program%20Files%20(x86)/vnTools/Ufunctions.xlam"),
                         "ufunctions.xlam")
        self.assertEqual(document_file_name("C:\\Tools\\It''s\\AccHelper.xll"), "acchelper.xll")


class Macros(unittest.TestCase):
    def test_document_functions_of_the_same_name(self):
        self.assertEqual(macro_defined_functions(["Option VBASupport 1\nPublic Function VND(n, Optional b)\nEnd Function",
                                                  "function usd(x)\n", None]), {"VND", "USD"})
        self.assertEqual(macro_defined_functions(["' Function VND(x)\nSub VND2()\nx = VND(1)\nFunction VNDX()"]), set())


class PackageLinks(unittest.TestCase):
    def test_external_link_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fx.write_xlsx(os.path.join(tmp, "a.xlsx"), {"A1": 1, "B1": ("[1]!VND(A1)", "Một")}, [
                fx.Link(fx.VNTOOLS_PATH, ["VND"]), fx.Link("UFUNCTIONS.XLAM", ["USD"], fx.XLLIBRARY),
                fx.Link("../Book%201.xlsx", ["Total"])])
            with zipfile.ZipFile(path) as package:
                self.assertEqual(external_link_files(package),
                                 {1: "ufunctions.xlam", 2: "ufunctions.xlam", 3: "book 1.xlsx"})
            plain = fx.write_xlsx(os.path.join(tmp, "b.xlsx"), {"A1": 1})
            with zipfile.ZipFile(plain) as package:
                self.assertEqual(external_link_files(package), {})


class Registration(unittest.TestCase):
    def test_job_runs_after_loading_a_spreadsheet(self):
        root = ET.parse(os.path.join(EXT, "Jobs.xcu")).getroot()
        nodes = {n.get(OOR + "name"): n for n in root.iter("node") if n.find("prop") is not None or
                 n.find("node") is not None}
        job = nodes["org.hst.office.vi.ExcelAddinCallsJob"]
        props = {p.get(OOR + "name"): p.find("value").text for p in job.findall("prop")}
        self.assertEqual(props, {"Service": "org.hst.office.vi.ExcelAddinCallsJob",
                                 "Context": "com.sun.star.sheet.SpreadsheetDocument"})
        for name in ("OnLoadFinished", "OnLoad"):
            self.assertIn("org.hst.office.vi.ExcelAddinCallsJob", [n.get(OOR + "name") for n in nodes[name].iter("node")])

    def test_component_registers_the_job(self):
        text = open(os.path.join(EXT, "python", "hst_office_component.py"), encoding="utf-8").read()
        self.assertTrue(re.search(r'\("excel_addin_calls_job", "ExcelAddinCallsJob", '
                                  r'"org.hst.office.vi.ExcelAddinCallsJob", JOB\)', text))


if __name__ == "__main__":
    unittest.main()
