# SPDX-License-Identifier: AGPL-3.0-only
import json
import os
import unittest

import _paths  # noqa: F401
from hst_office import welcome_content as wc

with open(os.path.join(_paths.ROOT, "data", "hst", "solutions.json"), encoding="utf-8") as _f:
    DATA = json.load(_f)
UTM = DATA["utm"]
TAIL = "utm_source=hst-office&utm_medium=%s&utm_campaign=hst-office-1-0"


class UtmUrl(unittest.TestCase):
    def test_without_query(self):
        self.assertEqual(wc.build_utm_url("https://aios.hasontech.vn", "welcome", UTM), "https://aios.hasontech.vn?" + TAIL % "welcome")
        self.assertEqual(wc.build_utm_url("https://espace.vn/zaloapp", "menu", UTM), "https://espace.vn/zaloapp?" + TAIL % "menu")

    def test_existing_query_is_extended_with_ampersand(self):
        self.assertEqual(wc.build_utm_url("https://a.vn/p?x=1&y=2", "menu", UTM), "https://a.vn/p?x=1&y=2&" + TAIL % "menu")

    def test_fragment_stays_last_and_utm_not_duplicated(self):
        got = wc.build_utm_url("https://a.vn/p?utm_medium=old&x=1#top", "welcome", UTM)
        self.assertEqual(got, "https://a.vn/p?x=1&" + TAIL % "welcome" + "#top")
        self.assertEqual(got.count("utm_medium"), 1)

    def test_rejects_unknown_medium_and_unsafe_urls(self):
        with self.assertRaises(ValueError):
            wc.build_utm_url("https://a.vn", "email", UTM)
        for bad in ("http://a.vn", "javascript:alert(1)", "file:///etc/passwd", "ftp://a.vn", "https://", "https://a.vn/ x", "//a.vn", ""):
            with self.subTest(bad), self.assertRaises(ValueError):
                wc.build_utm_url(bad, "menu", UTM)

    def test_display_url(self):
        self.assertEqual(wc.display_url("https://espace.vn/zaloapp"), "espace.vn/zaloapp")
        self.assertEqual(wc.display_url("https://hasontech.vn/"), "hasontech.vn")


class Model(unittest.TestCase):
    def test_order_and_links_from_data(self):
        model = wc.build_model(DATA, "welcome")
        self.assertEqual([s["name"] for s in model["solutions"]], [s["name"] for s in DATA["solutions"]])
        self.assertEqual(len(model["solutions"]), 6)
        for sol in model["solutions"]:
            self.assertTrue(sol["url"].endswith(TAIL % "welcome"), sol["url"])
        self.assertEqual(model["services"], "Digital Marketing · Thiết kế Website · Lập trình ứng dụng, phần mềm theo yêu cầu")
        self.assertEqual(model["contact"]["website"], "https://hasontech.vn?" + TAIL % "welcome")
        self.assertEqual(model["contact"]["phone"], "(0236) 3.507.507")
        # Owner decision 2026-10-29: every solution, HST Content included, links its live site.
        self.assertTrue(all(not s.get("note") for s in model["solutions"]))

    def test_menu_medium(self):
        self.assertTrue(all(s["url"].endswith(TAIL % "menu") for s in wc.build_model(DATA, "menu")["solutions"]))

    def test_malformed_data_fails_loudly(self):
        with self.assertRaises(KeyError):
            wc.build_model({"company": DATA["company"], "utm": UTM}, "menu")
        with self.assertRaises(ValueError):
            wc.build_model(dict(DATA, solutions=[]), "menu")
        bad = json.loads(json.dumps(DATA))
        bad["solutions"][0]["url"] = "http://insecure.example"
        with self.assertRaises(ValueError):
            wc.build_model(bad, "menu")


class Locales(unittest.TestCase):
    def test_welcome_strings_match_in_both_languages(self):
        base = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "locales")
        vi, en = (json.load(open(os.path.join(base, c + ".json"), encoding="utf-8")) for c in ("vi", "en"))
        self.assertEqual(set(vi["welcome"]), set(en["welcome"]))
        self.assertEqual(vi["welcome"]["title"], "Chào mừng đến HST Office")
        self.assertEqual(vi["menu"]["solutions"], "Giải pháp HASON TECH...")


if __name__ == "__main__":
    unittest.main()
