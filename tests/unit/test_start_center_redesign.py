# SPDX-License-Identifier: AGPL-3.0-only
"""The new Start Center (hst-start-center-redesign.patch), read from the patch: the menu of the left column
(no shared files, no account), the HASON TECH solutions that mirror data/hst/solutions.json, the tiles and the
ids automation uses, the Vietnamese texts, and the thin hook into LibreOffice's files."""
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT
from patch_sections import added, po_entries, sections

PATCH = "hst-start-center-redesign.patch"
UI = "sfx2/uiconfig/ui/hststartcenter.ui"
WINDOW = "sfx2/source/startcenter/hststartcenterwindow.cxx"
HRC = "sfx2/inc/startcenter/hststartcenter.hrc"
PO = "translations/source/vi/sfx2/messages.po"
HOOK = "sfx2/source/dialog/backingcomp.cxx"
SERIES = os.path.join(ROOT, "patches", "libreoffice", "series")

MENU = [("nav_home", "Home", "Trang chủ"), ("nav_new", "New Document", "Tài liệu mới"),
        ("open_all", "Open File", "Mở tệp"), ("nav_recent", "Recent", "Gần đây"),
        ("nav_pinned", "Pinned", "Đã ghim"), ("nav_update", "Update HST Office", "Cập nhật HST Office")]
TILES = [("writer_all", "Văn bản"), ("calc_all", "Bảng tính"), ("impress_all", "Trình chiếu")]


def decode(literal):
    """C++ u"..." body with \\uXXXX escapes -> text."""
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), literal)


class StartCenterRedesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui_text = added(PATCH, UI)
        cls.ui = ET.fromstring(cls.ui_text.encode("utf-8"))
        cls.po = po_entries(added(PATCH, PO))

    def ids(self, element):
        return [o.get("id") for o in element.iter("object") if o.get("id")]

    def label(self, object_id):
        for o in self.ui.iter("object"):
            if o.get("id") == object_id:
                prop = o.find("property[@name='label']")
                return prop.text if prop is not None else None
        return None

    def test_series_position(self):
        with open(SERIES, encoding="utf-8") as handle:
            names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
        self.assertIn(PATCH, names)
        # applies over the former Start Center patches, which it leaves untouched
        for earlier in ("hst-start-center-banner.patch", "hst-unsaved-documents-entry.patch"):
            self.assertLess(names.index(earlier), names.index(PATCH))

    def test_menu_items_in_order(self):
        left = next(o for o in self.ui.iter("object") if o.get("id") == "leftcol")
        buttons = [o.get("id") for o in left.iter("object") if o.get("class") == "GtkButton"
                   and o.get("id").startswith(("nav_", "open_all"))]
        self.assertEqual([m[0] for m in MENU], buttons)
        for object_id, english, vietnamese in MENU:
            self.assertEqual(english, self.label(object_id))
            self.assertEqual((english, vietnamese), self.po["hststartcenter|" + object_id])

    def test_no_shared_files_and_no_account(self):
        for object_id in self.ids(self.ui):
            self.assertNotRegex(object_id.lower(), "share|account|avatar|user")
        for text in re.findall(r">([^<>]+)</property>", self.ui_text):
            self.assertNotIn(text.strip(), ("Shared", "Shared with Me", "Account", "Được chia sẻ"))
        for _, msgstr in self.po.values():
            self.assertNotIn("chia sẻ", msgstr)

    def test_tiles_and_automation_ids(self):
        ids = self.ids(self.ui)
        for object_id, vietnamese in TILES:
            self.assertIn(object_id, ids)
            self.assertEqual(vietnamese, self.po["hststartcenter|" + object_id][1])
        # the former Start Center's ids: LibreOffice's UI tests create documents through them
        for object_id in ("draw_all", "math_all", "database_all", "open_all"):
            self.assertIn(object_id, ids)
        window = added(PATCH, WINDOW)
        self.assertIn('{ u"writer_all"_ustr, u"private:factory/swriter"_ustr }', window)
        self.assertIn('{ u"calc_all"_ustr, u"private:factory/scalc"_ustr }', window)
        self.assertIn('{ u"impress_all"_ustr, u"private:factory/simpress?slot=6686"_ustr }', window)
        self.assertIn('UPDATE_CHECK = u"org.hst.office.update:Check"_ustr', window)

    def test_solutions_mirror_data(self):
        with open(os.path.join(ROOT, "data", "hst", "solutions.json"), encoding="utf-8") as handle:
            expected = [(s["name"], s["tagline"], s["url"]) for s in json.load(handle)["solutions"]]
        rows = re.findall(r'^\s*\{ u"([^"]*)"_ustr,\n\s*u"([^"]*)"_ustr,\n\s*u"([^"]*)"_ustr \},',
                          added(PATCH, WINDOW), re.M)
        self.assertEqual(expected, [tuple(decode(part) for part in row) for row in rows])
        self.assertIn("utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0",
                      added(PATCH, WINDOW))

    def test_every_text_is_translated(self):
        for match in re.finditer(r'context="(hststartcenter\|[^"]+)">([^<]+)<', self.ui_text):
            context, english = match.group(1), match.group(2)
            self.assertIn(context, self.po)
            self.assertEqual(english, self.po[context][0])
            self.assertTrue(self.po[context][1])
        for context, english in re.findall(r'NC_\("(STR_HST_SC_\w+)", "([^"]*)"\)', added(PATCH, HRC)):
            self.assertEqual(english, self.po[context][0])
            self.assertTrue(self.po[context][1])
        self.assertEqual("Chào mừng bạn quay lại", self.po["hststartcenter|welcome"][1])
        self.assertEqual("Tìm kiếm tài liệu gần đây", self.po["hststartcenter|search"][1])
        self.assertEqual("Tạo nhanh tài liệu mới", self.po["hststartcenter|quicktitle"][1])
        self.assertEqual("Các giải pháp chuyển đổi số của HASON TECH", self.po["hststartcenter|solutionstitle"][1])
        self.assertEqual(["Tên", "Đã mở", "Vị trí"],
                         [self.po["hststartcenter|recentcol%d" % i][1] for i in range(3)])
        self.assertEqual("Được ghim", self.po["hststartcenter|pinnedtitle"][1])

    def test_ui_has_no_empty_property(self):
        # VclBuilder (Windows, macOS, gen) nests the following siblings into a self-closing property element
        self.assertNotRegex(self.ui_text, r"<property[^>]*/>")

    def test_thin_hook(self):
        parts = sections(PATCH)
        hook = [line for line in parts[HOOK] if line[:1] in "+-" and not line.startswith(("+++", "---"))]
        self.assertLessEqual(len(hook), 8)
        for path in parts:
            if "/startcenter/" in path or path.endswith(("hststartcenter.ui", "CppunitTest_sfx2_hst_startcenter.mk")):
                self.assertIn("LicenseRef-HST-Proprietary", added(PATCH, path), path)


if __name__ == "__main__":
    unittest.main()
