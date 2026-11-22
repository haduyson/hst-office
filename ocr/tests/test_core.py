# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Unit tests of the OCR core (no UNO, no models: Tesseract output is faked where needed).

Run: python3 -m unittest discover -s ocr/tests   (needs Pillow, numpy and OpenCV)
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "core"), os.path.join(HERE, "..", "bench")]

from PIL import Image, ImageDraw  # noqa: E402

from hst_ocr import __main__ as cli  # noqa: E402
from hst_ocr import formula_pix2tex, pipeline, protocol, table_grid, text_tesseract  # noqa: E402
from hst_ocr.protocol import OcrError  # noqa: E402

TSV_HEAD = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def word(block, par, line, num, x, y, w, h, text, conf=95):
    return "5\t1\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%s" % (block, par, line, num, x, y, w, h, conf, text)


class TempImage:
    def __init__(self, img):
        self.img = img

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        self.img.save(self.path)
        return self.path

    def __exit__(self, *exc):
        os.unlink(self.path)


class ProtocolTest(unittest.TestCase):
    def test_valid_request_gets_defaults(self):
        with TempImage(Image.new("L", (50, 50), 255)) as path:
            req = protocol.parse_request({"version": 1, "image": path})
        self.assertEqual((req.mode, req.lang, req.threads), ("text", "vie", 2))

    def test_rejections_carry_stable_codes(self):
        with TempImage(Image.new("L", (50, 50), 255)) as path:
            cases = [
                ([], "bad-request"),
                ({"image": path}, "bad-version"),
                ({"version": 1, "image": "relative.png"}, "bad-request"),
                ({"version": 1, "image": path, "extra": 1}, "bad-request"),
                ({"version": 1, "image": path, "mode": "pdf"}, "bad-request"),
                ({"version": 1, "image": path, "threads": True}, "bad-request"),
                ({"version": 1, "image": path, "threads": 0}, "bad-request"),
                ({"version": 1, "image": path, "lang": "vie;rm -rf"}, "bad-request"),
                ({"version": 1, "image": path + ".missing"}, "image-missing"),
            ]
            for data, code in cases:
                with self.subTest(data=data), self.assertRaises(OcrError) as caught:
                    protocol.parse_request(data)
                self.assertEqual(caught.exception.code, code)


class TesseractTsvTest(unittest.TestCase):
    def test_lines_of_a_paragraph_join_and_paragraphs_split(self):
        tsv = "\n".join([TSV_HEAD,
                         word(1, 1, 1, 1, 10, 10, 40, 20, "Câu"), word(1, 1, 1, 2, 60, 10, 30, 20, "1."),
                         word(1, 1, 2, 1, 10, 40, 50, 20, "tiếp"),
                         "4\t1\t1\t1\t3\t0\t0\t0\t0\t0\t-1\t",
                         word(1, 2, 1, 1, 10, 90, 40, 20, "Đáp", conf=-1)])
        blocks = text_tesseract.paragraphs_from_tsv(tsv, offset=(100, 0))
        self.assertEqual([b["text"] for b in blocks], ["Câu 1. tiếp", "Đáp"])
        self.assertEqual(blocks[0]["bbox"], [110, 10, 80, 50])
        self.assertEqual(blocks[1]["confidence"], 0.0)  # only "no confidence" words

    def test_missing_program_is_reported(self):
        with mock.patch.object(text_tesseract.resources, "tesseract_exe", return_value="/nonexistent/tesseract"):
            with self.assertRaises(OcrError) as caught:
                text_tesseract.run_tsv(Image.new("L", (20, 20), 255))
        self.assertEqual(caught.exception.code, "engine-missing")


class PipelineTest(unittest.TestCase):
    def test_errors_become_error_responses(self):
        resp = pipeline.run({"version": 1, "image": "/nonexistent/x.png"})
        self.assertEqual(resp, {"version": 1, "ok": False,
                                "error": {"code": "image-missing", "message": "image not found"}})

    def test_unreadable_image(self):
        fd, path = tempfile.mkstemp(suffix=".png")
        os.write(fd, b"not a png")
        os.close(fd)
        try:
            self.assertEqual(pipeline.run({"version": 1, "image": path})["error"]["code"], "image-unreadable")
        finally:
            os.unlink(path)

    def test_text_mode_response_shape(self):
        tsv = "\n".join([TSV_HEAD, word(1, 1, 1, 1, 10, 10, 40, 20, "Xin"), word(1, 1, 1, 2, 60, 10, 40, 20, "chào")])
        with TempImage(Image.new("L", (2400, 100), 255)) as path, \
                mock.patch.object(text_tesseract, "run_tsv", return_value=tsv):
            resp = pipeline.run({"version": 1, "image": path, "mode": "text"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["blocks"][0]["text"], "Xin chào")
        json.dumps(resp)  # must be plain JSON

    def test_page_without_layout_model_falls_back_to_text(self):
        with TempImage(Image.new("L", (2400, 100), 255)) as path, \
                mock.patch.object(pipeline.layout_ppdoc, "available", return_value=False), \
                mock.patch.object(text_tesseract, "run_tsv", return_value=TSV_HEAD):
            resp = pipeline.run({"version": 1, "image": path, "mode": "page"})
        self.assertEqual(resp["warnings"], ["layout-missing"])
        self.assertIsNone(resp["engine"]["layout"])


class CliTest(unittest.TestCase):
    def test_bad_json_and_internal_errors_still_answer_json(self):
        self.assertEqual(cli._answer("{nope")["error"]["code"], "bad-json")
        with mock.patch.object(cli.pipeline, "run", side_effect=ZeroDivisionError("boom")):
            self.assertEqual(cli._answer('{"version": 1}')["error"]["code"], "internal")


class FormulaCleanTest(unittest.TestCase):
    def test_token_text_to_latex(self):
        self.assertEqual(formula_pix2tex._clean("\\ frac { 1 } { 2 } [EOS]"), "\\frac{1}{2}")
        self.assertEqual(formula_pix2tex._clean("\\ sin Ġ x"), "\\sin x")

    def test_blank_image_has_no_formula(self):
        with self.assertRaises(OcrError) as caught:
            formula_pix2tex._crop_pad(Image.new("L", (64, 64), 255))
        self.assertEqual(caught.exception.code, "no-content")


def ruled_table(merge_first_row=False):
    """3 x 3 bordered grid of 120 x 60 cells; the first row may be one merged cell."""
    img = Image.new("L", (400, 220), 255)
    draw = ImageDraw.Draw(img)
    x0, y0, cw, ch = 20, 20, 120, 60
    for r in range(4):
        draw.line((x0, y0 + r * ch, x0 + 3 * cw, y0 + r * ch), fill=0, width=3)
    for c in range(4):
        top = y0 + ch if merge_first_row and c in (1, 2) else y0
        draw.line((x0 + c * cw, top, x0 + c * cw, y0 + 3 * ch), fill=0, width=3)
    return img


class TableGridTest(unittest.TestCase):
    WORDS = [(80, 50, 30, 20, "A"), (200, 50, 30, 20, "B"), (80, 110, 30, 20, "1"), (330, 170, 30, 20, "9")]

    def test_grid_and_word_assignment(self):
        with mock.patch.object(table_grid, "_words_without_rules", return_value=self.WORDS):
            result = table_grid.cells(ruled_table())
        self.assertEqual(result["rows"], [["A", "B", ""], ["1", "", ""], ["", "", "9"]])

    def test_merged_cell_gets_colspan(self):
        with mock.patch.object(table_grid, "_words_without_rules", return_value=self.WORDS):
            result = table_grid.cells(ruled_table(merge_first_row=True))
        first = result["cells"][0]
        self.assertEqual((first["colspan"], first["rowspan"], first["text"]), (3, 1, "A B"))

    def test_no_borders_means_no_table(self):
        self.assertIsNone(table_grid.cells(Image.new("L", (300, 200), 255)))

    def test_reading_order_within_a_cell(self):
        words = [(60, 41, 30, 20, "hai"), (20, 40, 30, 18, "một"), (20, 80, 30, 20, "ba")]
        self.assertEqual([w[4] for w in table_grid._reading_order(words)], ["một", "hai", "ba"])


class MetricsTest(unittest.TestCase):
    def test_cer_and_formula_equivalences(self):
        from metrics import cer, diacritic_errors, formula_scores
        self.assertEqual(cer("Câu  1 – a", "Câu 1 - a"), 0.0)
        self.assertAlmostEqual(cer("abcd", "abed"), 0.25)
        self.assertEqual(diacritic_errors("đoạn thẳng", "đoạn thằng"), 0.5)
        self.assertEqual(formula_scores("x^2", "x^{2}"), (0.0, True))
        self.assertTrue(formula_scores(r"\lim_{x\to 0}x", r"\operatorname*{lim}_{x\rightarrow0}x")[1])
        self.assertFalse(formula_scores("x^2", "x^3")[1])


if __name__ == "__main__":
    unittest.main()
