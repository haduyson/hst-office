# SPDX-License-Identifier: AGPL-3.0-only
"""Feature search of the ribbon tab row (hst-ribbon-feature-search.patch), read from the patch itself.

The interface the search box includes, Alt+Q, the "Find … in the document" row and its translation, and the Home
button that leaves the ribbon while the "Trang đầu" menu keeps the item.
"""
import os
import re
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-feature-search.patch")
UIS = ("sw/uiconfig/swriter/ui/notebookbar.ui", "sc/uiconfig/scalc/ui/notebookbar.ui",
       "sd/uiconfig/simpress/ui/notebookbar.ui")


def sections():
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None:
                current.append(line)
    return result


def added(path):
    return "\n".join(line[1:] for line in sections()[path] if line.startswith("+"))


def removed(path):
    return "\n".join(line[1:] for line in sections()[path] if line.startswith("-"))


class FeatureSearchPatchTest(unittest.TestCase):
    def test_interface_of_the_search_box(self):
        header = added("sfx2/inc/notebookbar/HstFeatureSearch.hxx")
        self.assertIn("namespace sfx2::hst", header)
        self.assertRegex(header, r"SFX2_DLLPUBLIC void ShowFeatureSearch\(vcl::Window\* pAnchor, "
                                 r"const OUString& rInitialText\);")
        source = added("sfx2/source/commandpopup/CommandPopup.cxx")
        self.assertIn("void sfx2::hst::ShowFeatureSearch(vcl::Window* pAnchor, const OUString& rInitialText)", source)
        self.assertIn('u"hst-tab-search"', source)  # the child id the tab row gives the box

    def test_popup_opens_under_the_box_from_every_entry_point(self):
        view = added("sfx2/source/view/viewfrm.cxx")
        self.assertIn("TakeFeatureSearchRequest(GetWindow())", view)
        self.assertIn("weld::GetPopupParent(rAnchor, aRectangle)", view)

    def test_alt_q_and_shift_escape(self):
        xcu = "officecfg/registry/data/org/openoffice/Office/Accelerators.xcu"
        new = added(xcu)
        self.assertRegex(new, r'oor:name="Q_MOD2"[\s\S]*?install:module="unxwnt">\.uno:CommandPopup<')
        self.assertNotIn("ESCAPE_SHIFT", removed(xcu))

    def test_find_in_document_row_and_translation(self):
        self.assertIn('NC_("STR_HST_FIND_IN_DOCUMENT", "Find “%1” in the document")', added("include/sfx2/strings.hrc"))
        po = added("translations/source/vi/sfx2/messages.po")
        self.assertIn('msgctxt "STR_HST_FIND_IN_DOCUMENT"\nmsgid "Find “%1” in the document"\n'
                      'msgstr "Tìm “%1” trong tài liệu"', po)
        source = added("sfx2/source/commandpopup/CommandPopup.cxx")
        self.assertIn(".uno:ExecuteSearch", source)
        self.assertIn(".uno:SearchDialog", source)

    def test_home_button_leaves_the_menu_item_stays(self):
        for ui in UIS:
            with self.subTest(ui=ui):
                self.assertIn('id="Home-HstFeatureSearch"', removed(ui))
                self.assertNotIn("MenuHome-HstFeatureSearch", removed(ui))
                self.assertNotIn("<object", added(ui))  # the patch only removes from the .ui


if __name__ == "__main__":
    unittest.main()
