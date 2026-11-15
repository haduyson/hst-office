# SPDX-License-Identifier: AGPL-3.0-only
"""Rich ribbon tooltips: every ribbon command of Writer, Sheets, Slides and Draw has a sentence (or is listed under
"except"), the sentences are short plain Vietnamese, and the generated patch matches the data.

Data: data/ribbon/tooltip-descriptions.json; ribbon commands: data/ribbon/tooltip-inventory.json (regenerated from a
fresh-applied tree by scripts/ribbon/ribbon-tooltip-inventory.py, which also reports when the ribbon changed)."""
import importlib.util
import json
import os
import re
import sys
import unittest

from _paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "scripts", "l10n"))
from vi_tone import fix as fix_tone  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "generate_ribbon_tooltips", os.path.join(ROOT, "scripts", "patches", "generate-ribbon-tooltips.py"))
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
APPS = ("writer", "calc", "impress", "draw")
MAX_VI = 90
OTHER_VENDOR = re.compile(r"Microsoft|\bWord\b|\bExcel\b|PowerPoint|\bOffice 365\b|\bM365\b")  # product names: case kept
VI_LETTERS = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def load(name):
    with open(os.path.join(ROOT, "data", "ribbon", name), encoding="utf-8") as handle:
        return json.load(handle)


DATA = load("tooltip-descriptions.json")
INVENTORY = load("tooltip-inventory.json")["apps"]


def sentences():
    """[(where, command, {"en", "vi"})] of every sentence in the data."""
    rows = [("common", cmd, t) for cmd, t in DATA["descriptions"].items()]
    for app, table in DATA.get("app_descriptions", {}).items():
        rows += [(app, cmd, t) for cmd, t in table.items()]
    return rows


class Coverage(unittest.TestCase):
    def test_every_ribbon_command_has_a_sentence_or_is_excepted(self):
        excepted = {cmd for cmds in DATA["except"].values() for cmd in cmds}
        for app in APPS:
            own = DATA.get("app_descriptions", {}).get(app, {})
            ribbon = INVENTORY[app]["main"] + INVENTORY[app]["contextual"]
            self.assertGreater(len(ribbon), 150, app)
            missing = [cmd for cmd in ribbon if cmd not in INVENTORY[app]["ui_described"] and cmd not in own
                       and cmd not in DATA["descriptions"] and cmd not in excepted]
            self.assertEqual(missing, [], f"{app}: ribbon commands without a sentence")

    def test_exceptions_are_ribbon_commands_with_a_reason(self):
        ribbon = {cmd for app in APPS for cmd in INVENTORY[app]["main"] + INVENTORY[app]["contextual"]}
        for reason, cmds in DATA["except"].items():
            self.assertGreater(len(reason), 10)
            self.assertEqual(sorted(set(cmds) - ribbon), [], reason)
            self.assertEqual(sorted(set(cmds) & set(DATA["descriptions"])), [], reason)

    def test_app_keys(self):
        self.assertLessEqual(set(DATA.get("app_descriptions", {})), set(APPS))
        self.assertEqual(sorted(INVENTORY), sorted(APPS))


class Wording(unittest.TestCase):
    def test_vietnamese_is_short_plain_and_complete(self):
        for where, cmd, text in sentences():
            vi, en = text["vi"], text["en"]
            label = f"{where} {cmd}: {vi}"
            self.assertLessEqual(len(vi), MAX_VI, label)
            self.assertRegex(vi, VI_LETTERS, label)  # written with diacritics
            self.assertTrue(vi[0].isupper() and vi.endswith(".") and not vi.endswith(".."), label)
            self.assertNotIn("\n", vi + en, label)
            self.assertNotIn("tập tin", vi.lower(), label)  # glossary: "tệp tin"
            self.assertEqual(fix_tone(vi), vi, label)  # new-style tones: "xóa", "hủy"
            self.assertIsNone(OTHER_VENDOR.search(vi + " " + en), label)
            self.assertTrue(en and en.endswith(".") and len(en) <= 110, f"{where} {cmd}: {en}")

    def test_commands_are_command_urls(self):
        for _where, cmd, _text in sentences():
            self.assertRegex(cmd, r"^(\.uno:[A-Za-z0-9_.]+|[a-z.]+:[A-Za-z0-9]+)$")


class ReferenceDesign(unittest.TestCase):
    """1.0.2 reference design: Writer sentences, toolbar wording, tips under the ribbon."""

    def overrides(self):
        with open(os.path.join(ROOT, "l10n", "vi-overrides.jsonl"), encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def test_vietnamese_says_thanh_cong_cu(self):
        # owner rule 15/11: never "ribbon" or "dải lệnh" in text the user sees
        banned = re.compile(r"ribbon|dải lệnh", re.I)
        self.assertEqual([cmd for _w, cmd, text in sentences() if banned.search(text["vi"])], [])
        self.assertEqual([r["msgctxt"] for r in self.overrides() if banned.search(r["msgstr"])], [])
        patch = open(os.path.join(PATCHES, "hst-ribbon-mockup-tooltip.patch"), encoding="utf-8").read()
        self.assertIn('+msgstr "Ghim thanh công cụ (Ctrl+F1)"', patch)
        self.assertIn('NC_("STR_HST_RIBBON_PIN", "Pin the Toolbar (Ctrl+F1)")', patch)

    def test_writer_sentences_are_the_designs(self):
        writer = DATA["app_descriptions"]["writer"]
        self.assertEqual(writer[".uno:SubScript"]["vi"], "Viết chữ nhỏ ở dưới dòng, như H₂O.")
        self.assertEqual(writer[".uno:InsertPageHeader"]["vi"], "Thêm hoặc sửa phần đầu trang.")
        # sentences a Writer .ui line gives are replaced through the .po: the key must be such a line
        described = {t["en"] for t in INVENTORY["writer"]["ui_described"].values()}
        # (menu buttons have no command, their .ui lines are not in the inventory)
        rows = [r for r in self.overrides() if r["msgctxt"] == "TabbedWriter|hstUxTip"
                and r["reason"].startswith("Writer ribbon tooltip sentence")]
        self.assertGreaterEqual(len(rows), 30)
        self.assertEqual([r["msgid"] for r in rows if r["msgid"] not in described], [])
        self.assertIn("Căn đều cả hai lề, thường dùng cho văn bản hành chính.", [r["msgstr"] for r in rows])
        # short bold names of the design: no full stop, no shortcut (added at run time), Writer only for now
        for cmd, app, en, vi in gen.titles(DATA):
            self.assertTrue(app in APPS and 0 < len(vi) <= 30 and not vi.endswith(".") and "(" not in vi, (cmd, vi))
            self.assertEqual(fix_tone(vi), vi)
        self.assertEqual(DATA["app_titles"]["writer"][".uno:Underline"]["vi"], "Gạch chân")

    def test_tip_goes_under_the_ribbon(self):
        patch = open(os.path.join(PATCHES, "hst-ribbon-mockup-tooltip.patch"), encoding="utf-8").read()
        for needle in ("constexpr tools::Long RIBBON_TIP_GAP = 2;", "constexpr tools::Long RIBBON_TIP_INSET = 4;",
                       "constexpr tools::Long RIBBON_TIP_MAX_WIDTH = 300;", "dynamic_cast<NotebookBar*>(pWin)",
                       "PositionByToolkit(", "eType == WindowType::MENUBUTTON", "Lookup(aHstRibbonTitles,",
                       "const bool bNative = !bPlaced"):
            self.assertIn(needle, patch)
        series = open(os.path.join(PATCHES, "series"), encoding="utf-8").read().split()
        self.assertLess(series.index("hst-ribbon-rich-tooltips.patch"), series.index("hst-ribbon-mockup-tooltip.patch"))


class GeneratedPatch(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(PATCHES, "hst-ribbon-tooltip-descriptions.patch"), encoding="utf-8") as handle:
            self.patch = handle.read()

    def test_table_and_catalogue_match_the_data(self):
        rows, titles = gen.entries(DATA), gen.titles(DATA)
        self.assertIn("\n".join("+" + line for line in gen.hrc_lines(rows, titles)) + "\n", self.patch)
        self.assertIn("\n".join("+" + line for line in gen.po_lines(rows, titles)) + "\n", self.patch)
        self.assertEqual(len({(gen.context(c, a), en) for c, a, en, _vi in rows}), len(rows))

    def test_po_hunk_sits_before_the_anchor_with_context_on_both_sides(self):
        hunk = self.patch.split("--- a/translations/source/vi/sfx2/messages.po\n", 1)[1].splitlines()[2:]
        self.assertTrue(all(line.startswith(" ") for line in hunk[:3] + hunk[-3:]), (hunk[:3], hunk[-3:]))
        self.assertEqual(hunk[-1], " " + gen.ANCHOR)
        self.assertTrue(hunk[-3].startswith(" #. "))


class Wiring(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
            return handle.read()

    def test_series_order(self):
        series = [line.strip() for line in self.read("series").splitlines() if line.strip()]
        self.assertLess(series.index("hst-ribbon-rich-tooltips.patch"),
                        series.index("hst-ribbon-tooltip-descriptions.patch"))

    def test_render_paths(self):
        patch = self.read("hst-ribbon-rich-tooltips.patch")
        for needle in ("RichTitle         = 0x0800", "is_typed_flags<QuickHelpFlags, 0xf7f>",  # flag and mask
                       "virtual bool            ShowRichTooltip(",  # SalFrame default: plain tooltip
                       "gtk_tooltip_set_markup(tooltip", "g_markup_escape_text",  # GTK: escaped markup, bold title
                       "ImplLayoutRich();", "ImplPaintRich(rRenderContext);",  # Windows, macOS, gen
                       "& QuickHelpFlags::RichTitle))",  # a plain tip window is not reused for a rich one
                       "hst::ribbon::RequestRichHelp(*this, rHEvt",  # NotebookbarToolBox
                       "QuickHelpFlags::RichTitle);",  # the ribbon asks for a rich tip
                       "sfx2/source/notebookbar/HstRibbonTooltip \\"):
            self.assertIn(needle, patch)
        # GTK markup: both the title (labels such as "Thu phóng & dời") and the sentence are escaped
        self.assertEqual(patch.count("g_markup_escape_text("), 2)
        # no new delay: the tip keeps HelpSettings' delay and hide timer
        self.assertNotIn("GetTipDelay", "".join(l for l in patch.splitlines() if l.startswith("+")))


if __name__ == "__main__":
    unittest.main()
