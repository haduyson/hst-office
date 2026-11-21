# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: MathType equations are recognised from their OLE data, the commands are wired, and saving a
document with formulas as .doc/.xls/.ppt asks first (other formats and documents without formulas never ask)."""
import os
import struct
import unittest

import _paths  # noqa: F401

from hst_office import formula_mathtype_server as server
from hst_office import formula_ole, formula_save_check


def compound_file(class_id):
    """A minimal OLE compound file: header, one directory sector whose root entry carries class_id."""
    header = bytearray(512)
    header[:8] = formula_ole.SIGNATURE
    struct.pack_into("<H", header, 0x1E, 9)  # 512-byte sectors
    struct.pack_into("<I", header, 0x30, 0)  # directory in sector 0
    directory = bytearray(512)
    name = "Root Entry".encode("utf-16-le")
    directory[:len(name)] = name
    first, second, third, rest = class_id.split("-", 3)
    directory[0x50:0x60] = struct.pack("<IHH", int(first, 16), int(second, 16), int(third, 16)) + \
        bytes.fromhex(rest.replace("-", ""))
    return bytes(header + directory)


class FakeObjects:
    def __init__(self, clsids):
        self.items = {"o%d" % i: type("O", (), {"CLSID": c}) for i, c in enumerate(clsids)}

    def getElementNames(self):
        return tuple(self.items)

    def getByName(self, name):
        return self.items[name]


class FakeWriter:
    def __init__(self, clsids):
        self.objects = FakeObjects(clsids)

    def supportsService(self, name):
        return name == "com.sun.star.text.TextDocument"

    def getEmbeddedObjects(self):
        return self.objects


class FormulaOleTest(unittest.TestCase):
    def test_class_ids(self):
        self.assertEqual(formula_ole.MATHTYPE, formula_ole.root_class_id(compound_file(formula_ole.MATHTYPE)))
        self.assertTrue(formula_ole.is_mathtype(compound_file(formula_ole.MATHTYPE)))
        self.assertTrue(formula_ole.is_mathtype(compound_file(formula_ole.EQUATION3)))
        excel = "00020820-0000-0000-C000-000000000046"
        self.assertFalse(formula_ole.is_mathtype(compound_file(excel)))

    def test_not_a_compound_file(self):
        for data in (b"", b"PK\x03\x04" + bytes(600), formula_ole.SIGNATURE + bytes(100)):
            self.assertEqual("", formula_ole.root_class_id(data))
        broken = bytearray(compound_file(formula_ole.MATHTYPE))
        struct.pack_into("<I", broken, 0x30, 1000)  # directory beyond the end
        self.assertEqual("", formula_ole.root_class_id(bytes(broken)))

    def test_math_clsid(self):
        self.assertTrue(formula_ole.is_math_clsid(formula_ole.MATH.lower()))
        self.assertFalse(formula_ole.is_math_clsid(None))

    def test_commands_dispatched(self):
        python = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "python", "hst_office")
        for name in ("action_names.py", "actions.py"):  # dispatch takes its command names from action_names
            text = open(os.path.join(python, name), encoding="utf-8").read()
            for command in ("ConvertFormulas", "AskConvertFormula", "FormulaTemplates"):
                self.assertIn('"%s"' % command, text)

    def test_document_jobs_skip_embedded_formulas(self):
        """Converting hundreds of equations changes each new formula's modified state several times: the jobs on
        document events run for document windows only, not for every embedded formula or chart."""
        import xml.etree.ElementTree as ET
        oor = "{http://openoffice.org/2001/registry}"
        path = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "Jobs.xcu")
        jobs = {n.get(oor + "name"): n for n in ET.parse(path).getroot().find("node").findall("node")}
        for job in ("org.hst.office.vi.FormulaOpenJob", "org.hst.office.vi.PreviousVersionsJob"):
            context = {p.get(oor + "name"): p.findtext("value") for p in jobs[job].findall("prop")}.get("Context", "")
            modules = context.split(",")
            for module in ("com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument",
                           "com.sun.star.presentation.PresentationDocument", "com.sun.star.drawing.DrawingDocument"):
                self.assertIn(module, modules, job)
            self.assertNotIn("com.sun.star.formula.FormulaProperties", context, job)
            self.assertNotIn("com.sun.star.chart2.ChartDocument", context, job)


class MathTypeServerTest(unittest.TestCase):
    """The double-click question offers "Mở bằng MathType" only where MathType is installed (Windows)."""
    MATHTYPE_EXE = r"C:\Program Files (x86)\MathType\MathType.exe"

    def registry(self, entries):
        return lambda path: entries.get(path)

    def test_installed_mathtype(self):
        read = self.registry({r"CLSID\{%s}\LocalServer32" % formula_ole.MATHTYPE: '"%s" /Automation' % self.MATHTYPE_EXE})
        self.assertTrue(server.server_installed(formula_ole.MATHTYPE, read, lambda p: p == self.MATHTYPE_EXE, "win32"))
        self.assertEqual(("convert", "open", "leave"), server.choices(
            formula_ole.MATHTYPE, lambda c: server.server_installed(c, read, lambda p: True, "win32")))

    def test_equation3_treated_as_mathtype(self):
        read = self.registry({r"CLSID\{%s}\TreatAs" % formula_ole.EQUATION3: "{%s}" % formula_ole.MATHTYPE,
                              r"CLSID\{%s}\LocalServer32" % formula_ole.MATHTYPE: self.MATHTYPE_EXE + " /Automation"})
        self.assertTrue(server.server_installed(formula_ole.EQUATION3, read, lambda p: p == self.MATHTYPE_EXE, "win32"))

    def test_not_installed(self):
        stale = self.registry({r"CLSID\{%s}\LocalServer32" % formula_ole.MATHTYPE: self.MATHTYPE_EXE})
        self.assertFalse(server.server_installed(formula_ole.MATHTYPE, stale, lambda p: False, "win32"))  # uninstalled
        self.assertFalse(server.server_installed(formula_ole.MATHTYPE, self.registry({}), lambda p: True, "win32"))
        self.assertFalse(server.server_installed(formula_ole.MATHTYPE, stale, lambda p: True, "linux"))
        self.assertFalse(server.server_installed(formula_ole.MATHTYPE, stale, lambda p: True, "darwin"))
        self.assertEqual(("convert", "leave"), server.choices(formula_ole.MATHTYPE, lambda c: False))

    def test_program_path(self):
        self.assertEqual(r"C:\a b\m.exe", server.program_path(r'"C:\a b\m.exe" /x'))
        self.assertEqual(r"C:\a b\m.exe", server.program_path(r"C:\a b\m.exe /x"))


class FormulaSaveCheckTest(unittest.TestCase):
    def test_binary_formats(self):
        self.assertEqual(".doc", formula_save_check.binary_extension("MS Word 97"))
        self.assertEqual(".xls", formula_save_check.binary_extension("MS Excel 97 Vorlage/Template"))
        self.assertEqual(".ppt", formula_save_check.binary_extension("MS PowerPoint 97 AutoPlay"))
        for name in ("MS Word 2007 XML", "Calc MS Excel 2007 XML", "writer8", "", None):
            self.assertIsNone(formula_save_check.binary_extension(name))

    def test_asks_only_for_formulas_in_binary_formats(self):
        asked = []

        def ask(ctx, doc, extension):
            asked.append(extension)
            return False
        with_formula, without = FakeWriter([formula_ole.MATH]), FakeWriter(["00000000-0000-0000-0000-000000000000"])
        self.assertFalse(formula_save_check.check(None, with_formula, "MS Word 97", ask))
        self.assertTrue(formula_save_check.check(None, with_formula, "MS Word 2007 XML", ask))
        self.assertTrue(formula_save_check.check(None, without, "MS Word 97", ask))
        self.assertTrue(formula_save_check.check(None, None, "MS Word 97", ask))
        self.assertEqual([".doc"], asked)
        self.assertTrue(formula_save_check.check(None, with_formula, "MS Word 97", lambda *a: True))

    def test_unreadable_document_saves(self):
        self.assertTrue(formula_save_check.check(None, object(), "MS Word 97", lambda *a: False))


if __name__ == "__main__":
    unittest.main()
