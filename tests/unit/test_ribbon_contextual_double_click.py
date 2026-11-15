# SPDX-License-Identifier: AGPL-3.0-only
"""A double-click on an object opens its contextual ribbon tab (hst-ribbon-contextual-double-click.patch) and
HST Draw's "Xoay trang" (hst-ribbon-ux-impress-draw-commands.patch, placed by hst-ribbon-ux-impress-draw.patch).
Reads the patches only."""
import os
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")


def read(name):
    with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
        return handle.read()


def section(text, path):
    start = text.index(f"+++ b/{path}\n")
    end = text.find("\n--- a/", start)
    return text[start:end if end >= 0 else len(text)]


class DoubleClickOpensContextualTab(unittest.TestCase):
    patch = read("hst-ribbon-contextual-double-click.patch")

    def test_sd_and_sc_call_the_engine_before_editing(self):
        for path, window in (("sd/source/ui/func/fudraw.cxx", "*mpWindow"),
                             ("sc/source/ui/drawfunc/fusel.cxx", "*pWindow")):
            hunk = section(self.patch, path)
            self.assertIn("+#include <vcl/HstRibbonContext.hxx>", hunk)
            self.assertIn(f"+                hst::ribbon::OpenContextualTab({window});"
                          if path.startswith("sd") else f"+                        hst::ribbon::OpenContextualTab({window});",
                          hunk)
        # sd: before the OLE activation, text edit and dialogs of the same double-click
        sd = section(self.patch, "sd/source/ui/func/fudraw.cxx")
        self.assertLess(sd.index("OpenContextualTab"), sd.index("GetObjInventor"))


class RotatePage(unittest.TestCase):
    commands = read("hst-ribbon-ux-impress-draw-commands.patch")
    ribbon = read("hst-ribbon-ux-impress-draw.patch")

    def test_command_is_wired_and_undoable(self):
        for name, sid in (("HstRotatePageLeft", "SID_HST_ROTATE_PAGE_LEFT"),
                          ("HstRotatePageRight", "SID_HST_ROTATE_PAGE_RIGHT")):
            self.assertIn(f"+SfxVoidItem {name} {sid}", section(self.commands, "sd/sdi/sdraw.sdi"))
            self.assertIn(f"+    {sid}\n", section(self.commands, "sd/sdi/drviewsh.sdi"))
            self.assertIn(f'"action-name">.uno:{name}<', self.ribbon)
        code = section(self.commands, "sd/source/ui/func/HstRotatePage.cxx")
        for needed in ("CreateUndoGeoObject", "SdPageFormatUndoAction", "EnterListAction", "DocumentType::Draw"):
            self.assertIn(needed, code)
        self.assertIn('+msgstr "Xoay trang phải 90°"', self.commands)
        self.assertIn('context="TabbedImpress|hstUXlabelPageRotate">Rotate<', self.ribbon)


if __name__ == "__main__":
    unittest.main()
