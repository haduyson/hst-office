# SPDX-License-Identifier: AGPL-3.0-only
"""Own title bar of the Tabbed document windows on Windows (hst-custom-titlebar.patch).

The geometry header has no LibreOffice dependencies: it is taken from the patch and compiled with a
small driver (skipped without a C++ compiler). The other tests check the contracts that a build on
Linux cannot exercise: the Windows message handling, the opt-out setting and its Options entry.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCH_DIR = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCH_DIR, "hst-custom-titlebar.patch")

DRIVER = r"""
#include "HstTitleBarGeometry.hxx"
#include <cstdio>
using namespace hst::titlebar;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %d %s\n", __LINE__, #c); ++failures; } } while (0)
int main()
{
    // the merged row is 48 logical px: band = 48 - tab row, never below 4 px
    CHECK(bandHeight(35, 1.0) == 13);
    CHECK(bandHeight(35 * 1.5, 1.5) == 72 - 52);
    CHECK(bandHeight(70, 2.0) == 26);
    CHECK(bandHeight(60, 1.0) == 4);
    CHECK(buttonsWidth(1.0) == 138 && buttonsWidth(1.25) == 3 * 58 && buttonsWidth(2.0) == 276);
    // caption area 300 px wide at 100 %: title, then minimize, maximize, close from left to right
    CHECK(captionAreaHit(0, 300, 1.0) == Caption);
    CHECK(captionAreaHit(161, 300, 1.0) == Caption);
    CHECK(captionAreaHit(162, 300, 1.0) == MinButton);
    CHECK(captionAreaHit(208, 300, 1.0) == MaxButton);
    CHECK(captionAreaHit(254, 300, 1.0) == CloseButton);
    CHECK(captionAreaHit(299, 300, 1.0) == CloseButton);
    CHECK(captionAreaHit(300, 300, 1.0) == Client);
    CHECK(captionAreaHit(-1, 300, 1.0) == Client);
    CHECK(captionAreaHit(2 * 300 - 92 * 2, 600, 2.0) == MaxButton);
    // the title yields first: the search box keeps 320 px, short titles show whole, long ones are elided
    CHECK(titleWidth(1000, 200, 1.0) == 224);
    CHECK(titleWidth(1000, 2000, 1.0) == 420);
    CHECK(titleWidth(320 + 150, 2000, 1.0) == 150);
    CHECK(titleWidth(320 + 95, 2000, 1.0) == 0);
    CHECK(titleWidth(320 + 60, 30, 1.0) == 54);
    CHECK(titleWidth(300, 200, 1.0) == 0);
    CHECK(titleWidth(1000, 0, 1.0) == 0);
    CHECK(titleWidth(2000, 400, 2.0) == 448);
    // resize edge at the top of a restored window
    CHECK(onTopEdge(0, 4) && onTopEdge(3, 4) && !onTopEdge(4, 4) && !onTopEdge(-1, 4));
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def patch_text():
    with open(PATCH, encoding="utf-8") as handle:
        return handle.read()


def added_file(path):
    """Contents of a file the patch adds."""
    match = re.search(r"^\+\+\+ b/" + re.escape(path) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", patch_text(), re.M)
    if not match:
        raise AssertionError(f"{path} not added by the patch")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


def added_lines(path):
    """Lines the patch adds to an existing file."""
    sections = re.split(r"^--- (?:a/|/dev/null)", patch_text(), flags=re.M)
    for section in sections:
        if section.startswith(path) or f"+++ b/{path}\n" in section[:400]:
            return "\n".join(line[1:] for line in section.splitlines() if line.startswith("+") and not line.startswith("+++"))
    raise AssertionError(f"{path} not changed by the patch")


class CustomTitleBarTest(unittest.TestCase):
    def test_in_series_once_and_last_of_its_files(self):
        with open(os.path.join(PATCH_DIR, "series"), encoding="utf-8") as handle:
            names = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertEqual(names.count("hst-custom-titlebar.patch"), 1)

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstTitleBarGeometry.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added_file("vcl/inc/HstTitleBarGeometry.hxx"))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Werror", "-o", exe, os.path.join(tmp, "driver.cxx")],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_windows_messages_stay_native(self):
        win = added_file("vcl/win/window/HstWinTitleBar.cxx")
        for code in ("HTCAPTION", "HTMINBUTTON", "HTMAXBUTTON", "HTCLOSE", "HTTOP", "HTTOPLEFT", "HTTOPRIGHT"):
            self.assertIn(code, win)
        for message in ("WM_NCCALCSIZE", "WM_NCHITTEST", "WM_NCLBUTTONDOWN", "WM_NCLBUTTONUP", "WM_NCMOUSELEAVE",
                        "WM_GETTITLEBARINFOEX"):
            self.assertIn(f"case {message}:", win)
        self.assertIn("SC_MAXIMIZE", win)
        self.assertIn("ABM_GETAUTOHIDEBAREX", win)  # maximized: room for an auto-hide taskbar
        self.assertIn("DwmExtendFrameIntoClientArea", win)
        frame = added_lines("vcl/win/window/salframe.cxx")
        self.assertIn("ImplHstTitleBarProc( hWnd, nMsg, wParam, lParam, nRet )", frame)
        self.assertEqual(frame.count("ImplHstAdjustWindowRect( "), 2)  # SetPosSize and the min/max border
        self.assertIn("ImplHstWindowStateShift(this)", frame)

    def test_other_platforms_keep_the_system_title_bar(self):
        logic = added_file("vcl/source/window/HstTitleBar.cxx")
        supported = logic[logic.index("bool hst::titlebar::Supported()"):]
        self.assertRegex(supported, r"(?s)#ifdef _WIN32\s+return true;.*#else\s+return false;")
        for condition in ("HstSystemTitleBar::get()", "IsFullScreenMode()", "HstHasOwnBanner()", "mbMenuHide"):
            self.assertIn(condition, logic)

    def test_tab_row_keeps_room_for_the_caption_area(self):
        tabs = added_lines("vcl/source/control/tabctrl.cxx")
        self.assertIn("hst::titlebar::RowReserve(*this", tabs)
        self.assertIn("nWidth -= nHstCaption;", tabs)

    def test_opt_out_setting(self):
        schema = added_lines("officecfg/registry/schema/org/openoffice/Office/Common.xcs")
        self.assertIn('<prop oor:name="HstSystemTitleBar" oor:type="xs:boolean" oor:nillable="false">', schema)
        self.assertIn("<value>false</value>", schema)
        ui = added_lines("cui/uiconfig/ui/optviewpage.ui")
        self.assertIn('id="systemtitlebar"', ui)
        self.assertIn("Use the operating system's _title bar", ui)
        page = added_lines("cui/source/options/optgdlg.cxx")
        self.assertIn("hst::titlebar::SettingChanged();", page)
        self.assertIn("set_visible(hst::titlebar::Supported())", page)
        vi = added_lines("translations/source/vi/cui/messages.po")
        self.assertIn('msgstr "Dùng _thanh tiêu đề của hệ điều hành"', vi)
        self.assertIn('msgstr "Giao diện"', vi)

    def test_no_third_party_product_names(self):
        user_facing = added_lines("cui/uiconfig/ui/optviewpage.ui") + added_lines("translations/source/vi/cui/messages.po")
        for name in ("Microsoft", "Office 365", "Word", "Excel", "PowerPoint"):
            self.assertNotIn(name, user_facing)


if __name__ == "__main__":
    unittest.main()
