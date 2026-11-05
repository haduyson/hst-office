# SPDX-License-Identifier: AGPL-3.0-only
"""The wizard's live monospace preview (nd30_preview) mirrors the inserted layout."""
import unittest

import _paths  # noqa: F401
from hst_office import nd30, nd30_layout


class Preview(unittest.TestCase):
    """The wizard's live monospace preview (nd30_preview) mirrors the inserted layout."""

    def preview(self, type_id, fields=None, width=64):
        from hst_office import nd30_preview
        return nd30_preview.layout_to_preview(nd30_layout.build_layout(type_id, fields or {}), width).split("\n")

    def test_header_columns_side_by_side(self):
        rows = self.preview("thong-bao", {"agency": "Sở A", "number": "7", "symbol": "tb-sa"})
        self.assertIn("SỞ A", rows[0])
        self.assertIn("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", rows[0])
        self.assertTrue(any("Số: 07/TB-SA" in r for r in rows))
        self.assertTrue(any("THÔNG BÁO" in r for r in rows))
        self.assertTrue(any(set(r.strip()) == {"─"} for r in rows), "rules are drawn")

    def test_lines_fit_width(self):
        long = "Về việc " + "rất dài " * 30
        for t in nd30.rules()["documentTypes"]:
            if t.get("module") == "sheets":
                continue
            for row in self.preview(t["id"], {"summary": long, "body": long, "kinhGui": "A\nB"}, 60):
                self.assertLessEqual(len(row), 60, row)

    def test_kinh_gui_dashes_align_under_colon(self):
        rows = self.preview("to-trinh", {"kinhGui": "Ủy ban nhân dân thành phố\nSở Tài chính"})
        label = next(r for r in rows if r.strip() == "Kính gửi:")
        items = [r for r in rows if r.strip().startswith("- ") and r.strip().endswith((";", "."))][:2]
        colon = label.index(":")
        self.assertEqual([r.index("-") for r in items], [items[0].index("-")] * 2)
        self.assertLessEqual(abs(items[0].index("-") - colon), 2)

    def test_signature_block(self):
        rows = self.preview("quyet-dinh", {"signerAuthority": "kt. giám đốc", "signerName": "Nguyễn Văn A"})
        self.assertTrue(any(r.startswith("Nơi nhận:") and "KT. GIÁM ĐỐC" in r for r in rows))
        self.assertIn("Nguyễn Văn A", rows[-1])


class OfficialLetterSummary(unittest.TestCase):
    def test_typed_ve_viec_is_not_doubled(self):
        for typed in ("Về việc triển khai", "về việc: triển khai", "V/v triển khai", "triển khai"):
            text = nd30_layout.layout_to_text(nd30_layout.build_layout("cong-van", {"summary": typed}))
            self.assertIn("V/v triển khai", text, typed)


if __name__ == "__main__":
    unittest.main()
