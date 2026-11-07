# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Giao diện: the icon style choice and the SymbolStyle values it reads and writes."""
import os
import sys
import types
import unittest
import xml.etree.ElementTree as ET

import _paths


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.lang"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import appearance_options as ao  # noqa: E402

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR = "{http://openoffice.org/2001/registry}"
DLG = "{http://openoffice.org/2000/dialog}"


class Mapping(unittest.TestCase):
    def test_modern_is_auto_and_follows_dark_mode(self):
        self.assertEqual(ao.value_for("modern", False), "auto")
        self.assertEqual(ao.value_for("modern", True), "auto")

    def test_classic_picks_the_light_or_dark_pack(self):
        self.assertEqual(ao.value_for("classic", False), "hst")
        self.assertEqual(ao.value_for("classic", True), "hst_dark")
        with self.assertRaises(ValueError):
            ao.value_for("emoji", False)

    def test_reading_back(self):
        for value in ("auto", "", None, "hst_modern", "hst_modern_dark"):
            self.assertEqual(ao.style_of(value), "modern", value)
        for value in ("hst", "hst_dark"):
            self.assertEqual(ao.style_of(value), "classic", value)
        self.assertIsNone(ao.style_of("colibre"))  # chosen in the core Appearance page: neither box is ticked


class Page(unittest.TestCase):
    def test_options_leaves_join_the_hst_office_group(self):
        root = ET.parse(os.path.join(EXT, "OptionsDialog.xcu")).getroot()
        node = next(n for n in root.iter("node") if n.get(OOR + "name") == "vn.hasontech.hstoffice.Options")
        props = {p.get(OOR + "name"): p.find("value").text for p in node.findall("prop")}
        self.assertEqual(props["Label"], "HST Office")  # same label as the product group
        self.assertEqual(props["AllModules"], "true")  # otherwise Tools ▸ Options hides the node in every module
        leaves = {leaf.get(OOR + "name"): {p.get(OOR + "name"): p.find("value").text for p in leaf.findall("prop")}
                  for leaf in next(n for n in node if n.get(OOR + "name") == "Leaves")}
        labels = sorted(v["Label"] for v in leaves.values())
        self.assertEqual(labels, ["Giao diện", "Mở tài liệu"])
        for leaf in leaves.values():
            self.assertEqual(leaf["Id"], "vn.hasontech.hst.vietnamese-tools")
            self.assertTrue(os.path.isfile(os.path.join(EXT, leaf["OptionsPage"].replace("%origin%/", ""))))

    def test_appearance_page_controls(self):
        root = ET.parse(os.path.join(EXT, "dialogs", "Appearance.xdl")).getroot()
        controls = {c.get(DLG + "id"): c.get(DLG + "value") for c in root.iter() if c.get(DLG + "id")}
        self.assertEqual(controls["modern"], "Hiện đại (nhiều màu)")
        self.assertEqual(controls["classic"], "Cổ điển")
        self.assertEqual(controls["heading"], "Kiểu biểu tượng")
        self.assertTrue(set(ao.PREVIEWS) <= set(controls))


if __name__ == "__main__":
    unittest.main()
