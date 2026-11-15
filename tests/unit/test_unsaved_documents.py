# SPDX-License-Identifier: AGPL-3.0-only
"""Tài liệu chưa lưu (unsaved_store, unsaved_dialog labels) and the settings-repair notice (profile_notice): the files
the office writes are read, expired ones hidden, deletions done; no office needed."""
import os
import tempfile
import time
import unittest

import _paths  # noqa: F401
from hst_office import profile_notice
from hst_office import unsaved_store as store

NOW = 1_800_000_000


def write(folder, stem, info=None, size=10):
    path = os.path.join(folder, stem + ".odt")
    with open(path, "wb") as handle:
        handle.write(b"x" * size)
    if info is not None:
        with open(path + ".txt", "w", encoding="utf-8") as handle:
            handle.write("HST-UNSAVED 1\n" + "".join("%s\t%s\n" % kv for kv in info.items()))
    return path


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_info(self):
        self.assertEqual(store.parse_info("HST-UNSAVED 1\ntitle\tBáo cáo\nurl\t\n"), {"title": "Báo cáo", "url": ""})
        self.assertEqual(store.parse_info("something else\ntitle\tx\n"), {})
        self.assertEqual(store.parse_info(""), {})

    def test_lists_newest_first_and_hides_expired(self):
        write(self.folder, "a", {"title": "Cũ", "saved": NOW - 100, "closed": NOW - 50})
        write(self.folder, "b", {"title": "Mới", "url": "file:///home/u/b.docx", "saved": NOW - 20, "closed": NOW - 10})
        write(self.folder, "c", {"title": "Hết hạn", "saved": NOW - 9 * 86400, "closed": NOW - 8 * 86400})
        kept = store.list_kept(self.folder, now=NOW)
        self.assertEqual([k.title for k in kept], ["Mới", "Cũ"])
        self.assertEqual(kept[0].url, "file:///home/u/b.docx")
        self.assertEqual(kept[0].saved, NOW - 20)

    def test_copy_without_description_uses_its_own_time(self):
        path = write(self.folder, "d")
        os.utime(path, (NOW - 5, NOW - 5))
        (kept,) = store.list_kept(self.folder, now=NOW)
        self.assertEqual((kept.title, kept.closed), ("", NOW - 5))

    def test_delete_and_delete_all(self):
        write(self.folder, "a", {"closed": time.time()})
        write(self.folder, "b", {"closed": time.time()})
        first = store.list_kept(self.folder)[0]
        self.assertTrue(store.delete(first))
        self.assertFalse(os.path.exists(first.path) or os.path.exists(first.info))
        self.assertEqual(store.delete_all(self.folder), 1)
        self.assertEqual(os.listdir(self.folder), [])

    def test_missing_folder(self):
        self.assertEqual(store.list_kept(os.path.join(self.folder, "none")), [])

    def test_file_path(self):
        self.assertEqual(store.file_path("file:///home/u/B%C3%A1o%20c%C3%A1o.docx"), "/home/u/Báo cáo.docx")
        self.assertEqual(store.file_path("https://x/y.docx"), "")
        self.assertEqual(store.file_path(""), "")


class DialogLabels(unittest.TestCase):
    def test_labels(self):
        from hst_office import unsaved_dialog as dlg
        kept = store.Kept("/p/x.odt", "/p/x.odt.txt", "", "file:///home/u/b.docx", "", 0, 0, 1)
        self.assertEqual(dlg.display_name(kept), "b.docx")
        self.assertEqual(dlg.display_name(kept._replace(url="")), dlg.UNTITLED)
        self.assertEqual(dlg.item_label(kept._replace(title="Báo cáo"), localtime=time.gmtime),
                         "Báo cáo · tự lưu 00:00 01/01/1970")
        self.assertEqual(dlg.origin_label(kept), "Tệp gốc: /home/u/b.docx")
        self.assertEqual(dlg.origin_label(kept._replace(url="")), dlg.NEVER_SAVED)

    def test_texts_name_no_other_product(self):
        import re
        from hst_office import unsaved_dialog as dlg
        texts = " ".join(v for k, v in vars(dlg).items() if k.isupper() and isinstance(v, str))
        texts += " ".join(profile_notice.TEXT.values())
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint|LibreOffice|OpenOffice", texts))
        self.assertIn("7 ngày", dlg.EMPTY)


class ProfileNotice(unittest.TestCase):
    def test_marker_is_taken_once(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(profile_notice.take_marker(folder))
            with open(os.path.join(folder, profile_notice.MARKER), "w") as handle:
                handle.write("restored\n")
            self.assertEqual(profile_notice.take_marker(folder), "restored")
            self.assertIsNone(profile_notice.take_marker(folder))
            with open(os.path.join(folder, profile_notice.MARKER), "w") as handle:
                handle.write("garbage")
            self.assertEqual(profile_notice.take_marker(folder), "reset")


if __name__ == "__main__":
    unittest.main()
