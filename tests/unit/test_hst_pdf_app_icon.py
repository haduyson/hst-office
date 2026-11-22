# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST PDF's own app icon (crimson tile, folded page, the letters "PDF" as outlines): one master for every size, made
into the Linux hicolor set, the Windows .ico copied into the source tree and the macOS launcher icon."""
import importlib.util
import json
import os
import tempfile
import unittest

import _paths

ROOT = _paths.ROOT
SPEC = json.load(open(os.path.join(ROOT, "assets", "brand", "brand-spec.json"), encoding="utf-8"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HstPdfIcon(unittest.TestCase):
    def test_brand_spec_lists_it_with_every_output(self):
        module = next(m for m in SPEC["appIcons"]["modules"] if m["id"] == "pdf")
        self.assertEqual((module["name"], module["color"]), ("hst-pdf", "#D0312D"))
        self.assertEqual(SPEC["windowsAppIcons"]["icons"]["pdf_app.ico"], "pdf")
        for size in SPEC["appIcons"]["sizes"]:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "assets", "brand", "icons", "hst-pdf-%d.png" % size)))
        for path in ("assets/brand/icons/hst-pdf.svg", "branding/icons/app/hst-pdf.png", "branding/macos/hst-pdf.icns",
                     "branding/windows/app-icons/pdf_app.ico"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)

    def test_master_is_plain_svg_with_outlined_letters(self):
        with open(os.path.join(ROOT, "branding", "icons", "app", "hst-pdf.svg"), encoding="utf-8") as handle:
            svg = handle.read()
        self.assertNotIn("<text", svg)  # letters are paths: no font dependency
        self.assertNotIn("<image", svg)
        self.assertIn('fill-rule="evenodd"', svg)
        self.assertIn("#D0312D", svg)

    def test_windows_ico_is_copied_into_the_tree(self):
        overrides = load("apply_icon_overrides", "scripts/brand/apply-icon-overrides.py")
        with tempfile.TemporaryDirectory() as tree:
            icons = os.path.join(tree, "sysui", "desktop", "icons")
            os.makedirs(icons)
            for name in overrides.SYSUI_ICONS:
                open(os.path.join(icons, name), "wb").close()
            os.makedirs(os.path.join(tree, "icon-themes", "colibre", "res"))
            open(os.path.join(tree, "icon-themes", "colibre", "res", "mainapp_16.png"), "wb").close()
            pairs, missing = overrides.plan(tree)
        self.assertEqual(missing, [])
        self.assertIn((os.path.join(overrides.APP_ICONS, "pdf_app.ico"), os.path.join(icons, "pdf_app.ico")), pairs)


if __name__ == "__main__":
    unittest.main()
