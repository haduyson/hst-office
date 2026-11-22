# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: MathType equations are recognised from their OLE data, the commands are wired, and saving a
document with formulas as .doc/.xls/.ppt asks first (other formats and documents without formulas never ask)."""
import os
import struct
import sys
import types
import unittest
from unittest import mock

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


class FormulaUnloadTest(unittest.TestCase):
    """A replaced MathType object lets go of MathType (state LOADED), whatever state it was in."""

    class Embedded:
        def __init__(self, state, fail=False):
            self.state, self.fail, self.calls = state, fail, []

        def getCurrentState(self):
            return self.state

        def changeState(self, state):
            self.calls.append(state)
            if self.fail:
                raise RuntimeError("cannot unload")
            self.state = state

    def test_unload(self):
        from hst_office import formula_convert
        running, loaded, stuck = self.Embedded(1), self.Embedded(0), self.Embedded(2, fail=True)
        for embedded in (running, loaded, stuck, None):
            formula_convert.unload(embedded)
        self.assertEqual(([0], 0), (running.calls, running.state))
        self.assertEqual([], loaded.calls)
        self.assertEqual([0], stuck.calls)  # tried; the conversion goes on


class MathTypeRegistryViewTest(unittest.TestCase):
    """The 64-bit office also finds a 32-bit OLE server, registered in the 32-bit view of HKCR\\CLSID (WOW6432Node)."""

    def fake_winreg(self, views):
        """A winreg whose OpenKey finds `views[flag]` = {path: value} only for the view flag it is asked for."""
        module = types.ModuleType("winreg")
        module.HKEY_CLASSES_ROOT, module.KEY_READ, module.KEY_WOW64_64KEY, module.KEY_WOW64_32KEY = 1, 0x20019, 0x100, 0x200

        class Key:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def open_key(root, path, reserved=0, access=0):
            for flag, entries in views.items():
                if access & flag and path in entries:
                    return Key(entries[path])
            raise OSError(2, "not found")
        module.OpenKey = open_key
        module.QueryValue = lambda key, sub: key.value
        return module

    def test_32_bit_server_found(self):
        path = r"CLSID\{%s}\LocalServer32" % formula_ole.MATHTYPE
        winreg = self.fake_winreg({0x200: {path: r"C:\Program Files (x86)\MathType\MathType.exe /Embedding"}})
        with mock.patch.dict(sys.modules, {"winreg": winreg}):
            read = server._windows_reader()
            self.assertEqual(r"C:\Program Files (x86)\MathType\MathType.exe /Embedding", read(path))
            self.assertTrue(server.server_installed(formula_ole.MATHTYPE, read, lambda p: True, "win32"))

    def test_64_bit_view_first_and_missing_key(self):
        path = r"CLSID\{%s}\LocalServer32" % formula_ole.MATHTYPE
        winreg = self.fake_winreg({0x100: {path: "a.exe"}, 0x200: {path: "b.exe"}})
        with mock.patch.dict(sys.modules, {"winreg": winreg}):
            read = server._windows_reader()
            self.assertEqual("a.exe", read(path))
            self.assertIsNone(read(r"CLSID\{00000000-0000-0000-0000-000000000000}\LocalServer32"))


class MathTypeDoubleClickTest(unittest.TestCase):
    """Where MathType is installed, double-clicking its equation is left to the office: MathType opens it (1.0.2)."""

    def setUp(self):
        stubs = {name: types.ModuleType(name) for name in ("unohelper", "com", "com.sun", "com.sun.star",
                                                            "com.sun.star.awt")}
        stubs["unohelper"].Base = type("Base", (), {})
        stubs["com.sun.star.awt"].XCallback = type("XCallback", (), {})
        stubs["com.sun.star.awt"].XMouseClickHandler = type("XMouseClickHandler", (), {})
        patcher = mock.patch.dict(sys.modules, stubs)
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.modules.pop("hst_office.formula_click", None)
        self.addCleanup(sys.modules.pop, "hst_office.formula_click", None)
        from hst_office import formula_click
        self.click = formula_click

    @staticmethod
    def controller(selection):
        return types.SimpleNamespace(getSelection=lambda: selection)

    @staticmethod
    def text_object(clsid):
        return types.SimpleNamespace(CLSID=clsid, supportsService=lambda n: n == "com.sun.star.text.TextEmbeddedObject")

    def test_writer_object(self):
        mathtype = self.controller(self.text_object(formula_ole.MATHTYPE.lower()))
        self.assertTrue(self.click.opens_in_mathtype(mathtype, lambda c: c == formula_ole.MATHTYPE))
        self.assertFalse(self.click.opens_in_mathtype(mathtype, lambda c: False))  # not installed: the question
        equation3 = self.controller(self.text_object(formula_ole.EQUATION3))
        self.assertTrue(self.click.opens_in_mathtype(equation3, lambda c: True))
        formula = self.controller(self.text_object(formula_ole.MATH))
        self.assertFalse(self.click.opens_in_mathtype(formula, lambda c: True))
        self.assertFalse(self.click.opens_in_mathtype(self.controller(None), lambda c: True))

    def test_single_ole_shape(self):
        shape = types.SimpleNamespace(CLSID=formula_ole.MATHTYPE, getShapeType=lambda: "com.sun.star.drawing.OLE2Shape")
        shapes = types.SimpleNamespace(supportsService=lambda n: False, getCount=lambda: 1, getByIndex=lambda i: shape)
        self.assertTrue(self.click.opens_in_mathtype(self.controller(shapes), lambda c: True))
        two = types.SimpleNamespace(supportsService=lambda n: False, getCount=lambda: 2, getByIndex=lambda i: shape)
        self.assertFalse(self.click.opens_in_mathtype(self.controller(two), lambda c: True))


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
