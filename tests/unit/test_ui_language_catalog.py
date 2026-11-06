# SPDX-License-Identifier: AGPL-3.0-only
"""Language menu catalog, placeholders and placement."""
import os
import string
import unittest
import xml.etree.ElementTree as ET
import _paths
from hst_office import ui_language as ui
from hst_office.data_files import load_locale

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR, XML = "{http://openoffice.org/2001/registry}", "{http://www.w3.org/XML/1998/namespace}"


class CatalogTest(unittest.TestCase):
    def test_catalog_keys_and_placeholders_match(self):
        vi, en = (load_locale(code)["uiLanguage"] for code in ("vi", "en"))

        def compare(left, right):
            self.assertEqual(set(left), set(right))
            for key, value in left.items():
                if isinstance(value, dict):
                    compare(value, right[key])
                else:
                    self.assertTrue(value)
                    self.assertTrue(right[key])
                    fields = lambda text: {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}
                    self.assertEqual(fields(value), fields(right[key]), key)

        compare(vi, en)
        self.assertEqual(vi["names"], {"vi": "Tiếng Việt", "en-US": "English", "": "Theo máy"})
        self.assertEqual(set(vi), {"title", "locked", "selected", "saveError", "restart", "restartNow", "later", "names"})

    def test_menu_titles_urls_contexts_and_placement(self):
        root = ET.parse(os.path.join(EXT, "Addons.xcu")).getroot()
        menu = root.find("./node/node[@%sname='OfficeMenuBar']/node[@%sname='org.hst.office.vi']/node" % (OOR, OOR))
        # Placement: test_hst_menu_order keeps Giải pháp and Kiểm tra cập nhật last.
        m8 = menu.find("node[@%sname='m8']" % OOR)
        children = m8.findall("node/node")
        labels = ("Ngôn ngữ giao diện", "Tiếng Việt", "English", "Theo máy")
        self.assertEqual([node.find("prop[@%sname='URL']/value" % OOR).text for node in children],
                         ["org.hst.office.vi:" + command for command in ui.COMMANDS])
        solutions = next(node for node in menu if node.find("prop[@%sname='URL']/value" % OOR) is not None
                         and node.find("prop[@%sname='URL']/value" % OOR).text == "org.hst.office.vi:ShowSolutions")
        context = solutions.find("prop[@%sname='Context']/value" % OOR).text  # every module incl. the Start Center
        for node, title in zip([m8] + children, labels):
            self.assertEqual({value.get(XML + "lang", ""): value.text for value in node.findall("prop[@%sname='Title']/value" % OOR)},
                             {"": title, "en-US": title, "vi": title})
            self.assertEqual(node.find("prop[@%sname='Context']/value" % OOR).text, context)
            self.assertEqual(node.find("prop[@%sname='Target']/value" % OOR).text, "_self")
        # No add-on ribbon row at all: the Extensions tab is authored in notebookbar.ui.
        self.assertIsNone(root.find("./node/node[@%sname='OfficeNotebookBar']" % OOR))
        for code in ("vi", "en"):
            catalog = load_locale(code)["menu"]
            self.assertEqual(tuple(catalog[key] for key in ("uiLanguage", "uiLanguageVi", "uiLanguageEn", "uiLanguageSystem")), labels)


if __name__ == "__main__":
    unittest.main()
