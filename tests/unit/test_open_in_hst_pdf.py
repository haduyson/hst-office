# SPDX-License-Identifier: AGPL-3.0-only
"""PDF ▸ Mở trong HST PDF (hst_office/open_in_hst_pdf.py): which file HST PDF shows, and the exported copy."""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

import _paths  # puts the extension's python/ on sys.path


uno = types.ModuleType("uno")
uno.createUnoStruct = lambda name: types.SimpleNamespace(Name=None, Value=None)
uno.systemPathToFileUrl = lambda path: "file://" + path
sys.modules["uno"] = uno

from hst_office import open_in_hst_pdf as op  # noqa: E402


class Choice(unittest.TestCase):
    def test_an_unchanged_pdf_is_shown_as_it_is(self):
        self.assertEqual(op.reusable_pdf("file:///tmp/hop-dong.PDF", False), "file:///tmp/hop-dong.PDF")
        self.assertIsNone(op.reusable_pdf("file:///tmp/hop-dong.pdf", True))  # changed: export the edits
        self.assertIsNone(op.reusable_pdf("file:///tmp/ban-ve.odg", False))
        self.assertIsNone(op.reusable_pdf("", False))  # never saved

    def test_filter_follows_the_document(self):
        self.assertEqual(op.pdf_filter(["com.sun.star.drawing.DrawingDocument"]), "draw_pdf_Export")
        self.assertEqual(op.pdf_filter(["com.sun.star.drawing.DrawingDocument",
                                        "com.sun.star.presentation.PresentationDocument"]), "impress_pdf_Export")
        self.assertEqual(op.pdf_filter(["com.sun.star.text.TextDocument"]), "writer_pdf_Export")
        self.assertIsNone(op.pdf_filter(["com.sun.star.sdb.OfficeDatabaseDocument"]))

    def test_file_name(self):
        self.assertEqual(op.pdf_file_name("Hợp đồng số 12.pdf"), "Hợp đồng số 12.pdf")
        self.assertEqual(op.pdf_file_name('a/b:c*?"<>|.odg'), "a b c.pdf")
        self.assertEqual(op.pdf_file_name("  "), "Bản vẽ.pdf")

    def test_the_command_is_registered(self):
        # actions.py needs the office to import; its table is read as text
        with open(os.path.join(_paths.ROOT, "extensions/hst-vietnamese-tools/python/hst_office/actions.py"), encoding="utf-8") as handle:
            self.assertIn('"OpenInHstPdf": open_in_hst_pdf.run,', handle.read())


class Run(unittest.TestCase):
    def host(self, location, modified):
        doc = mock.Mock()
        doc.hasLocation.return_value = bool(location)
        doc.getLocation.return_value = location
        doc.isModified.return_value = modified
        doc.getTitle.return_value = "ban-ve.pdf"
        doc.supportsService.side_effect = lambda s: s == "com.sun.star.drawing.DrawingDocument"
        desktop = mock.Mock()
        ctx = mock.Mock()
        ctx.ServiceManager.createInstanceWithContext.return_value = desktop
        return types.SimpleNamespace(doc=doc, ctx=ctx), desktop

    def test_unchanged_pdf_opens_without_export(self):
        host, desktop = self.host("file:///tmp/ban-ve.pdf", False)
        self.assertEqual(op.run(host), "file:///tmp/ban-ve.pdf")
        host.doc.storeToURL.assert_not_called()
        (url, target, flags, args), _ = desktop.loadComponentFromURL.call_args
        self.assertEqual((url, target, flags), ("file:///tmp/ban-ve.pdf", "_blank", 0))
        self.assertEqual([(a.Name, a.Value) for a in args], [("HSTPdfOpenInViewer", True)])  # whatever the Options say

    def test_changed_drawing_is_exported_to_a_folder_of_its_own(self):
        host, desktop = self.host("file:///tmp/ban-ve.pdf", True)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(op.tempfile, "mkdtemp", return_value=tmp):
            url = op.run(host)
        self.assertEqual(url, "file://" + os.path.join(tmp, "ban-ve.pdf"))
        (target, args), _ = host.doc.storeToURL.call_args
        self.assertEqual(target, url)
        self.assertEqual((args[0].Name, args[0].Value), ("FilterName", "draw_pdf_Export"))
        (loaded, _target, _flags, args), _ = desktop.loadComponentFromURL.call_args
        self.assertEqual(loaded, url)
        self.assertEqual([(a.Name, a.Value) for a in args], [("HSTPdfOpenInViewer", True)])


if __name__ == "__main__":
    unittest.main()
