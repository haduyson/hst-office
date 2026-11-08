# SPDX-License-Identifier: AGPL-3.0-only
"""Watermark acceptance math measured on actual synthetic PNG pixels."""
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw
from _paths import ROOT

sys.path.insert(0, str(Path(ROOT) / "tests/runtime"))
import pdf_watermark_metrics as metrics


class WatermarkMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reference = self.image("reference", 230)

    def image(self, name, grey=None, shift=(0, 0), dark_patch=False):
        image = Image.new("RGB", (128, 128), "white")
        draw = ImageDraw.Draw(image)
        if grey is not None:
            points = [(25, 100), (35, 110), (110, 35), (100, 25)]
            draw.polygon([(x + shift[0], y + shift[1]) for x, y in points], fill=(grey,) * 3)
        if dark_patch:
            draw.rectangle((64, 64, 71, 71), fill=(160,) * 3)
        path = self.root / (name + ".png")
        image.save(path)
        return str(path)

    def test_unchanged_pale_diagonal_passes_with_measured_reference_pixels(self):
        measured = metrics.measure(self.reference, self.image("same", 230))
        self.assertGreaterEqual(measured["pixels"], 200)
        self.assertEqual(measured["reference_mean"], 230.0)
        self.assertEqual(measured["mean"], 230.0)
        self.assertEqual(measured["solid_share"], 0.0)
        self.assertTrue(measured["faint"])

    def test_grey_tolerance_accepts_boundary_and_rejects_darker_watermark(self):
        for grey, expected in ((215, True), (214, False), (210, False)):
            with self.subTest(grey=grey):
                measured = metrics.measure(self.reference, self.image("grey-%d" % grey, grey))
                self.assertEqual(measured["mean"], float(grey))
                self.assertEqual(measured["solid_share"], 0.0)
                self.assertEqual(measured["faint"], expected)

    def test_opaque_dark_watermark_is_rejected(self):
        measured = metrics.measure(self.reference, self.image("dark", 130))
        self.assertEqual(measured["mean"], 130.0)
        self.assertEqual(measured["solid_share"], 1.0)
        self.assertFalse(measured["faint"])

    def test_excess_dark_pixels_fail_even_when_average_grey_remains_close(self):
        measured = metrics.measure(self.reference, self.image("patch", 230, dark_patch=True))
        self.assertLessEqual(abs(measured["mean"] - measured["reference_mean"]), 15)
        self.assertGreater(measured["solid_share"], 0.05)
        self.assertFalse(measured["faint"])

    def test_disappearing_watermark_is_rejected(self):
        measured = metrics.measure(self.reference, self.image("blank"))
        self.assertEqual(measured["mean"], 255.0)
        self.assertFalse(measured["faint"])

    def test_reference_without_a_watermark_cannot_pass_vacuously(self):
        with self.assertRaisesRegex(ValueError, "no translucent watermark"):
            metrics.measure(self.image("blank-reference"), self.reference)

    def test_one_pixel_edge_shifts_are_tolerated(self):
        for shift in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1)):
            with self.subTest(shift=shift):
                candidate = self.image("shift-%d-%d" % shift, 230, shift=shift)
                measured = metrics.measure(self.reference, candidate)
                self.assertEqual(measured["solid_share"], 0.0)
                self.assertTrue(measured["faint"])

    def test_crop_is_real_reference_and_candidate_image_evidence(self):
        crop = self.root / "crops/comparison.png"
        metrics.measure(self.reference, self.image("dark", 130), str(crop))
        with Image.open(crop) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (182, 86))


if __name__ == "__main__":
    unittest.main()
