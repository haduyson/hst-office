# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF windows and .pdf files carry HST PDF's own taskbar identity (hst-pdf-app-user-model-id.patch)."""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-pdf-app-user-model-id.patch")


def added(path):
    lines, current = [], None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = match.group(1)
            elif current == path and line.startswith("+"):
                lines.append(line[1:])
    return "\n".join(lines)


class PdfAppUserModelIdTest(unittest.TestCase):
    def test_series_has_the_patch_after_the_window_groups(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertIn("hst-pdf-app-user-model-id.patch", series)
        self.assertGreater(series.index("hst-pdf-app-user-model-id.patch"),
                           series.index("hst-module-window-groups.patch"))

    def test_viewer_windows_get_the_pdf_application(self):
        source = added("framework/source/helper/titlebarupdate.cxx")
        self.assertIn('supportsService( u"org.hasontech.hstoffice.PdfViewer"_ustr )', source)
        self.assertIn('sDesktopName = "Pdf";', source)
        self.assertIn("!bOfficeWindow && xViewer.is()", source)  # a PDF tab of HST Office stays HST Office's

    def test_pdf_progid_carries_the_same_id_open_with_stays_draw(self):
        macro = added("scp2/inc/macros.inc")
        self.assertIn("#define CONDITIONAL_REGISTER_DOC_EXTENSION_APPID(", macro)
        self.assertIn("REGISTRY_ENTRY_APPUSERMODELID(name,modid,app_id)", macro)
        self.assertIn("REGISTRY_ENTRY_CAPABILITIES(name,modid,key,doc_type)", macro)
        self.assertIn("CONDITIONAL_REGISTER_DOC_EXTENSION_APPID( Pdf,  gid_Module_Prg_Draw_Other_Reg, pdf, PDF, PDF, 5, "
                      "sdraw.exe, open, Draw, Pdf )", added("scp2/source/draw/registryitem_draw.scp"))

    def test_linux_launcher_matches_the_window_class(self):
        self.assertIn("StartupWMClass=vn.hasontech.hstoffice-pdf", added("sysui/desktop/menus/pdf.desktop"))


if __name__ == "__main__":
    unittest.main()
