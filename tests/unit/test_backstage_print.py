# SPDX-License-Identifier: AGPL-3.0-only
"""Print page of the File panel (hst-backstage-print.patch): the print dialog's panel form, the hand-over of a
print job from vcl to the File panel, and the Print page that hosts it. Read from the patch."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT
from patch_sections import added, after, po_entries

PATCH = "hst-backstage-print.patch"
PANEL_UI = "vcl/uiconfig/ui/hstprintpanel.ui"
DIALOG = "vcl/source/window/printdlg.cxx"
PRINT3 = "vcl/source/gdi/print3.cxx"
JOBPANEL = "vcl/source/window/hstprintjobpanel.cxx"
PAGE = "sfx2/source/backstage/hstbackstageprint.cxx"
HOST = "sfx2/source/backstage/hstbackstage.cxx"
WINDOW = "sfx2/source/backstage/hstbackstagewindow.cxx"
BACKSTAGE_UI = "sfx2/uiconfig/ui/hstbackstage.ui"
VCL_PO = "translations/source/vi/vcl/messages.po"
SFX_PO = "translations/source/vi/sfx2/messages.po"

# ids vcl::PrintDialog welds unconditionally (printdlg.cxx constructor, CustomWeld areas): a missing one crashes
DIALOG_IDS = """tabcontrol scrolledwindow layoutframe printersbox status setup copycount collate collateimage pagerange
rbRangePages sidesbox singlejobs reverseorder ok cancel backward forward btnFirst btnLast previewbox totalnumpages
preview pageedit pagespersheetbtn brochure pagespersheettxt pagespersheetbox pagestxt pagecols by pagerows
pagemargintxt1 pagemarginsb pagemargintxt2 sheetmargintxt1 sheetmarginsb sheetmargintxt2 papersizebox
pageorientationbox labelorder orderbox orderpreview bordercb exRangeExpander exLayoutExpander customcontents
custom""".split()
# ids the applications' print options look for in the dialog's own .ui (setupOptionalUI), incl. Calc's scaling list
OPTION_IDS = "rbAllPages rbRangeSelection evenoddbox includeevenodd printextrabox fromwhich scalingbox scalingboxlabel " \
             "scriptdirection".split()
PANEL_IDS = "HstPrintPanel moreoptions pagesetup previewscroll zoomscale zoomin zoomout zoomfit zoomtext".split()


def panel_ui():
    return ET.fromstring(added(PATCH, PANEL_UI).encode("utf-8"))


class PanelForm(unittest.TestCase):
    def test_series_order(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertIn(PATCH, series)
        # after the backstage placement of the ribbon work, whose GetPlacement sizes the Print page
        self.assertLess(series.index("hst-ribbon-adaptive-backstage.patch"), series.index(PATCH))

    def test_panel_has_every_dialog_id(self):
        ids = {obj.get("id") for obj in panel_ui().iter("object")}
        for oid in DIALOG_IDS + OPTION_IDS + PANEL_IDS:
            with self.subTest(id=oid):
                self.assertIn(oid, ids)
        self.assertNotIn("PrintDialog", ids)  # a container toplevel, not a dialog

    def test_panel_widgets_are_welded(self):
        code = added(PATCH, DIALOG)
        for oid in PANEL_IDS:
            with self.subTest(id=oid):
                self.assertIn('(u"%s"_ustr)' % oid, code)
        self.assertIn('Application::CreateBuilder(pParent, u"vcl/ui/hstprintpanel.ui"_ustr)', code)
        self.assertIn('Application::CreateBuilder(i_pWindow, u"vcl/ui/printdialog.ui"_ustr)', code)

    def test_layout_settings_left_preview_right(self):
        root = panel_ui()
        panel = next(o for o in root.iter("object") if o.get("id") == "HstPrintPanel")
        columns = [c.find("object").get("id") for c in panel.findall("child")]
        self.assertEqual(columns, ["leftcolumn", "rightcolumn"])
        left = next(o for o in root.iter("object") if o.get("id") == "leftcolumn")
        left_ids = {o.get("id") for o in left.iter("object")}
        self.assertTrue({"ok", "copycount", "printersbox", "tabcontrol", "pagesetup", "moreoptions"} <= left_ids)
        right = next(o for o in root.iter("object") if o.get("id") == "rightcolumn")
        right_ids = {o.get("id") for o in right.iter("object")}
        self.assertTrue({"preview", "btnFirst", "pageedit", "btnLast", "zoomscale", "zoomfit"} <= right_ids)
        hidden = next(o for o in root.iter("object") if o.get("id") == "hiddenbox")
        self.assertEqual({o.get("id") for o in hidden.iter("object")} >= {"cancel", "help", "previewbox"}, True)

    def test_zoom_controls_are_named(self):
        for obj in panel_ui().iter("object"):
            if obj.get("id") in ("zoomin", "zoomout", "zoomscale"):
                with self.subTest(id=obj.get("id")):
                    names = [p.text for p in obj.iter("property") if p.get("name") == "AtkObject::accessible-name"]
                    self.assertTrue(names and names[0])

    def test_panel_keeps_dialog_settings_apart(self):
        code = after(PATCH, DIALOG)
        # the panel neither stores the dialog's window state, preview box or expanders nor runs as a dialog
        self.assertIn("if (m_xDialog)\n        officecfg::VCL::VCLSettings::PrintDialog::WindowState::set(", code)
        self.assertIn("if (m_xDialog) // the panel always previews", code)
        self.assertIn("if (!m_xDialog) // the panel expands both sections", code)
        self.assertIn("maPanelPrintHdl.Call(*this);", code)


class HandOver(unittest.TestCase):
    def test_prepare_print_job_offers_the_job(self):
        code = after(PATCH, PRINT3)
        self.assertIn("if (o_pHandedOver && vcl::PrintJobPanel::HandOver(xController))", code)
        self.assertIn("if (!bHandedOver) // else the panel showing the job ends it\n        FinishPrintJob(xController);",
                      code)
        # the hand-over sits inside the dialog branch: not for printers with their own dialog (macOS), direct
        # printing or jobs without dialogs
        self.assertLess(code.index("xController->isShowDialogs()"), code.index("PrintJobPanel::HandOver"))

    def test_resume_is_the_dialog_ok_path(self):
        code = after(PATCH, PRINT3)
        resume = code[code.index("void Printer::ResumePrintJob"):code.index("void Printer::CancelPrintJob")]
        for step in ("lcl_applyDialogResult(", "pushPropertiesToPrinter();", "ExecutePrintJob(", "FinishPrintJob("):
            with self.subTest(step=step):
                self.assertIn(step, resume)
        cancel = code[code.index("void Printer::CancelPrintJob"):]
        self.assertIn("abortJob();", cancel)
        self.assertIn("FinishPrintJob(xController);", cancel)
        # the classic dialog and the panel apply print-to-file and single jobs the same way
        self.assertIn("lcl_applyDialogResult(xController, aDlg.isPrintToFile(), aDlg.isSingleJobs())", code)

    def test_job_panel_lifecycle(self):
        code = added(PATCH, JOBPANEL)
        self.assertRegex(code, r"PrintJobPanel::~PrintJobPanel\(\)\n\{[^}]*if \(m_bPending\)\n\s+Printer::CancelPrintJob")
        self.assertIn("xDialog->takeSettings(*m_xSettings);", code)
        self.assertIn("m_xSettings->takeSettings(*xDialog);", code)


class PrintPage(unittest.TestCase):
    def test_file_panel_is_the_host(self):
        host = added(PATCH, HOST)
        self.assertIn("vcl::PrintJobPanel::SetHost(lcl_takePrintJob);", host)
        self.assertIn("comphelper::LibreOfficeKit::isActive()", host)
        self.assertIn("pBackstage->ShowPrintJob(rxController)", host)

    def test_page_requests_and_cancels_jobs(self):
        page = added(PATCH, PAGE)
        self.assertIn('comphelper::dispatchCommand(u".uno:Print"_ustr, m_xFrame, {})', page)
        for command in (".uno:PageDialog", ".uno:PageFormatDialog", ".uno:PageSetup"):
            with self.subTest(command=command):
                self.assertIn('u"%s"_ustr' % command, page)
        window = added(PATCH, WINDOW)
        self.assertIn("m_xPrintPage->Deactivate(); // leaving the Print page cancels its print job", window)
        self.assertIn("m_xPrintPage->Deactivate(); // a print job waiting on the Print page is cancelled", window)
        self.assertIn('else if (aCommand == ".uno:Print") // Ctrl+P: the Print page', window)
        # the page is sized by GetPlacement of the ribbon work, not by its own code
        self.assertNotIn("PANEL_WIDTH", window)

    def test_old_buttons_hidden_duplex_kept(self):
        ui = after(PATCH, BACKSTAGE_UI)
        for oid in ("printprint", "printpreview"):
            with self.subTest(id=oid):
                self.assertRegex(ui, r'id="%s">\n(.*\n){1,2}\s*<property name="visible">False</property>' % oid)
        self.assertIn('id="printhost"', ui)
        self.assertNotIn('id="printduplex">\n                    <property name="visible">False', ui)


class Vietnamese(unittest.TestCase):
    def test_strings(self):
        for path, po, prefix in ((PANEL_UI, VCL_PO, "hstprintpanel"), (BACKSTAGE_UI, SFX_PO, "hstbackstage")):
            entries = po_entries(added(PATCH, po))
            contexts = set(re.findall(r'context="(%s\|[^"]+)"' % prefix, added(PATCH, path)))
            self.assertTrue(contexts)
            for context in contexts:
                with self.subTest(context=context):
                    self.assertTrue(entries[context][1])
                    self.assertFalse(entries[context][1].endswith(("…", "...")))
        entries = po_entries(added(PATCH, VCL_PO))
        self.assertEqual(entries["hstprintpanel|moreoptions"][1], "Thêm _tùy chọn")
        self.assertEqual(entries["hstprintpanel|pagesetup"][1], "Thiết _lập trang")


if __name__ == "__main__":
    unittest.main()
