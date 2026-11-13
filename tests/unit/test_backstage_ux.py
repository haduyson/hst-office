# SPDX-License-Identifier: AGPL-3.0-only
"""File panel "In" and "Xuất" pages (hst-backstage-ux.patch), read from the patch."""
import re
import unittest

from patch_sections import added, after, po_entries, removed

PATCH = "hst-backstage-ux.patch"
UI = "sfx2/uiconfig/ui/hstbackstage.ui"
WINDOW = "sfx2/source/backstage/hstbackstagewindow.cxx"
PO = "translations/source/vi/sfx2/messages.po"
COMMANDS = {
    "m_xPrintPrint": ".uno:Print",
    "m_xPrintPreview": ".uno:PrintPreview",
    "m_xPrintDuplex": "org.hst.office.vi:ToggleDuplex",
    "m_xExportPdf": ".uno:ExportToPDF",
    "m_xExportPdfDirect": ".uno:ExportDirectToPDF",
    "m_xExportOther": ".uno:ExportTo",
    "m_xExportMinimize": ".uno:PresentationMinimizer",
}


class Pages(unittest.TestCase):
    def test_print_and_export_open_pages(self):
        window = after(PATCH, WINDOW)
        self.assertIn('else if (aId == "navprint")\n        ShowPage(Page::Print);', window)
        self.assertIn("ShowPage(Page::Export);", window)
        self.assertIn('CloseAndDispatch(u".uno:Print"_ustr);', removed(PATCH, WINDOW))

    def test_buttons_run_their_commands(self):
        window = added(PATCH, WINDOW)
        for member, command in COMMANDS.items():
            with self.subTest(member=member):
                self.assertRegex(window, r"&rButton == %s\.get\(\)\)[^\n]*\n\s+CloseAndDispatch\(u\"%s\"_ustr\);"
                                 % (re.escape(member), re.escape(command)))

    def test_app_specific_buttons(self):
        window = added(PATCH, WINDOW)
        self.assertIn("m_xPrintDuplex->set_visible(m_eApp == BackstageApp::Writer);", window)
        self.assertIn("m_xExportMinimize->set_visible(m_eApp == BackstageApp::Impress);", window)

    def test_vietnamese(self):
        ui = added(PATCH, UI)
        entries = po_entries(after(PATCH, PO))
        for context in set(re.findall(r'context="(hstbackstage\|[^"]+)"', ui)):
            with self.subTest(context=context):
                self.assertTrue(entries[context][1])
                self.assertFalse(entries[context][1].endswith(("…", "...")))
        self.assertEqual(entries["hstbackstage|navpdf"], ("Export", "Xuất"))
        self.assertEqual(entries["hstbackstage|printpreview"][1], "Xem trước khi in")
        self.assertIn('<property name="label">In hai mặt</property>', ui)  # extension command: Vietnamese always
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint", ui + added(PATCH, PO)))


if __name__ == "__main__":
    unittest.main()
