# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/perf large-file harness: fixture shapes, profile seeds and the summary (offline, small sizes)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

PERF = Path(__file__).resolve().parents[2] / "scripts/perf"
sys.path.insert(0, str(PERF))

import large_file_fixtures_text as text  # noqa: E402
import large_file_open_profile as profile  # noqa: E402
from large_file_fixtures_xlsx import retarget_generator, write_xlsx  # noqa: E402


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def sheet(self, name, **kw):
        write_xlsx(self.tmp / name, 50, True, kw.pop("generator", "Microsoft Excel"), **kw)
        with zipfile.ZipFile(self.tmp / name) as z:
            return z.read("xl/worksheets/sheet1.xml").decode(), z.read("docProps/app.xml").decode()

    def test_shared_formulas_with_cached_results(self):
        sheet, _ = self.sheet("f.xlsx")
        self.assertIn('<f t="shared" ref="N2:N51" si="3">SUMIF(B:B,B2,K:K)</f><v>', sheet)
        self.assertIn('<f t="shared" si="3"/><v>', sheet)

    def test_no_results_variant(self):
        sheet, app = self.sheet("n.xlsx", generator="SyntheticExport", results=False)
        self.assertIn('<f t="shared" si="3"/></c>', sheet)
        self.assertNotIn("</f><v>", sheet)
        self.assertIn("<Application>SyntheticExport</Application>", app)

    def test_other_generator_keeps_sheets(self):
        self.sheet("f.xlsx")
        retarget_generator(self.tmp / "f.xlsx", self.tmp / "o.xlsx", "SyntheticExport")
        with zipfile.ZipFile(self.tmp / "f.xlsx") as a, zipfile.ZipFile(self.tmp / "o.xlsx") as b:
            self.assertEqual(a.read("xl/worksheets/sheet1.xml"), b.read("xl/worksheets/sheet1.xml"))
            self.assertIn(b"SyntheticExport", b.read("docProps/app.xml"))

    def test_text_encodings(self):
        cases = {"bom.txt": dict(bom=True, newline="\r\n"), "u16.txt": dict(encoding="utf-16-le", bom=True),
                 "plain.txt": {}, "legacy.txt": dict(encoding="cp1258")}
        for name, kw in cases.items():
            text.write_txt(self.tmp / name, 0.02, 14, **kw)
        self.assertTrue((self.tmp / "bom.txt").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", (self.tmp / "bom.txt").read_bytes())
        self.assertTrue((self.tmp / "u16.txt").read_bytes().startswith(b"\xff\xfe"))
        self.assertFalse((self.tmp / "plain.txt").read_bytes().startswith(b"\xef\xbb\xbf"))
        (self.tmp / "plain.txt").read_bytes().decode("utf-8")
        with self.assertRaises(UnicodeDecodeError):
            (self.tmp / "legacy.txt").read_bytes().decode("utf-8")
        text.write_txt(self.tmp / "huge.txt", 0.05, 100_000)
        self.assertEqual((self.tmp / "huge.txt").read_bytes().count(b"\n"), 1)  # one line of all the text

    def test_text_jobs_cover_the_shapes(self):
        for name in ("text-short-50mb.txt", "text-hugelines-50mb.txt", "text-bom-crlf-50mb.txt",
                     "text-utf16-50mb.txt", "text-cp1258-50mb.txt", "text-lines-50mb.txt"):
            self.assertIn(name, text.TEXT_JOBS)


class Profile(unittest.TestCase):
    def test_spell_seed(self):
        self.assertIn('IsSpellAuto" oor:op="fuse"><value>true', profile.seed_items("spell"))
        self.assertIn('IsSpellAuto" oor:op="fuse"><value>false', profile.seed_items("default"))

    def test_reseed_puts_items_back(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "user").mkdir()
        (tmp / "user" / "registrymodifications.xcu").write_text("<oor:items>\n</oor:items>\n", encoding="utf-8")
        profile.reseed(str(tmp), "norowheight")
        self.assertIn("RecalcOptimalRowHeightMode", (tmp / "user" / "registrymodifications.xcu").read_text())


class Summary(unittest.TestCase):
    def test_crash_timeout_and_times(self):
        out = Path(tempfile.mkdtemp())
        rows = [{"label": "before", "file": "a.xlsx", "size_mb": 1, "office_exit": 3221226505, "after": 611.0,
                 "peak_mb": 900},
                {"label": "after", "file": "a.xlsx", "size_mb": 1, "load": 8.0, "idle": 8.5, "peak_mb": 700},
                {"label": "after", "file": "b.txt", "size_mb": 2, "error": "timeout", "after": 900, "peak_mb": 5}]
        (out / "x.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        md = subprocess.run([sys.executable, str(PERF / "large-file-open-summary.py"), str(out)],
                            capture_output=True, text=True, check=True).stdout
        self.assertIn("CRASH 0xC0000409 at 611.0 s", md)
        self.assertIn("8.0 / 8.5 s, 700 MB", md)
        self.assertIn("TIMEOUT@900 s", md)


if __name__ == "__main__":
    unittest.main()
