# SPDX-License-Identifier: AGPL-3.0-only
"""VBA authoring in HST Writer/Sheets ("Macro VBA"): module template, shortcuts, ribbon button, menu item.

The runtime behaviour (modules run, .xlsm/.docm keep the code) is checked by tests/runtime/check-vba.py.
"""
import os
import re
import sys
import unicodedata
import unittest
import xml.etree.ElementTree as ET

import _paths

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
sys.path.insert(0, os.path.join(EXT, "python"))
from hst_office import vba_template  # noqa: E402

NAME = "{http://openoffice.org/2001/registry}name"
PATCH = os.path.join(_paths.ROOT, "patches", "libreoffice", "hst-vba-authoring.patch")
CONTEXT = {"com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument"}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def child(node, name):
    return next(n for n in node if n.get(NAME) == name)


class Template(unittest.TestCase):
    def test_new_modules_start_in_vba_mode_with_a_vietnamese_guide(self):
        for app, office in (("calc", "Excel"), ("writer", "Word")):
            text = vba_template.module_text(app)
            self.assertTrue(text.startswith("Option VBASupport 1\n"))
            self.assertTrue(vba_template.has_vba_option(text))
            self.assertIn("Microsoft " + office, text)
            self.assertIn("Alt+F8", text)
            self.assertIn("Sub XinChao()", text)
            self.assertTrue(all(line.startswith("'") for line in text.splitlines()[1:8]), "guide lines are comments")

    def test_editor_cursor_goes_to_the_example(self):
        text = vba_template.module_text("calc")
        line = vba_template.first_line_of(text, "XinChao")
        self.assertEqual(text.splitlines()[line - 1], "Sub XinChao()")
        self.assertEqual(vba_template.first_line_of("Sub A()\nEnd Sub", "XinChao"), 1)

    def test_vba_option_must_precede_procedures(self):
        self.assertFalse(vba_template.has_vba_option("Sub Main()\nEnd Sub\nOption VBASupport 1"))
        self.assertTrue(vba_template.has_vba_option("Rem Attribute VBA_ModuleType=VBAModule\noption  vbasupport 1\nSub A()\nEnd Sub"))
        self.assertFalse(vba_template.has_vba_option("REM  *****  BASIC  *****\nSub Main\nEnd Sub"))

    def test_module_names_follow_office(self):
        self.assertEqual(vba_template.next_module_name([]), "Module1")
        self.assertEqual(vba_template.next_module_name(["Module1", "module2", "ThisWorkbook"]), "Module3")
        self.assertEqual(vba_template.project_name("calc"), "VBAProject")
        self.assertEqual(vba_template.project_name("writer"), "Project")

    def test_round_trip_comparison_ignores_code_page_artifacts(self):
        text = vba_template.module_text("writer")
        stored = "Rem Attribute VBA_ModuleType=VBAModule\r\n" + unicodedata.normalize("NFD", text).replace("\n", "\r\n")
        self.assertTrue(vba_template.same_text(stored, text))
        self.assertFalse(vba_template.same_text(stored.replace("XinChao", "Khac"), text))

    def test_vietnamese_code_page(self):
        self.assertEqual(vba_template.VBA_TEXT_ENCODING_VI, 40)  # RTL_TEXTENCODING_MS_1258


class Shortcuts(unittest.TestCase):
    def keys(self):
        root = ET.parse(os.path.join(EXT, "Accelerators.xcu")).getroot()
        modules = child(child(root, "PrimaryKeys"), "Modules")
        return {(module.get(NAME), key.get(NAME)): key.find("prop/value").text for module in modules for key in module}

    def test_alt_f11_opens_the_vba_editor_in_writer_and_sheets(self):
        keys = self.keys()
        for module in CONTEXT:
            self.assertEqual(keys[(module, "F11_MOD2")], "org.hst.office.vi:EditVba")

    def test_alt_f8_opens_the_macro_dialog_like_office(self):
        keys = self.keys()
        for module in CONTEXT:
            self.assertEqual(keys[(module, "F8_MOD2")], ".uno:MacroDialog")
        self.assertEqual(len(keys), 4)

    def test_manifest_registers_accelerators(self):
        manifest = read(os.path.join(EXT, "META-INF", "manifest.xml"))
        self.assertIn('manifest:full-path="Accelerators.xcu"', manifest)

    def test_command_is_dispatched(self):
        actions = read(os.path.join(EXT, "python", "hst_office", "actions.py"))
        self.assertIn('"EditVba": vba.run', actions)


class CorePatch(unittest.TestCase):
    def setUp(self):
        self.text = read(PATCH)
        series = read(os.path.join(_paths.ROOT, "patches", "libreoffice", "series")).split()
        self.assertIn("hst-vba-authoring.patch", series)

    def test_ribbon_button_in_writer_and_sheets_tools_tab(self):
        for ui in ("sw/uiconfig/swriter/ui/notebookbar.ui", "sc/uiconfig/scalc/ui/notebookbar.ui"):
            self.assertIn("+++ b/" + ui, self.text)
        self.assertEqual(len(re.findall(r'^\+\s*<property name="action-name">org\.hst\.office\.vi:EditVba</property>', self.text, re.M)), 2)
        self.assertEqual(len(re.findall(r'^\+\s*<property name="label">Macro VBA</property>', self.text, re.M)), 2)
        self.assertNotIn("Soạn macro VBA", self.text)

    def test_macro_security_asks_before_running_document_macros(self):
        self.assertRegex(self.text, r"\+\s*<value>1</value>")
        self.assertIn("Office/Common.xcs", self.text)


class WordPatch(unittest.TestCase):
    def test_word_object_model_events_and_code_page(self):
        path = os.path.join(_paths.ROOT, "patches", "libreoffice", "hst-vba-word.patch")
        text = read(path)
        series = read(os.path.join(_paths.ROOT, "patches", "libreoffice", "series")).split()
        self.assertIn("hst-vba-word.patch", series)
        self.assertGreater(series.index("hst-vba-word.patch"), series.index("hst-vba-authoring.patch"))
        for needle in ("XCell Cell(", "any Words(", "any Sentences(", "long Alignment", "ApplyBulletDefault",
                       "VBACompatibilityMode", "RTL_TEXTENCODING_MS_1258", "SetVbaEventProcessor"):
            self.assertIn(needle, text)


class Menu(unittest.TestCase):
    def test_menu_item_for_writer_and_sheets(self):
        root = ET.parse(os.path.join(EXT, "Addons.xcu")).getroot()
        top = next(n for n in root.iter("node") if n.get(NAME) == "org.hst.office.vi")
        items = [n for n in child(top, "Submenu")]
        vba = [n for n in items if any(p.get(NAME) == "URL" and p.find("value").text == "org.hst.office.vi:EditVba" for p in n)]
        self.assertEqual(len(vba), 1)
        props = {p.get(NAME): p for p in vba[0]}
        self.assertEqual({v.text for v in props["Title"].findall("value")}, {"Macro VBA"})
        self.assertEqual(set(props["Context"].find("value").text.split(",")), CONTEXT)


if __name__ == "__main__":
    unittest.main()
