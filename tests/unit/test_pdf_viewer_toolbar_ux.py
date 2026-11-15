# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF toolbar (hst-pdf-viewer-toolbar-ux.patch): Sign never clipped, new view buttons, ≡ menu, rotation."""
import re
import unittest

from patch_sections import added, po_entries, sections

PATCH = "hst-pdf-viewer-toolbar-ux.patch"
UI = "xmlsecurity/uiconfig/ui/hstpdfviewer.ui"
WINDOW = "xmlsecurity/source/hstpdf/pdfviewerwindow.cxx"
VIEW = "xmlsecurity/source/hstpdf/pdfpageview.cxx"
PO = "translations/source/vi/xmlsecurity/messages.po"
NEW_BUTTONS = ("savecopy", "fitwidth", "rotate", "prevpage", "nextpage")


def toolbar_order():
    """Toolbar child ids in packing order, read from the .ui lines after the patch (hunk by hunk)."""
    positions, current = {}, None
    for line in sections(PATCH)[UI]:
        if line.startswith("@@") or line[1:] == "        <child>":
            current = None
        elif line[:1] in (" ", "+"):
            match = re.match(r' {10}<object class="Gtk\w+" id="(\w+)">', line[1:])
            if match:
                current = match.group(1)
            match = re.match(r' {12}<property name="position">(\d+)<', line[1:])
            if match and current:
                positions[current] = int(match.group(1))
    return sorted(positions, key=positions.get)


class Toolbar(unittest.TestCase):
    def test_new_buttons_and_the_menu_at_the_right_end(self):
        order = toolbar_order()
        self.assertEqual(order, ["savecopy", "fitwidth", "rotate", "prevpage", "nextpage", "sep4", "menu"])
        lines = sections(PATCH)[UI]
        after = [int(n) for n in re.findall(r'^[ +] {12}<property name="position">(\d+)<', "\n".join(lines), re.M)]
        added_positions = [int(n) for n in re.findall(r'^\+ {12}<property name="position">(\d+)<', "\n".join(lines), re.M)]
        self.assertEqual(max(after), 24)
        self.assertEqual(sorted(set(added_positions)), list(range(2, 25)))  # one toolbar, renumbered 0-24
        self.assertEqual(len(added_positions), len(set(added_positions)))

    def test_menu_offers_help_report_about(self):
        ui = added(PATCH, UI)
        self.assertIn('<property name="popup">hstmenu</property>', ui)
        self.assertEqual(re.findall(r'<object class="GtkMenuItem" id="(\w+)"', ui), ["help", "reporterror", "about"])
        window = added(PATCH, WINDOW)
        for command in (".uno:HelpIndex", "org.hst.office.vi:ReportError", ".uno:About"):
            self.assertIn('u"%s"_ustr' % command, window)

    def test_narrow_window_shrinks_search_first_never_sign_or_edit(self):
        window = added(PATCH, WINDOW)
        widths = [int(n) for n in re.search(r"SEARCH_WIDTH_CHARS\[\] = \{([^}]*)\}", window).group(1).split(",")]
        self.assertEqual(widths[0], 24)
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertGreater(widths[0], widths[1])  # the first step only shrinks the search box
        compact = re.search(r"for \(weld::Button\* pButton : \{ m_xOpen\.get\(\), (.*?)\}\)", window, re.S).group(0)
        self.assertNotIn("m_xSign", compact)
        self.assertNotIn("m_xEdit", compact)
        self.assertIn("fitToolbar();\n    InterimItemWindow::Resize();", window)

    def test_shortcuts_in_tooltips_are_handled(self):
        window = added(PATCH, WINDOW)
        for key in ("KEY_2", "KEY_R", "KEY_S", "KEY_PAGEUP", "KEY_PAGEDOWN"):
            self.assertIn("case %s:" % key, window)
        entries = po_entries(added(PATCH, PO))
        tips = {ctx.split("|")[1]: vi for ctx, (_en, vi) in entries.items() if ctx.endswith("tooltip_text")}
        self.assertTrue(tips["savecopy"].endswith("(Ctrl+Shift+S)"))
        self.assertTrue(tips["fitwidth"].endswith("(Ctrl+2)"))
        self.assertTrue(tips["rotate"].endswith("(Ctrl+R)"))
        self.assertTrue(tips["prevpage"].startswith("Trang trước"))
        self.assertTrue(tips["nextpage"].startswith("Trang sau"))


class Strings(unittest.TestCase):
    def test_every_new_ui_string_has_vietnamese(self):
        ui = added(PATCH, UI)
        contexts = set(re.findall(r'context="(hstpdfviewer\|[^"]+)"', ui))
        entries = po_entries(added(PATCH, PO))
        for context in contexts - {"hstpdfviewer|fitpage", "hstpdfviewer|fitpage|tooltip_text"}:
            with self.subTest(context=context):
                self.assertIn(context, entries)
                self.assertTrue(entries[context][1])
        for name in ("STR_HSTPDF_SAVE_COPY_TITLE", "STR_HSTPDF_COPY_SAME_FILE", "STR_HSTPDF_COPY_FAILED",
                     "STR_HSTPDF_COPY_SAVED"):
            self.assertIn(name, entries)
        self.assertEqual(entries["hstpdfviewer|fitwidth"][1], "Vừa bề rộng")
        self.assertEqual(entries["hstpdfviewer|reporterror"][1], "Báo lỗi cho HASON TECH")
        po = "\n".join(sections(PATCH)[PO])
        self.assertIn(' msgctxt "hstpdfviewer|zoomwidth"\n msgid "Fit Width"\n-msgstr "Vừa chiều rộng"\n+msgstr "Vừa bề rộng"', po)

    def test_no_microsoft_product_names(self):
        text = "".join(added(PATCH, path) for path in sections(PATCH))
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint|Acrobat", text))


class Rotation(unittest.TestCase):
    def test_view_and_page_points_round_trip(self):
        # the patch's mapping, rewritten in Python: page point -> shown point -> page point
        view = added(PATCH, VIEW)
        self.assertIn("case 1: return basegfx::B2DPoint(aSize.getHeight() - fY, fX);", view)
        self.assertIn("case 1: return basegfx::B2DPoint(fY, aSize.getHeight() - fX);", view)
        w, h = 595.0, 842.0
        to_view = {0: lambda x, y: (x, y), 1: lambda x, y: (h - y, x), 2: lambda x, y: (w - x, h - y),
                   3: lambda x, y: (y, w - x)}
        from_view = {0: lambda x, y: (x, y), 1: lambda x, y: (y, h - x), 2: lambda x, y: (w - x, h - y),
                     3: lambda x, y: (w - y, x)}
        for turns in range(4):
            for point in ((0.0, 0.0), (10.0, 20.0), (w, h)):
                self.assertEqual(from_view[turns](*to_view[turns](*point)), point)
        self.assertEqual(to_view[1](0.0, 0.0), (h, 0.0))  # clockwise: the top left corner goes to the top right

    def test_signature_points_stay_upright(self):
        view = added(PATCH, VIEW)
        self.assertIn("return fromViewPoint(nPage", view)
        self.assertIn("aBitmap.Rotate(Degree10((4 - m_nRotation) * 900), COL_WHITE);", view)
        self.assertNotIn("m_oPlacement", view)


if __name__ == "__main__":
    unittest.main()
