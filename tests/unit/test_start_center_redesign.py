# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The new Start Center (hst-start-center-redesign.patch), read from the patch: the menu of the left column
(no shared files, no account), the HASON TECH solutions that mirror data/hst/solutions.json, the tiles and the
ids automation uses, the Vietnamese texts, the HST application icons, the shared HST design tokens and the thin
hook into LibreOffice's files."""
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT
from patch_sections import added, po_entries, sections

PATCH = "hst-start-center-redesign.patch"
UIS = ("sfx2/uiconfig/ui/hststartcentersearch.ui",)
WINDOW = "sfx2/source/startcenter/hststartcenterwindow.cxx"
ICONS = "sfx2/source/startcenter/hststartcentericons.cxx"
LOGOS = "sfx2/source/startcenter/hststartcenterlogos.cxx"
HRC = "sfx2/inc/startcenter/hststartcenter.hrc"
PO = "translations/source/vi/sfx2/messages.po"
HOOK = "sfx2/source/dialog/backingcomp.cxx"
TOKENS_HXX = "include/vcl/hst/designtokens.hxx"
TOKENS = "vcl/source/hst/designtokens.cxx"
HELPERS = "vcl/source/hst/drawhelpers.cxx"
SERIES = os.path.join(ROOT, "patches", "libreoffice", "series")

# the menu, in display order: its string, its context and its texts
MENU = [("STR_HST_SC_NAV_HOME", "nav_home", "Home", "Trang chủ"),
        ("STR_HST_SC_NAV_NEW", "nav_new", "New Document", "Tài liệu mới"),
        ("STR_HST_SC_NAV_OPEN", "open_all", "Open File", "Mở tệp"),
        ("STR_HST_SC_NAV_UNSAVED", "nav_unsaved", "Unsaved Documents", "Tài liệu chưa lưu"),
        ("STR_HST_SC_NAV_RECENT", "nav_recent", "Recent", "Gần đây"),
        ("STR_HST_SC_NAV_PINNED", "nav_pinned", "Pinned", "Đã ghim"),
        ("STR_HST_SC_NAV_UPDATE", "nav_update", "Update HST Office", "Cập nhật HST Office")]
TILES = [("writer_all", "Văn bản"), ("calc_all", "Bảng tính"), ("impress_all", "Trình chiếu")]
ICON_ASSETS = {"SVG_WRITER": "hst-writer.svg", "SVG_SHEETS": "hst-sheets.svg", "SVG_SLIDES": "hst-slides.svg",
               "SVG_DRAW": "hst-draw.svg", "SVG_PDF": "hst-pdf.svg"}


def decode(literal):
    """C++ u"..." body with \\uXXXX escapes -> text."""
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), literal)


class StartCenterRedesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui_texts = [added(PATCH, path) for path in UIS]
        cls.ui_text = "\n".join(cls.ui_texts)
        cls.uis = [ET.fromstring(text.encode("utf-8")) for text in cls.ui_texts]
        cls.po = po_entries(added(PATCH, PO))
        cls.hrc = dict((name, (context, english)) for name, context, english in re.findall(
            r'#define (STR_HST_SC_\w+)\s+NC_\("([^"]+)", "([^"]*)"\)', added(PATCH, HRC)))
        cls.window = added(PATCH, WINDOW)

    def ids(self):
        return [o.get("id") for ui in self.uis for o in ui.iter("object") if o.get("id")]

    def test_one_toplevel_per_ui_file(self):
        # VclBuilder (Windows, macOS) builds every toplevel of a .ui into the window that asks for one: the search
        # entry's file holds only it
        for path, ui in zip(UIS, self.uis):
            self.assertEqual(1, len(ui.findall("object")), path)
        self.assertEqual("SearchBox", self.uis[0].find("object").get("id"))
        self.assertIn('u"sfx/ui/hststartcentersearch.ui"_ustr, u"SearchBox"_ustr', self.window)
        self.assertNotIn("hststartcenter.ui", self.window)

    def test_no_banner_in_the_start_center(self):
        # the owner took the HASON TECH banner out of the Start Center (the ribbon and the File panel keep theirs):
        # no banner widget, no banner .ui, nothing that fetches the feed
        self.assertFalse([path for path in sections(PATCH) if "banner" in path])
        for path in sections(PATCH):
            if "/startcenter/" in path:
                self.assertNotRegex(added(PATCH, path), r"HstBanner|BannerBox|FocusBanner|aBanner\b", path)

    def test_series_position(self):
        with open(SERIES, encoding="utf-8") as handle:
            names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
        self.assertIn(PATCH, names)
        # applies over the former Start Center patches, which it leaves untouched
        for earlier in ("hst-start-center-banner.patch", "hst-unsaved-documents-entry.patch"):
            self.assertLess(names.index(earlier), names.index(PATCH))

    def test_menu_items_in_order(self):
        order = re.search(r"const TranslateId aNav\[NAV_COUNT\]\s*=\s*\{([^}]*)\}", self.window)
        self.assertEqual([m[0] for m in MENU], re.findall(r"STR_HST_SC_NAV_\w+", order.group(1)))
        for name, context, english, vietnamese in MENU:
            self.assertEqual(("hststartcenter|" + context, english), self.hrc[name])
            self.assertEqual((english, vietnamese), self.po["hststartcenter|" + context])

    def test_only_search_is_a_widget(self):
        # everything else is drawn by the canvas
        self.assertEqual(["SearchBox", "search", "search-atkobject"], self.ids())

    def test_no_shared_files_and_no_account(self):
        for name, (context, english) in self.hrc.items():
            self.assertNotRegex((context + english).lower(), "share|account|avatar")
        for _, msgstr in self.po.values():
            self.assertNotIn("chia sẻ", msgstr)
        self.assertNotRegex(self.window.lower(), "account|avatar")

    def test_tiles_and_automation_ids(self):
        for object_id, vietnamese in TILES:
            self.assertEqual(vietnamese, self.po["hststartcenter|" + object_id][1])
        self.assertIn('{ u"writer_all"_ustr, u"private:factory/swriter"_ustr }', self.window)
        self.assertIn('{ u"calc_all"_ustr, u"private:factory/scalc"_ustr }', self.window)
        self.assertIn('{ u"impress_all"_ustr, u"private:factory/simpress?slot=6686"_ustr }', self.window)
        # the former Start Center's ids: automation creates documents through them
        for object_id in ("draw_all", "math_all", "database_all"):
            self.assertRegex(self.window, r'\{ u"%s"_ustr, u"private:factory/' % object_id)
        self.assertIn('u"open_all"_ustr', self.window)
        self.assertIn('UPDATE_CHECK = u"org.hst.office.update:Check"_ustr', self.window)
        self.assertIn('UNSAVED_DOCUMENTS = u"org.hst.office.vi:UnsavedDocuments"_ustr', self.window)

    def test_solutions_mirror_data(self):
        with open(os.path.join(ROOT, "data", "hst", "solutions.json"), encoding="utf-8") as handle:
                solutions = json.load(handle)["solutions"]
        # name, full tagline (tooltip and accessible description), short taglines (on the card: Vietnamese, English), page
        expected = [(s["name"], s["tagline"], s.get("short", ""), s.get("shortEn", ""), s["url"]) for s in solutions]
        rows = re.findall(r'^\s*\{ u"([^"]*)"_ustr,\n\s*u"([^"]*)"_ustr,\n\s*u"([^"]*)"_ustr,\n\s*u"([^"]*)"_ustr,\n'
                          r'\s*u"([^"]*)"_ustr \},', self.window, re.M)
        self.assertEqual(expected, [tuple(decode(part) for part in row) for row in rows])
        for solution in solutions:
            # short enough for two lines of a card in two columns
            self.assertLessEqual(len(solution.get("short", "")), 38, solution["id"])
            self.assertTrue(solution.get("shortEn"), solution["id"])
            self.assertLessEqual(len(solution["shortEn"]), 38, solution["id"])
        self.assertIn("utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0", self.window)
        self.assertIn('MORE_SOLUTIONS_TEXT = u"Xem thêm các giải pháp khác →"_ustr', self.window)

    def test_every_text_is_translated(self):
        for match in re.finditer(r'context="(hststartcenter\|[^"]+)">([^<]+)<', self.ui_text):
            context, english = match.group(1), match.group(2)
            self.assertEqual(english, self.po[context][0])
            self.assertTrue(self.po[context][1])
        for name, (context, english) in self.hrc.items():
            self.assertIn(context, self.po, name)
            self.assertEqual(english, self.po[context][0], name)
            self.assertTrue(self.po[context][1], name)
        self.assertEqual("Chào mừng bạn quay lại", self.po["hststartcenter|welcome"][1])
        self.assertEqual("Tìm kiếm tài liệu gần đây", self.po["hststartcenter|search"][1])
        self.assertEqual("Tạo nhanh tài liệu mới", self.po["hststartcenter|quicktitle"][1])
        self.assertEqual("HASON TECH - Giải pháp chuyển đổi số", self.po["hststartcenter|solutionstitle"][1])
        self.assertEqual("HASON TECH - Digital solutions", self.po["hststartcenter|solutionstitle"][0])
        self.assertEqual(["Tên", "Đã mở", "Vị trí"],
                         [self.po["hststartcenter|recentcol%d" % i][1] for i in range(3)])
        self.assertEqual("Được ghim", self.po["hststartcenter|pinnedtitle"][1])

    def test_app_icons_are_the_brand_assets(self):
        # the HST application icons, embedded verbatim (the branding files are not all installed)
        icons = added(PATCH, ICONS)
        for constant, asset in ICON_ASSETS.items():
            embedded = re.search(r'%s = R"HSTSVG\((.*?)\)HSTSVG"' % constant, icons, re.S)
            self.assertIsNotNone(embedded, constant)
            with open(os.path.join(ROOT, "assets", "brand", "icons", asset), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), embedded.group(1), asset)

    def test_solution_logos_are_the_assets(self):
        # each card shows its solution's logo: the 24 and 48 px PNGs of solutions.json's "icon", embedded byte
        # for byte, in the order of the cards
        with open(os.path.join(ROOT, "data", "hst", "solutions.json"), encoding="utf-8") as handle:
            solutions = json.load(handle)["solutions"]
        logos = added(PATCH, LOGOS)
        arrays = dict((name, bytes(int(b, 16) for b in re.findall(r"0x([0-9a-f]{2})", body)))
                      for name, body in re.findall(r"constexpr sal_uInt8 (PNG_\w+)\[\] = \{(.*?)\};", logos, re.S))
        order = re.findall(r"\{ (PNG_\w+)_24, sizeof", logos)
        self.assertEqual(["PNG_" + s["id"].upper().replace("-", "_") for s in solutions], order)
        for solution in solutions:
            icon = solution.get("icon")
            self.assertEqual("assets/start-center/solutions/%s-24.png" % solution["id"], icon)
            for size in (24, 48):
                path = os.path.join(ROOT, icon.replace("-24.png", "-%d.png" % size))
                with open(path, "rb") as handle:
                    data = handle.read()
                self.assertEqual(b"\x89PNG", data[:4], path)
                self.assertEqual((size, size), (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")))
                name = "PNG_%s_%d" % (solution["id"].upper().replace("-", "_"), size)
                self.assertEqual(data, arrays.get(name), name)

    def test_app_icon_rasters_are_the_brand_icons(self):
        # the application icons come from the brand's own PNGs (no SVG rendered at start-up), byte for byte, each
        # name with its sizes in ascending order (the lookup takes the first one large enough)
        logos = added(PATCH, LOGOS)
        arrays = dict((name, bytes(int(b, 16) for b in re.findall(r"0x([0-9a-f]{2})", body)))
                      for name, body in re.findall(r"constexpr sal_uInt8 (PNG_\w+)\[\] = \{(.*?)\};", logos, re.S))
        rows = re.findall(r'\{ "([a-z-]+)", (\d+), (PNG_\w+), sizeof\(\3\) \},', logos)
        names = ["hst-writer", "hst-sheets", "hst-slides", "hst-draw", "hst-pdf"]
        self.assertEqual(names, list(dict.fromkeys(name for name, _size, _array in rows)))
        for name in names:
            sizes = [int(size) for row, size, _array in rows if row == name]
            self.assertEqual(sorted(sizes), sizes, name)
            self.assertIn(24, sizes, name)
        for name, size, array in rows:
            path = os.path.join(ROOT, "assets", "brand", "icons", "%s-%s.png" % (name, size))
            with open(path, "rb") as handle:
                data = handle.read()
            self.assertEqual((int(size), int(size)), (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")))
            self.assertEqual(data, arrays.get(array), array)
        icons = added(PATCH, ICONS)
        for name in names:
            self.assertIn('return "%s";' % name, icons)
        self.assertLess(icons.index("RenderAppIconRaster("), icons.index("ImportGraphic("))

    def test_visual_constants_are_design_tokens(self):
        # every colour lives in the shared HST tokens; the Start Center's sources hold none of their own
        for path in sections(PATCH):
            if "/startcenter/" in path and path not in (ICONS, LOGOS):
                self.assertNotRegex(added(PATCH, path), r"Color\(0x|\bCOL_(?!TRANSPARENT\b|WHITE\b|BLACK\b)[A-Z]", path)
        tokens = added(PATCH, TOKENS)
        for hex_colour in ("0xEC, 0xF3, 0xFC", "0xEA, 0xF2, 0xFD", "0x0A, 0x47, 0x96", "0x1A, 0x56, 0xC8"):
            self.assertIn(hex_colour, tokens)
        header = added(PATCH, TOKENS_HXX)
        for token in ("namespace radius", "namespace space", "namespace type", "namespace icon",
                      "SHADOW_LAYERS", "FOCUS_RING_WIDTH", "aPressed", "aHover"):
            self.assertIn(token, header)
        helpers = added(PATCH, HELPERS)
        for helper in ("DrawRoundRect", "DrawCard", "DrawPill", "DrawBadge", "DrawFocusRing", "DrawBackground"):
            self.assertIn("void %s(" % helper, helpers)

    def test_ui_has_no_empty_property(self):
        # VclBuilder (Windows, macOS, gen) nests the following siblings into a self-closing property element
        self.assertNotRegex(self.ui_text, r"<property[^>]*/>")

    def test_thin_hook(self):
        parts = sections(PATCH)
        hook = [line for line in parts[HOOK] if line[:1] in "+-" and not line.startswith(("+++", "---"))]
        self.assertLessEqual(len(hook), 8)
        for path in parts:
            if ("/startcenter/" in path or "/hst/" in path
                    or path.endswith(("hststartcenter.ui", "CppunitTest_sfx2_hst_startcenter.mk"))):
                self.assertIn("LicenseRef-HST-Proprietary", added(PATCH, path), path)


if __name__ == "__main__":
    unittest.main()
