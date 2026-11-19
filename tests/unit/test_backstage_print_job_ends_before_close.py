# SPDX-License-Identifier: AGPL-3.0-only
"""hst-backstage-print-job-ends-before-close.patch: a job the Print page takes gets a close guard on its frame and its
document; asked to close, either closes the File panel first, which cancels the job. Never a veto. The behaviour is
checked on Windows by tests/runtime/check-backstage-print-close.py (session end, close() from a macro, Ctrl+W, X,
.uno:Quit, terminate)."""
import unittest

from patch_sections import added

PATCH = "hst-backstage-print-job-ends-before-close.patch"
FILE = "sfx2/source/backstage/hstbackstage.cxx"


class JobEndsBeforeCloseTest(unittest.TestCase):
    def test_the_guard_closes_the_panel_when_asked_to_close(self):
        code = added(PATCH, FILE)
        self.assertIn("class PrintPageCloseGuard final : public cppu::WeakImplHelper<util::XCloseListener>", code)
        self.assertIn("void SAL_CALL queryClosing(const lang::EventObject&, sal_Bool) override", code)
        self.assertIn("CloseBackstage(xFrame);", code)
        self.assertNotIn("CloseVetoException", code)  # it never keeps the document open

    def test_the_frame_and_the_document_of_a_taken_job_are_guarded(self):
        code = added(PATCH, FILE)
        self.assertIn("xFrame->addCloseListener(xGuard);", code)
        self.assertIn("xModel->addCloseListener(xGuard);", code)
        self.assertIn("lcl_guardPrintPage(xFrame, pFrame->GetObjectShell());", code)

    def test_one_guard_per_frame_and_document(self):
        code = added(PATCH, FILE)
        self.assertIn("if (rGuard->Guards(rxFrame, xModelId))", code)
        self.assertIn("std::erase_if(aGuards,", code)


if __name__ == "__main__":
    unittest.main()
