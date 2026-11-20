# SPDX-License-Identifier: AGPL-3.0-only
"""The synthetic large .docx of the recovery kill check: a valid package, reproducible, as large as its picture."""
import os
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
import make_large_docx_fixture as fixture  # noqa: E402


class LargeDocxFixtureTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def test_a_valid_word_package(self):
        with zipfile.ZipFile(fixture.write(self.path("a.docx"), side=64, paragraphs=10)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(sorted(archive.namelist()), sorted([
                "[Content_Types].xml", "_rels/.rels", "word/_rels/document.xml.rels", "word/document.xml",
                "word/media/noise.png"]))
            document = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Đoạn văn mẫu số 10", document)
        self.assertIn('r:embed="rIdImg1"', document)
        self.assertEqual(document.count("<w:tr>"), 20)

    def test_the_same_bytes_every_time(self):
        first = open(fixture.write(self.path("a.docx"), side=64, paragraphs=10), "rb").read()
        second = open(fixture.write(self.path("b.docx"), side=64, paragraphs=10), "rb").read()
        self.assertEqual(first, second)

    def test_the_picture_is_a_png_of_the_given_side(self):
        png = fixture.noise_png(32)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        width, height, depth, colour = struct.unpack(">IIBB", png[16:26])
        self.assertEqual((width, height, depth, colour), (32, 32, 8, 2))
        idat_length = struct.unpack(">I", png[33:37])[0]
        self.assertEqual(len(zlib.decompress(png[41:41 + idat_length])), 32 * (32 * 3 + 1))

    def test_the_default_size_makes_a_slow_save(self):
        # The picture is stored, not deflated: the package is about side*side*3 bytes, ~18.8 MB by default.
        size = os.path.getsize(fixture.write(self.path("big.docx")))
        self.assertGreater(size, 18_000_000)
        self.assertLess(size, 21_000_000)

    def test_bad_arguments_are_refused(self):
        with self.assertRaises(SystemExit):
            fixture.main([self.path("x.docx"), "--picture-side", "0"])


if __name__ == "__main__":
    unittest.main()
