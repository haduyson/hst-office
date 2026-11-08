# SPDX-License-Identifier: AGPL-3.0-only
"""Never accept a filename as proof of readable visual evidence."""
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
from _paths import ROOT
sys.path.insert(0, str(Path(ROOT) / "tests/runtime"))
from r1auto.artifacts import verify
from r1auto.results import row


class EvidenceTests(unittest.TestCase):
    def test_missing_empty_and_non_png_files_fail(self):
        for data in (None, b"", b"not an image"):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as tmp:
                if data is not None:
                    (Path(tmp) / "shot.png").write_bytes(data)
                report = dict(results=[row("W8", "PASS", "Đã đo", "shot.png")], owner_review=[])
                verify(tmp, report)
                self.assertEqual(report["results"][0]["status"], "FAIL")

    def test_valid_image_and_missing_owner_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new("RGB", (20, 20), "white").save(Path(tmp) / "shot.png")
            report = dict(results=[row("M4", "SKIP", "Chủ sở hữu duyệt", "shot.png")], owner_review=[])
            verify(tmp, report)
            self.assertEqual(report["results"][0]["status"], "SKIP")
            report["owner_review"].append(dict(item="M4", screenshot="missing.png"))
            verify(tmp, report)
            self.assertEqual(report["results"][0]["status"], "FAIL")
