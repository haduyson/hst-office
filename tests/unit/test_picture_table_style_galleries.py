# SPDX-License-Identifier: AGPL-3.0-only
"""Picture and table style galleries (hst-picture-table-style-galleries*.patch).

The pieces live in different files that must agree: the style table and the strings it names, the
Vietnamese translations, the controller and protocol handler registrations, the C++ implementations,
the gallery .ui ids the code looks up, and the six ribbon placements. These tests read the patches only.
"""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
CORE = os.path.join(PATCHES, "hst-picture-table-style-galleries.patch")
STRINGS = os.path.join(PATCHES, "hst-picture-table-style-galleries-strings.patch")
PLACEMENT = os.path.join(PATCHES, "hst-picture-table-style-galleries-ui.patch")
DATA = "svx/source/tbxctrls/HstStyleGalleryData.cxx"
HRC = "svx/inc/hststylegallery.hrc"
WINDOW = "svx/source/tbxctrls/HstStyleGalleryWindow.cxx"
UI = "svx/uiconfig/ui/hststylegallery.ui"
GRIDS = {
    "sw/uiconfig/swriter/ui/notebookbar.ui": ("gdImageFillBorder", "gdTableStyle"),
    "sc/uiconfig/scalc/ui/notebookbar.ui": ("gdImageFillBorder", "gdTableDesignMain"),
    "sd/uiconfig/simpress/ui/notebookbar.ui": ("gdImageFillBorder", "gdTableLayout"),
}


def added(path):
    """{file: text of its added lines} of a unified diff."""
    result, current = {}, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None and line.startswith("+"):
                current.append(line[1:])
    return {name: "".join(lines) for name, lines in result.items()}


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class StyleGalleries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = added(CORE)
        cls.strings = added(STRINGS)
        cls.placement = added(PLACEMENT)
        cls.data = cls.core[DATA]

    def test_series_order(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        core, strings, ui = (series.index(os.path.basename(p)) for p in (CORE, STRINGS, PLACEMENT))
        self.assertLess(core, strings)
        self.assertLess(strings, ui)
        adaptive = [i for i, name in enumerate(series) if name.startswith("hst-ribbon-adaptive-")]
        self.assertTrue(all(i < ui for i in adaptive), "the placements go after the ribbon ladder patches")

    def test_six_to_eight_styles_each(self):
        pictures = re.findall(r'\{ u"([a-z-]+)", RID_HST_PICSTYLE_', self.data)
        tables = re.findall(r'\{ u"(HST [A-Za-z ]+)", RID_HST_TABLESTYLE_', self.data)
        for ids in (pictures, tables):
            self.assertTrue(6 <= len(ids) <= 8, ids)
            self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("none", pictures, "one tile removes the style")

    def test_every_string_is_translated(self):
        ids = re.findall(r'NC_\("(RID_HST_[A-Z_]+)", "([^"]+)"\)', self.core[HRC])
        po = self.strings["translations/source/vi/svx/messages.po"]
        for context, english in ids:
            self.assertIn(f'msgctxt "{context}"\nmsgid "{english}"\nmsgstr "', po)
            self.assertNotIn(f'msgctxt "{context}"\nmsgid "{english}"\nmsgstr ""', po)
            self.assertIn(context, self.data + self.core[WINDOW] + self.core["svx/source/tbxctrls/HstStyleDispatcher.cxx"],
                          f"{context} is used")
        for context in re.findall(r'context="(hststylegallery\|[a-z-]+)"', self.core[UI]):
            self.assertIn(f'msgctxt "{context}"', po)
        ui_po = self.strings["translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po"]
        for command in ("HstPictureStyles", "HstTableStyles"):
            self.assertIn(f".uno:{command}", self.core["officecfg/registry/data/org/openoffice/Office/UI/GenericCommands.xcu"])
            self.assertIn(f"Commands..uno:{command}\\n", ui_po)

    def test_registrations(self):
        component = self.core["svx/util/svxcore.component"]
        for name in ("HstStyleGalleryControl", "HstStyleDispatcher"):
            self.assertIn(f'constructor="com_sun_star_comp_svx_{name}_get_implementation"', component)
            cxx = self.core[f"svx/source/tbxctrls/{name}.cxx"]
            self.assertIn(f"com_sun_star_comp_svx_{name}_get_implementation", cxx)
        controllers = self.core["officecfg/registry/data/org/openoffice/Office/UI/Controller.xcu"]
        self.assertEqual(controllers.count("com.sun.star.comp.svx.HstStyleGalleryControl"), 2)
        self.assertIn("<value>vnd.hst.styles:*</value>",
                      self.core["officecfg/registry/data/org/openoffice/Office/ProtocolHandler.xcu"])
        makefile = self.core["svx/Library_svxcore.mk"]
        for name in re.findall(r"^\+\+\+ b/svx/source/tbxctrls/(\w+)\.cxx", open(CORE, encoding="utf-8").read(), re.M):
            self.assertIn(f"svx/source/tbxctrls/{name} \\", makefile)
        self.assertIn("svx/source/table/HstSlidesTableStyle \\", makefile)
        self.assertIn("sc/source/core/data/HstTableStyles \\", self.core["sc/Library_sc.mk"])
        self.assertIn("ScHstTableStyles::Register(*this);", self.core["sc/source/core/data/documen9.cxx"])

    def test_ui_ids_the_code_uses(self):
        for widget in re.findall(r'weld_\w+\(u"(\w+)"_ustr\)', self.core[WINDOW]):
            self.assertIn(f'id="{widget}"', self.core[UI])
        self.assertIn('u"svx/ui/hststylegallery.ui"_ustr, u"StyleGalleryBox"_ustr', self.core[WINDOW])

    def test_each_grid_gets_one_gallery(self):
        for path, (picture_grid, table_grid) in GRIDS.items():
            text = self.placement[path]
            for kind in ("Picture", "Table"):
                self.assertEqual(text.count(f'id="hst{kind}StylesGallery"'), 1, path)
                self.assertEqual(text.count(f"<property name=\"action-name\">.uno:Hst{kind}Styles</property>"), 1)
            suppr = self.placement[f"solenv/sanitizers/ui/modules/{path.split('/')[2]}.suppr"]
            self.assertIn("hstPictureStylesGallery", suppr)
            self.assertIn("hstTableStylesGallery", suppr)
        header = open(PLACEMENT, encoding="utf-8").read().split("\n---\n")[0]
        for picture_grid, table_grid in GRIDS.values():
            self.assertIn(picture_grid, header)
            self.assertIn(table_grid, header)

    def test_header_text_is_readable(self):
        rows = re.findall(r'\{ u"(HST [A-Za-z ]+)", RID_HST_TABLESTYLE_\w+, ([^}]+)\}', self.data.replace("\n", " "))
        named = {"HST_BLUE": "0072BB", "HST_CHARCOAL": "322E2E", "COL_WHITE": "FFFFFF"}
        for name, body in rows:
            colours = []
            for token in re.findall(r"Color\(0x(\w\w), 0x(\w\w), 0x(\w\w)\)|(HST_BLUE|HST_CHARCOAL|COL_WHITE|COL_TRANSPARENT)", body):
                colours.append("".join(token[:3]) if token[0] else named.get(token[3]))
            fill, text = colours[0], colours[1]
            # bold header text on its fill (or on the white page): WCAG large text, 3:1
            self.assertGreaterEqual(contrast(fill or "FFFFFF", text), 3.0, name)


if __name__ == "__main__":
    unittest.main()
