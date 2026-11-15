# SPDX-License-Identifier: AGPL-3.0-only
"""The engine's public result (what the document layer consumes), input validation and speed."""
import json
import time
import unittest

import citation_golden as golden

from hst_office import citation_engine as engine
from hst_office import citation_style as styles


class Process(unittest.TestCase):
    def test_result_shape_is_json_safe(self):
        items = golden.samples()
        result = engine.process(styles.load_style("vn-so"), items, golden.clusters(items), uncited_ids=["nope"])
        json.dumps(result)
        self.assertEqual(set(result), {"citations", "bibliography", "numbers", "missing", "warnings"})
        first = result["citations"][0]
        self.assertEqual(set(first), {"citationID", "runs", "text", "html", "note"})
        self.assertEqual((first["citationID"], first["text"], first["note"]), ("c-vi-book", "[3]", False))
        bibliography = result["bibliography"]
        self.assertEqual((bibliography["title"], bibliography["numbered"], bibliography["hangingIndent"]),
                         ("TÀI LIỆU THAM KHẢO", True, True))
        group = bibliography["groups"][0]
        self.assertEqual((group["language"], group["heading"]), ("vi", "Tiếng Việt"))
        entry = group["entries"][0]
        self.assertEqual((entry["id"], entry["number"], entry["label"]), ("vi-book-2", 1, "1."))
        self.assertIn("<i>Cơ sở di truyền học ứng dụng</i>", entry["html"])
        self.assertEqual(result["numbers"]["vi-book-2"], 1)

    def test_bad_input_is_reported_not_fatal(self):
        items = {"a": {"id": "a", "type": "book", "title": "T", "author": [{"family": "Smith"}]}}
        clusters = [{"citationID": "x", "items": [{"id": "a"}, {"id": "gone"}]}, {"citationID": "bad", "items": []},
                    "garbage", {"citationID": "y", "items": [{"id": "a", "label": "nonsense", "locator": 5}]}]
        result = engine.process(styles.load_style("vn-so"), items, clusters)
        self.assertEqual([c["text"] for c in result["citations"]], ["[1], [?]", "?", "?", "[1]"])
        self.assertEqual(result["missing"], ["gone"])
        self.assertEqual(len(result["warnings"]), 3)
        with self.assertRaises(ValueError):
            engine.clean_cite({"id": ""})

    def test_note_style_marks_footnotes_and_uncited_items_are_listed(self):
        items = golden.samples()
        result = engine.process(styles.load_style("chicago-chu-thich"), items, golden.clusters(items)[:1],
                                uncited_ids=["en-krugman"])
        self.assertTrue(result["citations"][0]["note"])
        self.assertTrue(result["citations"][0]["text"].endswith("."))
        listed = [e["id"] for g in result["bibliography"]["groups"] for e in g["entries"]]
        self.assertEqual(sorted(listed), ["en-krugman", "vi-book"])
        self.assertEqual(result["numbers"], {})

    def test_preview(self):
        item = golden.samples()[0]
        preview = engine.preview(styles.load_style("vn-tac-gia-nam"), item, "15")
        self.assertEqual(preview["citation"]["text"], "(Trần Văn Bình, 2010, tr. 15)")
        self.assertTrue(preview["entry"]["text"].startswith("Trần Văn Bình (2010), Kinh tế học vĩ mô"))

    def test_thousand_items_are_fast(self):
        base = golden.samples()
        items = [dict(base[n % len(base)], id="i%d" % n, title="%s %d" % (base[n % len(base)]["title"], n))
                 for n in range(1000)]
        clusters = [{"citationID": str(n), "items": [{"id": "i%d" % n}]} for n in range(1000)]
        for style_id in ("vn-so", "apa-7"):
            style, times = styles.load_style(style_id), []
            for _ in range(3):  # a document refresh in a running office: the name/sort caches are warm after the first
                start = time.perf_counter()
                result = engine.process(style, items, clusters, document_language="vi")
                times.append(time.perf_counter() - start)
            self.assertEqual(sum(len(g["entries"]) for g in result["bibliography"]["groups"]), 1000)
            print("\n%s: 1000 items + 1000 citations in %.2f s (first run %.2f s)" % (style_id, min(times), times[0]))
            # target 0.3 s on the Linux build machine (measured 0.22-0.27 s); the bound leaves room for slow CI runners
            self.assertLess(min(times), 1.0)


if __name__ == "__main__":
    unittest.main()
