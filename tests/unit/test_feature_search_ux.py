# SPDX-License-Identifier: AGPL-3.0-only
"""Feature search (Alt+Q) keywords and ranking, offline.

The index of the search is built at run time from the menus, the add-on menus and the ribbon; the search words of
extensions/hst-vietnamese-tools/FeatureSearch.xcu are matched against what users type. This test mirrors the ranking
of hst-feature-search-ux.patch (scoreMatch in CommandPopup.cxx) and checks queries users type that used to find
nothing: each must reach its command through the keywords alone. It also checks the 20 HST tips of the day
(hst-tipoftheday-hst-tips.patch).
"""
import os
import re
import unicodedata
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

EXT = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-feature-search-ux.patch")
TIPS = os.path.join(ROOT, "patches", "libreoffice", "hst-tipoftheday-hst-tips.patch")
TIP_LINE = re.compile(r'^\+\s+\{ NC_\("RID_CUI_TIPOFTHEDAY", "([^"]+)"\), "([^"]*)", "", (\w+)\},$', re.M)
PO_ADDED = re.compile(r'^\+msgid "([^\n]+)"\n\+msgstr "([^\n]+)"$', re.M)
OOR = "{http://openoffice.org/2001/registry}"
LABEL_SCORE = (0, 30, 70, 80, 90, 95, 100)
EASY = ".uno:ConditionalFormatEasy?FormatRule:short=%d"
# (query, command); Slides "trang chieu moi" also needs the dispatch of commands without an SFX slot
GATE = (("le trang", ".uno:PageDialog"), ("margin", ".uno:PageDialog"), ("word count", ".uno:WordCountDialog"),
        ("gop o", ".uno:ToggleMergeCells"), ("xoa trung", ".uno:HandleDuplicateRecords"),
        ("pivot", ".uno:DataDataPilotRun"), ("freeze", ".uno:FreezePanes"), ("vlookup", ".uno:FunctionDialog"),
        ("trang chieu moi", ".uno:InsertSlide"), ("lưu dưới dạng", ".uno:SaveAs"), ("save as", ".uno:SaveAs"),
        ("luu ban sao", ".uno:SaveAs"), ("save a copy", ".uno:SaveAs"),
        ("nen ban trinh chieu", ".uno:PresentationMinimizer"), ("nén bản trình chiếu", ".uno:PresentationMinimizer"),
        ("tham chieu", ".uno:InsertReferenceField"), ("but dinh dang", ".uno:FormatPaintbrush"),
        ("chổi định dạng", ".uno:FormatPaintbrush"), ("phoi thu", ".uno:MailMergeWizard"),
        ("binh luan", ".uno:InsertAnnotation"), ("vi lenh", ".uno:MacroManager"), ("dem tu", ".uno:WordCountDialog"),
        ("co dinh dong", ".uno:FreezePanes"), ("dong bang", ".uno:FreezePanes"), ("bang xoay", ".uno:DataDataPilotRun"),
        ("tron o", ".uno:ToggleMergeCells"), ("canh le", ".uno:PageDialog"), ("sumif", ".uno:FunctionDialog"),
        ("countif", ".uno:FunctionDialog"), ("conditional formatting", ".uno:ConditionalFormatMenu"),
        # items of the conditional formatting menu, indexed from their keywords (built at run time)
        ("trung lap", EASY % 8), ("duplicate", EASY % 8), ("to sang", EASY % 8), ("top 10", EASY % 11),
        ("tren trung binh", EASY % 15), ("lon hon", EASY % 2), ("thanh du lieu", ".uno:DataBarFormatDialog?IconSet:short=0"),
        ("xoa quy tac", ".uno:HstConditionalFormatClear?Scope:short=0"), ("new rule", ".uno:ConditionalFormatDialog"),
        ("quan ly quy tac", ".uno:ConditionalFormatManagerDialog"))


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def fold(text):
    """foldForSearch: NFD, combining marks dropped, case-folded, đ as d, "~" dropped, white space collapsed."""
    text = unicodedata.normalize("NFD", text).casefold()
    text = "".join("d" if c == "đ" else c for c in text if unicodedata.category(c) != "Mn" and c != "~")
    return " ".join(text.split())


def strength(haystack, needle):
    """matchStrength: 6 whole text, 5 start to a word end, 4 whole word, 3 start, 2 word start, 1 inside, 0 none."""
    if not haystack or not needle:
        return 0
    if haystack == needle:
        return 6
    best, pos = 0, haystack.find(needle)
    while pos >= 0 and best < 5:
        end = pos + len(needle)
        start_ok = pos == 0 or not haystack[pos - 1].isalnum()
        end_ok = end == len(haystack) or not haystack[end].isalnum()
        best = max(best, (5 if end_ok else 3) if pos == 0 else (4 if end_ok else 2) if start_ok else 1)
        pos = haystack.find(needle, pos + 1)
    return best


def score(entry, query):
    """scoreMatch of an entry {command, label, path, keywords, tooltip} (texts already folded)."""
    total = LABEL_SCORE[strength(entry.get("label", ""), query)]
    kw = strength(entry.get("keywords", ""), query)
    total = max(total, 75 if kw >= 4 else 65 if kw >= 2 else 0)
    path = strength(entry.get("path", ""), query)
    total = max(total, 50 if path >= 4 else 40 if path >= 2 else 25 if path == 1 else 0)
    rest = entry.get("path", "") + " " + entry.get("tooltip", "") + " " + entry.get("keywords", "")
    if not total and all(word in rest for word in query.split()):
        total = 20
    if not total:
        return 0
    return total + (0 if entry["command"].startswith(".uno:") else 8) + (5 if entry.get("keywords") else 0)


def child(root, name):
    return next(node for node in root.findall("node") if node.get(OOR + "name") == name)


def keywords():
    """{command: folded words} as the patch builds it (words of several entries for one command are joined)."""
    words = {}
    root = ET.parse(os.path.join(EXT, "FeatureSearch.xcu")).getroot()
    for node in child(root, "Keywords"):
        props = {p.get(OOR + "name"): p.findtext("value") for p in node.findall("prop")}
        words[props["Command"]] = (words.get(props["Command"], "") + " " + fold(props["Words"])).strip()
    return words


def suggestions():
    root = ET.parse(os.path.join(EXT, "FeatureSearch.xcu")).getroot()
    result = {}
    for node in child(root, "Suggestions"):
        props = {p.get(OOR + "name"): p for p in node.findall("prop")}
        result[props["Module"].findtext("value")] = [it.text for it in props["Commands"].find("value")]
    return result


class FeatureSearchUxTest(unittest.TestCase):
    def test_audit_queries_reach_their_command(self):
        words = keywords()
        for query, command in GATE:
            with self.subTest(query=query):
                self.assertIn(command, words)
                self.assertGreaterEqual(score({"command": command, "keywords": words[command]}, fold(query)), 65)

    def test_word_start_ranks_before_hst_boost_and_inside_a_word(self):
        words = keywords()
        entries = [
            {"command": ".uno:NumberFormatCurrency", "label": "Tiền tệ", "path": "Định dạng ▸ Định dạng số ▸ Tiền tệ"},
            {"command": "org.hst.office.vi:UILanguageVi", "label": "Tiếng Việt",
             "path": "HST ▸ Ngôn ngữ giao diện ▸ Tiếng Việt"},
            {"command": ".uno:FreezePanesColumn", "label": "Cố định cột đầu tiên", "path": "Xem ▸ Cố định cột đầu tiên"},
            {"command": "org.hst.office.vi:FormatVnd", "label": "Định dạng tiền VND", "path": "HST ▸ Định dạng tiền VND"},
            {"command": ".uno:Gallery", "label": "Bộ sưu tập", "path": "Xem ▸ Bộ sưu tập"},
        ]
        for entry in entries:
            for key in ("label", "path"):
                entry[key] = fold(entry[key])
            entry["keywords"] = words.get(entry["command"], "")
        ranked = sorted(entries, key=lambda e: -score(e, "tien"))  # stable: equal ranks keep the menu order
        commands = [e["command"] for e in ranked if score(e, "tien")]
        self.assertLess(commands.index("org.hst.office.vi:FormatVnd"), commands.index("org.hst.office.vi:UILanguageVi"))
        self.assertLess(commands.index(".uno:FreezePanesColumn"), commands.index("org.hst.office.vi:UILanguageVi"))
        self.assertNotIn(".uno:Gallery", commands)
        self.assertGreater(score({"command": ".uno:X", "label": "dinh dang"}, "dang"),
                           score({"command": ".uno:Y", "label": "dang ky"}, "ang"))

    def test_patch_scores_match_this_mirror(self):
        text = re.sub(r"\n\+\s*", " ", read(PATCH))  # the added lines as one text
        self.assertIn("aLabelScore[] = { %s }" % ", ".join(map(str, LABEL_SCORE)), text)
        self.assertRegex(text, r"nKeyword >= 4 \? sal_Int32\(75\) : nKeyword >= 2 \? sal_Int32\(65\)")
        self.assertRegex(text, r"nPath >= 4 \? sal_Int32\(50\) : nPath >= 2 \? sal_Int32\(40\) "
                               r": nPath == 1 \? sal_Int32\(25\)")
        self.assertIn("nScore = 20;", text)
        self.assertIn('if (!rContent.m_aCommandURL.startsWith(".uno:")) nScore += 8;', text)
        self.assertIn("if (!rContent.m_aSearchableKeywords.isEmpty()) nScore += 5;", text)

    def test_fold_matches_typing_without_diacritics(self):
        self.assertEqual(fold("Định  dạng ~Tiền"), "dinh dang tien")
        self.assertEqual(fold(unicodedata.normalize("NFD", "Lề trang")), "le trang")

    def test_empty_box_suggests_five_known_commands_per_module(self):
        words = keywords()
        found = suggestions()
        self.assertEqual(set(found), {"com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument",
                                      "com.sun.star.presentation.PresentationDocument",
                                      "com.sun.star.drawing.DrawingDocument"})
        for module, commands in found.items():
            self.assertEqual(len(commands), 5, module)
            for command in commands:
                self.assertIn(command, words, (module, command))

    def test_schema_declares_suggestions_and_recent(self):
        text = read(os.path.join(EXT, "search.xcs"))
        self.assertIn('<set oor:name="Suggestions" oor:node-type="Suggestion"/>', text)
        self.assertIn('<prop oor:name="Recent" oor:type="oor:string-list">', text)
        self.assertIn('"/org.hasontech.hstoffice.FeatureSearch"', read(PATCH))
        self.assertIn("void MenuContentHandler::addKeywordOnlyContent()", read(PATCH))  # keyword-only commands

    def test_twenty_hst_tips_with_vietnamese_text(self):
        text = read(TIPS)
        tips = TIP_LINE.findall(text)
        self.assertEqual(len(tips), 20)
        self.assertEqual(tips[0][1], ".uno:CommandPopup")
        removed = [line for line in text.splitlines() if line.startswith("-") and "RID_CUI_TIPOFTHEDAY" in line]
        self.assertGreater(len(removed), 100)  # the upstream list goes
        po = dict(PO_ADDED.findall(text))
        for english, _, _ in tips:
            self.assertTrue(po.get(english), english)
        self.assertIn("Không thấy lệnh? Nhấn Alt+Q rồi gõ tên lệnh, không cần dấu.", po.values())
        self.assertIsNone(re.search(r"\b(Microsoft|Word|Excel|PowerPoint|LibreOffice)\b", " ".join(po.values())))

    def test_keywords_name_no_other_vendor(self):
        for command, words in keywords().items():
            self.assertIsNone(re.search(r"\b(microsoft|excel|powerpoint|outlook)\b", words), command)


if __name__ == "__main__":
    unittest.main()
