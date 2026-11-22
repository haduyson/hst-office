# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-gtk3-boxes-fit-rows.patch: on gtk3 the native boxes of a ribbon item fit the ribbon's 24 px rows.

GTK draws a combo box, entry or spin button at its theme height (Adwaita 31-34 px), so a 24 px ribbon row cut their
bottom. Only the native widgets of an item window inside the NotebookBar get the style class, and only that class
drops the boxes' vertical padding and minimum height; toolbars, the sidebar and dialogs keep the theme."""
import re
import unittest

from patch_sections import added

PATCH = "hst-ribbon-gtk3-boxes-fit-rows.patch"


class Gtk3BoxesFitRowsTest(unittest.TestCase):
    def test_only_a_window_under_the_notebookbar_is_in_the_ribbon(self):
        code = added(PATCH, "vcl/source/control/HstRibbonRow.cxx")
        self.assertIn("for (; pWindow; pWindow = pWindow->GetParent())", code)
        self.assertIn("dynamic_cast<const NotebookBar*>(pWindow)", code)
        self.assertIn('RowStyleClass[] = "hst-ribbon-row"', added(PATCH, "include/vcl/HstRibbonRow.hxx"))

    def test_the_interim_builder_marks_ribbon_items_only(self):
        code = added(PATCH, "vcl/unx/gtk3/gtkinst.cxx")
        self.assertIn("if (hst::ribbon::IsInRibbon(pParent))", code)
        self.assertIn("gtk_style_context_add_class(gtk_widget_get_style_context(pWindow), hst::ribbon::RowStyleClass);",
                      code)

    def test_the_css_drops_vertical_padding_and_min_height_under_the_class_only(self):
        css = "".join(re.findall(r'"([^"]*)"', added(PATCH, "vcl/unx/gtk3/gtkdata.cxx")))
        selectors, _, body = css.partition("{")
        for selector in selectors.split(","):
            self.assertTrue(selector.strip().startswith(".hst-ribbon-row "), selector)
        for widget in ("combobox *.combo", "box#combobox *.combo", "button", "entry", "spinbutton",
                       "spinbutton entry"):
            self.assertIn(f".hst-ribbon-row {widget}", selectors)
        self.assertIn("padding-top: 0; padding-bottom: 0; min-height: 0;", body)
        self.assertNotIn("border", body)  # the frames stay

    def test_the_new_file_is_built(self):
        self.assertIn("vcl/source/control/HstRibbonRow \\", added(PATCH, "vcl/Library_vcl.mk"))


if __name__ == "__main__":
    unittest.main()
