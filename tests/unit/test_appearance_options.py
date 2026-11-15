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
    def test_classic_is_auto_and_follows_dark_mode(self):
        # the default: the office's selector resolves "auto" to hst_classic, or hst_classic_dark on a dark UI
        self.assertEqual(ao.value_for("classic"), "auto")

    def test_modern_stores_the_base_style(self):
        # the base style in both modes: the office's selector adds "_dark" in dark mode, and a light UI later
        # must not keep a pinned dark pack
        self.assertEqual(ao.value_for("modern"), "hst_modern")
        with self.assertRaises(ValueError):
            ao.value_for("emoji")

    def test_saving_modern_in_dark_mode_replaces_a_pinned_dark_pack(self):
        from unittest import mock
        node = mock.Mock()
        node.getPropertyValue.return_value = "hst_modern_dark"  # a pinned dark pack
        from hst_office import dialogs
        with mock.patch.object(ao, "_node", return_value=node), mock.patch.object(dialogs, "is_dark", return_value=True):
            self.assertEqual(ao.save_style(None, "modern"), "hst_modern")
        node.setPropertyValue.assert_called_once_with("SymbolStyle", "hst_modern")
        node.commitChanges.assert_called_once()

    def test_saving_classic_rewrites_an_earlier_classic_value_as_auto(self):
        from unittest import mock
        node = mock.Mock()
        node.getPropertyValue.return_value = "hst_classic_dark"  # written by an earlier version in dark mode
        with mock.patch.object(ao, "_node", return_value=node):
            self.assertEqual(ao.save_style(None, "classic"), "auto")
        node.setPropertyValue.assert_called_once_with("SymbolStyle", "auto")

    def test_reading_back(self):
        # "auto" / unset is the default, Cổ điển; hst*: profiles of earlier versions
        for value in ("auto", "", None, "hst_classic", "hst_classic_dark", "hst", "hst_dark"):
            self.assertEqual(ao.style_of(value), "classic", value)
        for value in ("hst_modern", "hst_modern_dark"):
            self.assertEqual(ao.style_of(value), "modern", value)
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
        self.assertEqual(labels, ["Cập nhật", "Giao diện", "Mở tài liệu", "Phiên bản trước", "Đọc số và tiền"])
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

    def test_previews_ship_for_both_ui_modes(self):
        from PIL import Image
        for base in ao.PREVIEWS.values():
            for dark in (False, True):
                path = os.path.join(EXT, "dialogs", ao.preview_file(base, dark))
                self.assertTrue(os.path.isfile(path), path)
                with Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA")
                    self.assertLessEqual(image.size[1], 48)  # fits the 24-unit image control


if __name__ == "__main__":
    unittest.main()
