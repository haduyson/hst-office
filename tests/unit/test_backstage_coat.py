# SPDX-License-Identifier: AGPL-3.0-only
"""The File tab (backstage) in the HST frame coat (hst-ui-coat-backstage.patch), read from the patch.

The drawing itself (token colours, pill, focus ring, item height, no colour literal in the panel's code) is
checked by CppunitTest_sfx2_hst_backstagecoat in the build; here: the left column's spacing and its classes in
hstbackstage.ui, ids, accessible names and keyboard handling untouched, the GTK CSS from the tokens, and the
patch staying inside the phase's files."""
import re
import unittest

from patch_sections import added, removed, sections

PATCH = "hst-ui-coat-backstage.patch"
UI = "sfx2/uiconfig/ui/hstbackstage.ui"
WINDOW = "sfx2/source/backstage/hstbackstagewindow.cxx"
COAT = "sfx2/source/backstage/hstbackstagecoat.cxx"
COAT_HEADER = "sfx2/source/backstage/hstbackstagecoat.hxx"
LEGACY = "sfx2/source/backstage/hstbackstagelegacycolors.hxx"
CSS = "vcl/source/hst/coat/css/backstage.cxx"
COLOUR_LITERAL = re.compile(r"0x[0-9a-fA-F]{2}\s*,\s*0x[0-9a-fA-F]{2}\s*,\s*0x[0-9a-fA-F]{2}"
                            r"|\bCOL_(?!TRANSPARENT\b|AUTO\b)[A-Z_]+|#[0-9a-fA-F]{6}\b")
OWNED = re.compile(r"^(sfx2/source/backstage/|sfx2/inc/backstage/|sfx2/uiconfig/ui/hstbackstage\.ui$"
                   r"|sfx2/qa/cppunit/hstbackstagecoat\.cxx$|sfx2/CppunitTest_sfx2_hst_backstagecoat\.mk$"
                   r"|sfx2/Module_sfx2\.mk$|sfx2/Library_sfx\.mk$|vcl/source/hst/coat/css/backstage\.cxx$"
                   r"|include/vcl/hstprintjobpanel\.hxx$|vcl/source/gdi/print3\.cxx$)")


class LeftColumn(unittest.TestCase):
    def test_items_are_four_pixels_apart(self):
        ui = added(PATCH, UI)
        self.assertRegex(ui, r'<property name="spacing">4</property>')
        self.assertIn('<class name="hst-backstage-nav"/>', ui)
        # the coat's item height and gap are the Start Center's (a 40 px pill every 44 px)
        header = added(PATCH, COAT_HEADER)
        self.assertIn("NAV_ITEM_HEIGHT = 40;", header)
        self.assertIn("NAV_ITEM_GAP = 4;", header)

    def test_ids_names_and_keys_unchanged(self):
        ui_removed = removed(PATCH, UI)
        self.assertNotIn('id="nav', ui_removed)
        self.assertNotIn("translatable", ui_removed)
        self.assertNotIn("can-focus", ui_removed)
        window_removed = removed(PATCH, WINDOW)
        for kept in ("set_accessible_name(aItem.aText)", "connect_clicked", "grab_focus", "KEY_UP", "KEY_DOWN",
                     "CloseAndDispatch(u\".uno:"):
            with self.subTest(kept=kept):
                self.assertNotIn(kept, window_removed)

    def test_pill_focus_ring_and_side_panel_from_the_helpers(self):
        coat = added(PATCH, COAT)
        self.assertIn("design::DrawPill(", coat)
        self.assertIn("design::DrawFocusRing(", coat)
        self.assertIn("p.aSide", coat)
        self.assertIn("type::NavSelected", coat)


class Colours(unittest.TestCase):
    def test_no_colour_literal_outside_the_earlier_look(self):
        for path in sections(PATCH):
            if path == LEGACY or not path.startswith(("sfx2/source/backstage/", "sfx2/inc/backstage/", CSS)):
                continue
            with self.subTest(path=path):
                self.assertIsNone(COLOUR_LITERAL.search(added(PATCH, path)))
        self.assertRegex(added(PATCH, LEGACY), r"WRITER_COLOR\(0x1a, 0x85, 0xd1\)")

    def test_gtk_css_from_the_tokens(self):
        css = added(PATCH, CSS)
        self.assertIn("rPalette.aCardBorder", css)
        self.assertIn("d::radius::Card", css)
        self.assertIn(".hst-backstage-nav button", css)
        self.assertIn(".hst-backstage-card", css)
        # colours, corners and focus marks only, as CppunitTest_vcl_hst_coat requires of the whole CSS
        strings = "".join(re.findall(r'u"([^"]*)"', css))
        self.assertIn(".hst-backstage-card", strings)
        self.assertIsNone(re.search(r"padding|margin|min-width|min-height|border-width|font", strings))

    def test_cards_are_the_three_blocks(self):
        ui = added(PATCH, UI)
        self.assertEqual(ui.count('<class name="hst-backstage-card"/>'), 3)
        window = added(PATCH, WINDOW)
        self.assertIn('{ u"tiles"_ustr, u"infogrid"_ustr, u"pageexportgrid"_ustr }', window)


class Scope(unittest.TestCase):
    def test_patch_stays_in_the_phase_files(self):
        for path in sections(PATCH):
            with self.subTest(path=path):
                self.assertRegex(path, OWNED)
        for path in sections(PATCH):
            self.assertFalse(path.startswith(("translations/", "solenv/sanitizers/")), path)
            self.assertNotIn("printdialog.ui", path)
            self.assertNotIn("startcenter", path)

    def test_red_green_unit_test_registered(self):
        self.assertIn("CppunitTest_sfx2_hst_backstagecoat", added(PATCH, "sfx2/Module_sfx2.mk"))
        self.assertIn("sfx2/source/backstage/hstbackstagecoat", added(PATCH, "sfx2/Library_sfx.mk"))


if __name__ == "__main__":
    unittest.main()
