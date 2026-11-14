# SPDX-License-Identifier: AGPL-3.0-only
"""Compact ribbon (Ctrl+F1) of hst-ribbon-adaptive-compact.patch: quick command rows (data/ribbon/quick-rows.json and
the header generated from it), the dropped page, the per-app state and the 32 px document tab strip."""
import importlib.util
import json
import os
import unittest

from _paths import ROOT
from patch_sections import added, po_entries, sections

PATCH = "hst-ribbon-adaptive-compact.patch"
DATA = os.path.join(ROOT, "data", "ribbon", "quick-rows.json")
HEADER = "sfx2/source/notebookbar/HstRibbonQuickRows.hxx"

# the approved mockup (v2) rows of Writer's Home and Insert tabs
MOCKUP = {
    "pmhbHome": [".uno:Paste", ".uno:Cut", ".uno:Copy", "|", ".uno:Bold", ".uno:Italic", ".uno:Underline", "|",
                 ".uno:CenterPara", ".uno:DefaultBullet", "|", ".uno:SearchDialog", "org.hst.office.vi:Nd30Wizard"],
    "pmhbInsert": [".uno:TitlePageDialog", ".uno:InsertPagebreak", "|", ".uno:InsertTable", ".uno:InsertGraphic",
                   ".uno:BasicShapes", ".uno:InsertObjectChart", "|", ".uno:HyperlinkDialog", ".uno:InsertAnnotation",
                   "|", ".uno:InsertPageHeader", ".uno:PageNumberWizard", "|", ".uno:DrawText",
                   ".uno:CharmapControl"],
}


def generator():
    path = os.path.join(ROOT, "scripts", "patches", "generate-ribbon-quick-rows.py")
    spec = importlib.util.spec_from_file_location("generate_ribbon_quick_rows", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuickRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA, encoding="utf-8") as handle:
            cls.data = json.load(handle)

    def test_writer_home_and_insert_follow_the_mockup(self):
        rows = {r["box"]: r["commands"] for r in self.data["rows"] if r["app"] == "writer"}
        for box, commands in MOCKUP.items():
            self.assertEqual(rows[box], commands, box)

    def test_every_tab_of_the_four_apps_has_one_row(self):
        keys = [(r["app"], r["box"]) for r in self.data["rows"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual({app for app, _ in keys}, {"writer", "calc", "impress", "draw"})
        for app in ("writer", "calc", "impress", "draw"):
            self.assertIn((app, "pmhbHome"), keys)
            self.assertNotIn((app, "pmhbFile"), keys)  # the File tab opens the File page

    def test_home_rows_are_hand_made_in_one_form(self):
        rows = {(r["app"], r["box"]): r for r in self.data["rows"]}
        for app in ("writer", "calc", "impress", "draw"):
            row = rows[(app, "pmhbHome")]
            self.assertFalse(row.get("generated"), app)
            self.assertEqual(row["commands"][:3], [".uno:Paste", ".uno:Cut", ".uno:Copy"], app)
            self.assertIn(".uno:Bold", row["commands"], app)
            self.assertIn(".uno:SearchDialog", row["commands"], app)
            self.assertLessEqual(len([c for c in row["commands"] if c != "|"]), 10, app)

    def test_generated_rows_skip_fine_tuning_items(self):
        for row in self.data["rows"]:
            if row.get("generated"):
                for word in generator().SKIP_COMMANDS:
                    self.assertFalse([c for c in row["commands"] if word in c], (row["box"], word))

    def test_generated_rows_hold_at_most_ten_commands(self):
        for row in self.data["rows"]:
            commands = [c for c in row["commands"] if c != "|"]
            self.assertTrue(commands, row["box"])
            self.assertEqual(len(commands), len(set(commands)), row["box"])
            if row.get("generated"):
                self.assertLessEqual(len(commands), 10, row["box"])

    def test_patch_header_is_generated_from_the_data(self):
        body = "\n".join(line[1:] for line in sections(PATCH)[HEADER] if line.startswith("+")) + "\n"
        self.assertEqual(body, generator().header(self.data))


class CompactWiring(unittest.TestCase):
    def test_ctrl_f1_double_click_and_chevrons_toggle(self):
        tabs = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("pKey->GetKeyCode().GetFullCode() != (KEY_F1 | KEY_MOD1)", tabs)
        self.assertIn("if (rMEvt.GetClicks() == 2)", tabs)
        self.assertIn("LINK(this, NotebookbarTabControl, HstToggleHdl)", tabs)
        self.assertIn("if (nChosen == HST_COMPACT_ITEM && m_pHstCompact)", tabs)  # the ≡ menu entry
        # the bar takes its new height and the window gives the document the difference
        self.assertIn("pBar->SetSizePixel(Size(pBar->GetSizePixel().Width(), 0));", tabs)

    def test_compact_band_and_banner(self):
        compact = added(PATCH, "sfx2/source/notebookbar/HstRibbonCompact.cxx")
        self.assertIn("return px(80, fDpi);", compact)
        tabs = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("HstSetRowReserve(nReserve);", tabs)
        self.assertIn("stripSlot(HstRibbonCompact::BandHeight(fDpi), fDpi)", tabs)

    def test_chosen_tab_drops_its_page_and_file_tab_does_not(self):
        tabs = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("rEvent.GetId() != VclEventId::TabpageActivate", tabs)
        self.assertIn("if (GetPageName(nPageId) != hst::ribbon::FILE_TAB_NAME)\n        HstDrop();", tabs)
        drop = added(PATCH, "vcl/source/control/HstRibbonDrop.cxx")
        self.assertIn("m_xPage->SetParent(m_xTabs);", drop)  # the page returns when the popup ends
        self.assertIn("rEvent.GetId() != VclEventId::ToolboxSelect", drop)  # a command closes it
        self.assertIn("HstCloseDrop(); // the dropped page returns", added(PATCH, "vcl/source/control/tabctrl.cxx"))

    def test_state_is_remembered_per_app(self):
        schema = added(PATCH, "officecfg/registry/schema/org/openoffice/Office/HSTRibbon.xcs")
        self.assertIn('<prop oor:name="CompactApps" oor:type="oor:string-list" oor:nillable="false">', schema)
        compact = added(PATCH, "sfx2/source/notebookbar/HstRibbonCompact.cxx")
        self.assertIn('SetAppListed(u"CompactApps"_ustr, m_aApp, bCompact);', compact)
        self.assertNotIn("officecfg::", compact)  # no generated header: builds that skip officecfg still compile

    def test_tooltips_are_translated(self):
        entries = po_entries(added(PATCH, "translations/source/vi/sfx2/messages.po"))
        self.assertEqual(entries["STR_HST_RIBBON_COLLAPSE"][1], "Thu gọn ribbon (Ctrl+F1)")
        self.assertEqual(entries["STR_HST_RIBBON_EXPAND"][1], "Hiện đầy đủ ribbon (Ctrl+F1)")

    def test_new_sources_are_built(self):
        self.assertIn("vcl/source/control/HstRibbonDrop \\", added(PATCH, "vcl/Library_vcl.mk"))
        sfx = added(PATCH, "sfx2/Library_sfx.mk")
        self.assertIn("sfx2/source/notebookbar/HstRibbonCompact \\", sfx)
        self.assertIn("sfx2/source/notebookbar/HstRibbonCompactWidgets \\", sfx)

    def test_page_never_laid_out_at_full_width_first(self):
        tabctrl = added(PATCH, "vcl/source/control/tabctrl.cxx")
        self.assertIn("tools::Long nW = nWidth-TAB_OFFSET*2 - ImplHstPageReserve();", tabctrl)
        self.assertIn("pItem->mpTabPage->GetParent() != this", tabctrl)  # the dropped page is the popup's
        tabs = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("HstSetPageReserve(nPageWidth > 0 ? aPage.w - nPageWidth : 0);", tabs)
        self.assertNotIn("pPage->SetPosSizePixel(aPos, Size(nPageWidth, aPage.h));", tabs)

    def test_document_tab_strip_is_32_px(self):
        self.assertIn("BAR_HEIGHT = 32", added(PATCH, "framework/source/uielement/documenttabbar.cxx"))


if __name__ == "__main__":
    unittest.main()
