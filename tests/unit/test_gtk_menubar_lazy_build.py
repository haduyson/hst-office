# SPDX-License-Identifier: AGPL-3.0-only
"""Linux (GTK) builds the native menu bar only when it is shown (hst-gtk-menubar-lazy-build.patch).

Opening a spreadsheet built the whole GTK menu bar (every submenu activated, a widget per item) although the Tabbed
UI hides it at once, and closing a document built it again for a window about to show the Start Center. The patch
defers that build to an idle that only builds a menu bar still displayable.
"""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-gtk-menubar-lazy-build.patch")
CXX = "vcl/unx/gtk3/gtksalmenu.cxx"


def after(path):
    """The hunks of one file as they read after the patch (context and added lines)."""
    lines, current = [], False
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            if line.startswith("+++ b/"):
                current = line[6:].split()[0] == path
            elif current and not line.startswith("--- ") and line[:1] in (" ", "+"):
                lines.append(line[1:])
    return "\n".join(lines)


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}\n", start)]


class GtkMenubarLazyBuildTest(unittest.TestCase):
    def test_in_the_series_after_the_older_gtk_menubar_fix(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = handle.read().split()
        self.assertGreater(series.index("hst-gtk-menubar-lazy-build.patch"), series.index("hst-gtk-menubar-fix.patch"))

    def test_set_frame_defers_the_build_outside_unity_mode(self):
        body = function(after(CXX), "void GtkSalMenu::SetFrame(")
        unity, rest = body.split("return;", 1)
        self.assertIn("UpdateFull();", unity)  # the global menu is the model itself: built at once
        self.assertNotIn("UpdateFull", rest)
        self.assertNotIn("CreateMenuBarWidget", rest)
        self.assertIn("mbMenuBarBuildPending = true;", rest)
        self.assertIn("maBuildMenuBarIdle.Start();", rest)

    def test_the_idle_builds_only_a_displayable_menubar(self):
        body = function(after(CXX), "void GtkSalMenu::BuildPendingMenuBar()")
        self.assertLess(body.index("IsDisplayable()"), body.index("UpdateFull();"))
        # UpdateFull() can spin a nested main loop: visibility and frame are checked again before the widget
        self.assertRegex(body, re.compile(r"UpdateFull\(\);.*if \(mpFrame && !bUnityMode && pMenuBar->IsDisplayable\(\)\)"
                                          r".*CreateMenuBarWidget\(\);", re.S))

    def test_hiding_detaching_and_unity_cancel_a_pending_build(self):
        text = after(CXX)
        self.assertIn("maBuildMenuBarIdle.Stop();\n        DestroyMenuBarWidget();", function(text, "void GtkSalMenu::ShowMenuBar("))
        self.assertIn("maBuildMenuBarIdle.Stop();", function(text, "void GtkSalMenu::DetachFromFrame()"))
        self.assertIn("mbMenuBarBuildPending = false;", function(text, "void GtkSalMenu::EnableUnity("))

    def test_f10_and_menu_customisation_still_build_at_once(self):
        text = after(CXX)
        self.assertIn("BuildPendingMenuBar();", function(text, "bool GtkSalMenu::TakeFocus()"))
        self.assertIn("BuildPendingMenuBar();", function(text, "IMPL_LINK_NOARG(GtkSalMenu, MenuBarHierarchyChangeHandler"))


if __name__ == "__main__":
    unittest.main()
