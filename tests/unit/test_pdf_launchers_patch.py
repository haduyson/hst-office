# SPDX-License-Identifier: AGPL-3.0-only
"""hst-pdf-launchers.patch: HST PDF started from its Linux launcher or Windows shortcuts asks for a PDF file
(org.hst.office.vi.PdfOpen, tests/unit/test_pdf_open.py) instead of showing the Start Center, with HST PDF's icon.

Offline: the lines the patch adds. scripts/windows/check-app-shortcuts.ps1 checks an installed MSI in windows-smoke."""
import json
import re
import unittest
from pathlib import Path

from test_msi_app_desktop_shortcuts import scp_items

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-pdf-launchers.patch"
SERVICE = "service:org.hst.office.vi.PdfOpen"


def added():
    """{path: text of the lines the patch adds}."""
    found, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            found.setdefault(current, [])
        elif current and line.startswith("+"):
            found[current].append(line[1:])
    return {path: "\n".join(lines) + "\n" for path, lines in found.items()}


class LinuxLauncher(unittest.TestCase):
    def test_launcher_asks_unless_files_come_with_it(self):
        exec_line = next(line for line in added()["sysui/desktop/menus/pdf.desktop"].splitlines()
                         if line.startswith("Exec="))
        self.assertEqual(exec_line, 'Exec=${UNIXBASISROOTNAME} --nodefault "%s?begin" %%%%FILE%%%% %s' % (SERVICE, SERVICE))

    def test_launcher_and_hicolor_icons_are_hst_pdf(self):
        self.assertIn("Icon=pdf", added()["sysui/desktop/menus/pdf.desktop"])
        self.assertIn(" pdf:pdf; do", added()["sysui/desktop/share/create_tree.sh"])


class WindowsShortcuts(unittest.TestCase):
    def setUp(self):
        self.scp = added()["scp2/source/draw/folderitem_draw.scp"]

    def test_start_menu_and_desktop_shortcuts(self):
        items = scp_items(self.scp, "FolderItem")
        self.assertEqual(set(items), {"gid_Folderitem_HstPdf", "gid_Folderitem_HstPdf_Desktop"})
        for gid, item in items.items():
            with self.subTest(gid):
                self.assertEqual(item["Name"], "HST PDF")
                self.assertEqual(item["FileID"], "auto_brand_exe_soffice_exe")
                self.assertEqual(item["Parameter"], "--nodefault " + SERVICE)
                self.assertEqual(item["IconFile"], "gid_Brand_File_Ico_Pdf")
                self.assertIn("NON_ADVERTISED", item["Styles"])
                self.assertIn("USE_HELPER_FILENAME", item["Styles"])
        self.assertEqual(items["gid_Folderitem_HstPdf"]["FolderID"], "gid_Folder_Staroffice51")
        self.assertEqual(items["gid_Folderitem_HstPdf"]["ComponentIDFile"], "gid_Brand_File_Ico_Pdf")
        desktop = items["gid_Folderitem_HstPdf_Desktop"]
        self.assertEqual((desktop["FolderID"], desktop["ComponentIDFile"], desktop["ComponentCondition"]),
                         ("PREDEFINED_DESKTOP", "gid_Brand_File_Desktophelper_Pdf_Txt", "CREATEDESKTOPLINK=1"))

    def test_taskbar_grouping_matches_the_viewer_windows(self):
        props = scp_items(self.scp, "FolderItemProperty")
        self.assertEqual({p["ShortcutID"]: p["Value"] for p in props.values()},
                         {"gid_Folderitem_HstPdf": "HASONTECH.HSTOffice.Pdf",
                          "gid_Folderitem_HstPdf_Desktop": "HASONTECH.HSTOffice.Pdf"})

    def test_icon_and_helper_ship_with_hst_draw(self):
        files = scp_items(self.scp, "File")
        self.assertEqual(files["gid_Brand_File_Ico_Pdf"]["Name"], "pdf_app.ico")
        self.assertEqual(files["gid_Brand_File_Desktophelper_Pdf_Txt"]["Name"], "desktophelper_pdf.txt")
        module = added()["scp2/source/draw/module_draw.scp"]
        self.assertIn("gid_Brand_File_Ico_Pdf, gid_Brand_File_Desktophelper_Pdf_Txt", module)
        package = added()["setup_native/Package_misc.mk"]
        self.assertIn("$(LIBO_BIN_FOLDER)/pdf_app.ico,../../sysui/desktop/icons/pdf_app.ico", package)
        self.assertIn("$(LIBO_BIN_FOLDER)/desktophelper_pdf.txt,win32/desktophelper.txt", package)
        self.assertTrue((ROOT / "branding/windows/app-icons/pdf_app.ico").is_file())

    def test_non_advertised_shortcuts_keep_an_ico_of_their_own(self):
        hook = added()["solenv/bin/modules/installer/windows/shortcut.pm"]
        self.assertRegex(hook, r"\\\.ico\$/i")
        self.assertIn("! $ownico", hook)

    def test_tooltips_name_hst(self):
        self.assertIn('[STR_FI_TOOLTIP_PDF]\nen-US = "View PDF files and sign them digitally."',
                      added()["scp2/source/draw/folderitem_draw.ulf"])
        self.assertIn('msgstr "Xem tệp PDF và ký số."', added()["translations/source/vi/scp2/source/draw.po"])
        office = added()["scp2/source/ooo/folderitem_ooo.ulf"]
        self.assertNotRegex(office, re.compile("LibreOffice|Document Foundation"))
        rows = [json.loads(line) for line in (ROOT / "l10n/vi-overrides.jsonl").read_text(encoding="utf-8").splitlines()
                if "STR_FI_TOOLTIP_SOFFICE" in line]
        self.assertEqual(len(rows), 1)
        self.assertEqual('en-US = "%s"\n' % rows[0]["msgid_new"], office)
        self.assertIn("HASON TECH", rows[0]["msgstr"])


class WindowlessOffice(unittest.TestCase):
    def test_service_requests_count_until_dispatch_finished(self):
        """Without the HST extension the service is missing: the request must still end in the office's "no window,
        quit" rule (tests/runtime/check-pdf-launcher-linux.py runs it on a real office)."""
        hook = added()["desktop/source/app/dispatchwatcher.cxx"]
        self.assertIn("m_nRequestCount++;", hook)
        text = PATCH.read_text(encoding="utf-8")  # counted before the dispatch, which may finish at once
        self.assertIn("+                        m_nRequestCount++;\n"
                      "                         xDisp->dispatchWithNotification( aURL, aArgs2, this );", text)


class Series(unittest.TestCase):
    def test_after_the_patches_it_builds_on(self):
        series = [n for n in (ROOT / "patches/libreoffice/series").read_text().splitlines() if n and n[0] != "#"]
        for earlier in ("hst-pdf-viewer.patch", "hst-packaging-sysui.patch", "hst-msi-app-desktop-shortcuts.patch",
                        "hst-pdf-app-user-model-id.patch"):
            self.assertLess(series.index(earlier), series.index(PATCH.name))


if __name__ == "__main__":
    unittest.main()
