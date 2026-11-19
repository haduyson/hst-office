# SPDX-License-Identifier: AGPL-3.0-only
"""hst-backstage-panel-keeps-focus.patch: while the File panel is open, a focus its frame's view takes (Writer on the
window's activation) goes back to the panel's page after the activation; a click into the document still closes the
panel. The keys themselves are checked on Windows by tests/runtime/check-backstage-print-close.py."""
import unittest

from patch_sections import added

PATCH = "hst-backstage-panel-keeps-focus.patch"
CXX = "sfx2/source/backstage/hstbackstagewindow.cxx"
HXX = "sfx2/source/backstage/hstbackstagewindow.hxx"


class PanelKeepsFocusTest(unittest.TestCase):
    def test_a_focus_on_the_view_is_moved_back_later(self):
        code = added(PATCH, CXX)
        self.assertIn("if (rEvent.GetId() == VclEventId::WindowGetFocus)", code)
        self.assertIn("if (pFocus && pView && pView->IsWindowOrChild(pFocus) && !m_pPendingRefocus)", code)
        self.assertIn("m_pPendingRefocus = Application::PostUserEvent(LINK(this, BackstageWindow, RefocusHdl));", code)
        self.assertIn("FocusPage();", code)

    def test_the_posted_event_goes_with_the_panel(self):
        code = added(PATCH, CXX)
        self.assertEqual(code.count("Application::RemoveUserEvent(m_pPendingRefocus);"), 2)  # Close and destructor
        self.assertIn("ImplSVEvent* m_pPendingRefocus = nullptr;", added(PATCH, HXX))
        self.assertIn("DECL_LINK(RefocusHdl, void*, void);", added(PATCH, HXX))

    def test_the_click_into_the_document_still_closes_first(self):
        code = added(PATCH, CXX)
        self.assertIn("if (rEvent.GetId() != VclEventId::WindowMouseButtonDown)", code)


if __name__ == "__main__":
    unittest.main()
