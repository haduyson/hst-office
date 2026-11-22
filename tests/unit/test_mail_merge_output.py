# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư, "Hoàn tất và trộn": the engine (com.sun.star.text.MailMerge) is disposed right after it runs, also
when it fails, so no engine outlives the merge (one still alive at quit closes its document after Writer is gone)."""
import os
import tempfile
import unittest
import zipfile
from unittest import mock

import _paths  # noqa: F401

from hst_office import mail_merge_output as output


class Engine:
    def __init__(self, fail=False):
        self.fail, self.disposed = fail, 0

    def execute(self, _arguments):
        if self.fail:
            raise RuntimeError("engine error")

    def dispose(self):
        self.disposed += 1


class Session:
    def stage(self, *_arguments):
        return "HST_TronThu_test"


def run(engine, action=output.PDF):
    request = output.Request(action, [0, 1], "{Họ và tên}", "/nonexistent-folder")
    with mock.patch.object(output, "_engine", return_value=engine), \
            mock.patch.object(output, "_execute", side_effect=lambda ctx, merge, request, work: merge.execute(())):
        return output.run(None, None, Session(), request)


class EngineRelease(unittest.TestCase):
    def test_disposed_after_the_merge(self):
        engine = Engine()
        self.assertEqual(run(engine), (None, 2))
        self.assertEqual(engine.disposed, 1)

    def test_disposed_when_the_merge_fails(self):
        engine = Engine(fail=True)
        with self.assertRaises(RuntimeError):
            run(engine)
        self.assertEqual(engine.disposed, 1)

    def test_engine_without_dispose_is_only_dropped(self):
        output._release(object())
        output._release(None)

    def test_dispose_error_is_not_raised(self):
        engine = Engine()
        engine.dispose = mock.Mock(side_effect=RuntimeError("disposed"))
        with mock.patch("hst_office.diag_log.exception") as logged:
            output._release(engine)
        logged.assert_called_once()

    def test_no_reference_kept_in_the_module(self):
        engine = Engine()
        run(engine)
        self.assertFalse([name for name, value in vars(output).items() if value is engine])



def odt(folder, meta):
    path = os.path.join(folder, "tron-thu.odt")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
        package.writestr("meta.xml", '<office:document-meta xmlns:office="o" xmlns:meta="m">%s'
                                     '</office:document-meta>' % meta)
        package.writestr("content.xml", "<office:document-content/>")
    return path


class MergeResultMark(unittest.TestCase):
    """The merged document is marked before it is opened, so its layout has no blank page between recipients."""

    def test_mark_added_and_package_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = odt(folder, "<office:meta><meta:generator>HST</meta:generator></office:meta>")
            output.mark_merge_result(path)
            output.mark_merge_result(path)  # once only
            with zipfile.ZipFile(path) as package:
                first = package.infolist()[0]
                meta = package.read("meta.xml").decode("utf-8")
                self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))
                self.assertEqual(package.namelist(), ["mimetype", "meta.xml", "content.xml"])
            self.assertEqual(meta.count(output.META_FIELD), 1)
            self.assertIn("<meta:generator>HST</meta:generator>" + output.META_FIELD + "</office:meta>", meta)

    def test_empty_meta(self):
        with tempfile.TemporaryDirectory() as folder:
            path = odt(folder, "<office:meta/>")
            output.mark_merge_result(path)
            with zipfile.ZipFile(path) as package:
                self.assertIn("<office:meta>" + output.META_FIELD + "</office:meta>", package.read("meta.xml").decode())


if __name__ == "__main__":
    unittest.main()
