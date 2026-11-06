# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese UI labels end without "..." / "…" (owner rule 2026-11-06), except the kept categories."""
import glob
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/l10n"))
import vi_ellipsis  # noqa: E402


def jsonl_rows():
    for name in sorted(glob.glob(str(ROOT / "l10n/vi/*.jsonl"))) + [str(ROOT / "l10n/vi-overrides.jsonl")]:
        with open(name, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    yield f"{Path(name).name}:{number}", json.loads(line)


class CategoryTest(unittest.TestCase):
    def test_labels_lose_the_ellipsis_and_keep_access_keys(self):
        for old, new in (("Thuộc tính...", "Thuộc tính"), ("Lưu ~thành...", "Lưu ~thành"), ("C_hữ ký số…", "C_hữ ký số"),
                         ("Tùy chọn …", "Tùy chọn"), ("Xác định ~phạm vi....", "Xác định ~phạm vi")):
            self.assertEqual(vi_ellipsis.fix("sfx2/messages.po", "x|y", "Properties...", old), new)

    def test_kept_categories(self):
        cases = (("sw/messages.po", "STR_STATSTR_SWGWRITE", "Saving document...", "Đang lưu tài liệu...", "progress"),
                 ("svtools/messages.po", "STR_SVT_PRNDLG_WAITING", "Waiting", "Đợi...", "progress"),
                 ("svx/messages.po", "RID_SVXSTRARY_NUMBERINGTYPE", "1, 2, 3, ...", "1, 2, 3, ...", "omitted"),
                 ("sw/messages.po", "RID_SHELLRES_AUTOFMTSTRS", "Replace 1/2 ... with ½ ...",
                  "Thay thế 1/2 ... bằng ½ ...", "omitted"),
                 ("extensions/messages.po", "tableselectionpage|search", "_...", "_...", "glyph"),
                 ("cui/messages.po", "RID_SVXSTR_GALLERY_ID_EXISTS", "This ID already exists...", "Mã số này đã có...", "text"),
                 ("cui/messages.po", "RID_CUI_TIPOFTHEDAY", "Tip...", "Mẹo hay...", "text"),
                 ("officecfg/registry/data/org/openoffice/Office/UI.po", "x", "~Spelling...", "~Chính tả...", "label"),
                 ("sd/messages.po", "effectmenu|timing", "_Timing...", "_Thời gian...", "label"))
        for file, ctx, msgid, msgstr, kind in cases:
            self.assertEqual(vi_ellipsis.category(file, ctx, msgid, msgstr), kind, msgstr)
            self.assertEqual(vi_ellipsis.fix(file, ctx, msgid, msgstr) == msgstr, kind != "label", msgstr)
        self.assertIsNone(vi_ellipsis.category("sw/messages.po", "x", "A... b", "A... b"))

    def test_po_last_msgstr_line_only_and_patch_lines_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "messages.po"
            path.write_text('msgid ""\nmsgstr "Header..."\n\nmsgctxt "a|b"\nmsgid "Open..."\nmsgstr "Mở..."\n\n'
                            'msgctxt "a|c"\nmsgid "Long..."\nmsgstr ""\n"Dòng một "\n"dòng hai…"\n\n'
                            'msgctxt "a|d"\nmsgid "Print..."\nmsgstr "In..."\n\n'
                            'msgctxt "STR_STATSTR_X"\nmsgid "Saving..."\nmsgstr "Đang lưu..."\n', encoding="utf-8")
            counts = {}
            changed = vi_ellipsis.normalize_po(str(path), "sw/messages.po", frozenset({'msgstr "In..."'}), counts)
            self.assertEqual(changed, (2, 1))
            self.assertEqual(counts, {"label": 3, "progress": 1})
            text = path.read_text(encoding="utf-8")
            for part in ('msgstr "Header..."', 'msgstr "Mở"\n', '"Dòng một "\n"dòng hai"', 'msgstr "In..."',
                         'msgstr "Đang lưu..."'):
                self.assertIn(part, text)


class SourcesTest(unittest.TestCase):
    def test_translation_layers_have_no_label_ellipsis(self):
        bad = [f"{where}: {row['msgstr']}" for where, row in jsonl_rows()
               if vi_ellipsis.category(row["file"], row["msgctxt"], row.get("msgid_new") or row["msgid"],
                                       row["msgstr"]) == "label"]
        self.assertEqual(bad, [])

    def test_menu_and_ribbon_labels_in_the_access_key_snapshot(self):
        with open(ROOT / "l10n/access-keys-snapshot.json", encoding="utf-8") as handle:
            labels = json.load(handle)["labels"]
        bad = [label["vi"] for label in labels
               if vi_ellipsis.category(label["file"], (label.get("msgctxt") or "").replace("\n", "\\n"), label["msgid"],
                                       label["vi"]) == "label"]
        self.assertEqual(bad, [])

    def test_extension_menu_strings(self):
        for language in ("vi", "en"):
            with open(ROOT / f"extensions/hst-vietnamese-tools/locales/{language}.json", encoding="utf-8") as handle:
                menu = json.load(handle)["menu"]
            self.assertEqual([v for v in menu.values() if v.endswith(("...", "…"))], [], language)

    def test_keep_list_rows_name_a_category(self):
        for (file, ctx), kind in vi_ellipsis.keep_list().items():
            self.assertIn(kind, {"text", "progress", "omitted"}, (file, ctx))


if __name__ == "__main__":
    unittest.main()
