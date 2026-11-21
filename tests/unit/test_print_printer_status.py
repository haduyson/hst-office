# SPDX-License-Identifier: AGPL-3.0-only
"""Printer state dots on the Print page of the File panel (hst-print-printer-status.patch). Read from the patch."""
import os
import re
import unittest

from _paths import ROOT
from patch_sections import added, po_entries, sections

PATCH = "hst-print-printer-status.patch"
HRC = "vcl/inc/hstprinterstatus.hrc"
VIEW = "vcl/source/window/hstprinterstatus.cxx"
QUERY = "vcl/source/gdi/hstprinterstatusquery.cxx"
HEADER = "include/vcl/hstprinterstatus.hxx"
DIALOG = "vcl/source/window/printdlg.cxx"
DIALOG_HXX = "vcl/inc/printdlg.hxx"
VCL_PO = "translations/source/vi/vcl/messages.po"

VI = {"Ready": "Sẵn sàng", "Busy": "Đang bận", "Paused": "Tạm dừng", "Offline": "Ngoại tuyến",
      "Error: out of paper": "Lỗi: hết giấy", "Status unknown": "Không rõ trạng thái"}


class PrinterStatus(unittest.TestCase):
    def test_series_order(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        # on top of the Print page with Cancel/Back: both change the panel's PrintDialog
        self.assertLess(series.index("hst-backstage-print-cancel-back.patch"), series.index(PATCH))

    def test_every_string_has_vietnamese(self):
        strings = re.findall(r'NC_\("(STR_HST_PRINTER_\w+)", "([^"]*)"\)', added(PATCH, HRC))
        self.assertGreaterEqual(len(strings), 11)
        po = po_entries(added(PATCH, VCL_PO))
        for ctx, english in strings:
            with self.subTest(ctx=ctx):
                self.assertEqual(po[ctx][0], english)
                self.assertTrue(po[ctx][1])
        texts = {msgid: msgstr for msgid, msgstr in po.values()}
        for english, vietnamese in VI.items():
            self.assertEqual(texts[english], vietnamese)

    def test_hst_owned_files(self):
        for path in (HRC, VIEW, QUERY, HEADER):
            self.assertIn("SPDX-License-Identifier: LicenseRef-HST-Proprietary", added(PATCH, path))

    def test_thin_hook_in_the_dialog(self):
        hook = [line for path in (DIALOG, DIALOG_HXX) for line in sections(PATCH)[path]
                if line.startswith("+") and line[1:].strip()]
        self.assertLessEqual(len(hook), 8)
        code = added(PATCH, DIALOG)
        self.assertIn("std::make_unique<vcl::hst::PrinterStatusView>(*mxPrinters, *mxStatusTxt, 1)", code)
        self.assertIn("mxPrinterStatus->SelectionChanged(mxStatusTxt->get_label());", code)

    def test_never_blocks_the_ui(self):
        view = added(PATCH, VIEW)
        self.assertIn("std::thread(", view)
        self.assertIn(".detach();", view)
        self.assertIn("connect_popup_toggled", added(PATCH, VIEW))  # fresh again when the list drops down
        self.assertNotIn("Printer::GetQueueInfo", view)  # the synchronous queue state of vcl

    def test_dots_are_easy_to_see(self):
        view = added(PATCH, VIEW)
        self.assertIn("std::lround(10 * Application::GetDefaultDevice()->GetDPIScaleFactor())", view)  # 10 px at 100 %
        self.assertIn("m_rPrinters.get_text_height()", view)  # grows with the list's font
        self.assertIn("aRing.DecreaseLuminance(", view)  # darker outline
        self.assertIn("(aSize.Height() - nDiameter) / 2", view)  # centred on the text line

    def test_gtk_printer_list_has_an_image_column(self):
        ui = added(PATCH, "vcl/uiconfig/ui/hstprintpanel.ui")
        self.assertIn('<object class="GtkComboBox" id="printersbox">', ui)
        self.assertIn('<property name="model">printerstore</property>', ui)
        self.assertIn('<column type="CairoSurface"/>', ui)  # vcl's gtk3 combo box puts VirtualDevice images there
        self.assertIn('<attribute name="surface">3</attribute>', ui)

    def test_platform_sources(self):
        query = added(PATCH, QUERY)
        self.assertIn("PRINTER_ATTRIBUTE_WORK_OFFLINE", query)
        self.assertIn("GetPrinterW(hPrinter, 2,", query)
        self.assertIn('cupsGetOption("printer-state"', query)
        self.assertIn('cupsGetOption("printer-state-reasons"', query)
        self.assertIn('aState == "5"', query)  # a stopped (cupsdisable) queue is red


if __name__ == "__main__":
    unittest.main()
