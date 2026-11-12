# SPDX-License-Identifier: AGPL-3.0-only
"""Owner decisions of 2026-11-13 on the Vietnamese UI (docs/L10N_GLOSSARY.md):

- tab and group names of the ribbon are in sentence case: only the first word is capitalised ("Bố trí trang",
  "Thiết kế bảng", "Đầu trang & chân trang"), proper nouns and abbreviations excepted;
- the menu bar is "Thanh trình đơn", never "Thanh menu";
- Media is "Đa phương tiện", never "Phương tiện" alone.

The texts come from the layers HST owns, in the order the build applies them: the Vietnamese .po lines the patches
add, l10n/vi/*.jsonl (fills only empty upstream strings) and l10n/vi-overrides.jsonl (wins). The labels HST matches
against in data/ribbon/ and the bundled help follow the same rules.
"""
import glob
import json
import os
import re
import unittest

from _paths import ROOT

TABBED = re.compile(r"^Tabbed(?:Writer|Calc|Impress|Draw)\|(?:\w*TabLabel|\w*MenuButton|label\w+)$")
# words that keep their capital letter inside a name
PROPER = {"Việt", "Nam", "HASON", "TECH", "Unicode", "Basic", "Python"}
PO_PREFIX = "+++ b/translations/source/vi/"


def plain(text):
    return re.sub(r"[~_]", "", text)


def capitalised_words(text):
    """Words after the first that start with a capital and are neither abbreviations nor proper nouns."""
    words = plain(text).split()
    return [w for w in words[1:] if w[:1].isupper() and not (len(w) > 1 and w.isupper()) and w not in PROPER
            and not any(c.isdigit() for c in w)]


def patch_po_entries():
    """{(file, msgctxt, msgid): msgstr} of the Vietnamese .po entries the patches of the series add."""
    entries = {}
    series = os.path.join(ROOT, "patches", "libreoffice", "series")
    with open(series, encoding="utf-8") as handle:
        names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
    for name in names:
        current, fields = None, {}
        with open(os.path.join(ROOT, "patches", "libreoffice", name), encoding="utf-8") as handle:
            for line in handle.read().split("\n"):
                if line.startswith("+++ "):
                    current = line[len(PO_PREFIX):].split("\t")[0] if line.startswith(PO_PREFIX) else None
                    continue
                if not current or not line.startswith("+"):
                    continue
                match = re.match(r'^\+(msgctxt|msgid|msgstr) "(.*)"$', line)
                if not match:
                    continue
                fields[match.group(1)] = match.group(2)
                if match.group(1) == "msgstr" and "msgctxt" in fields and "msgid" in fields:
                    entries[(current, fields["msgctxt"], fields["msgid"])] = fields["msgstr"]
                    fields = {}
    return entries


def jsonl_rows(pattern):
    for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def effective():
    """{(file, msgctxt, msgid): msgstr} as far as HST's own layers decide it."""
    texts = dict(patch_po_entries())
    for row in jsonl_rows("l10n/vi/*.jsonl"):
        texts.setdefault((row["file"], row["msgctxt"], row["msgid"]), row["msgstr"])
    for row in jsonl_rows("l10n/vi-overrides.jsonl"):
        texts[(row["file"], row["msgctxt"], row.get("msgid_new") or row["msgid"])] = row["msgstr"]
    return texts


class RibbonNamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts = effective()

    def test_capitalised_words_helper(self):
        self.assertEqual(capitalised_words("~Bố trí Trang"), ["Trang"])
        self.assertEqual(capitalised_words("Đầu trang & C~hân trang"), ["Chân"])
        self.assertEqual(capitalised_words("Định dạng Việt Nam"), [])
        self.assertEqual(capitalised_words("Đối tượng 3D"), [])
        self.assertEqual(capitalised_words("Macro VBA"), [])

    def test_tab_and_group_names_are_in_sentence_case(self):
        bad = {key[1]: text for key, text in self.texts.items() if TABBED.match(key[1]) and capitalised_words(text)}
        self.assertEqual(bad, {})

    def test_the_known_names(self):
        wanted = {
            ("sc/messages.po", "TabbedCalc|LayoutTabLabel", "Page ~Layout"): "~Bố trí trang",
            ("sw/messages.po", "TabbedWriter|TableDesignTabLabel", "Table ~Design"): "Thiết kế bả~ng",
            ("sw/messages.po", "TabbedWriter|ImageTabLabel", "Picture ~Format"): "Định dạng ả~nh",
            ("sd/messages.po", "TabbedImpress|DrawTabLabel", "Shape For~mat"): "Định dạng hình dạn~g",
            ("sd/messages.po", "TabbedImpress|TableTabLabel", "Table ~Layout"): "Bố trí bản~g",
            ("sw/messages.po", "TabbedWriter|HeaderFooterTabLabel", "~Header & Footer"): "Đầu trang & c~hân trang",
            ("sw/messages.po", "TabbedWriter|labelInsertMedia", "Media"): "Đa phương tiện",
            ("sd/messages.po", "TabbedImpress|labelInsertMedia", "Media"): "Đa phương tiện",
        }
        for key, text in wanted.items():
            self.assertEqual(self.texts.get(key), text, key)

    def test_menubar_is_thanh_trinh_don(self):
        bad = {key: text for key, text in self.texts.items() if "thanh menu" in plain(text).lower()}
        self.assertEqual(bad, {})
        key = ("officecfg/registry/data/org/openoffice/Office/UI.po",
               "GenericCommands.xcu\\n..GenericCommands.UserInterface.Popups..uno:Menubar\\nLabel\\nvalue.text", "Menubar")
        self.assertEqual(self.texts[key], "Thanh trình đơn")

    def test_media_is_da_phuong_tien(self):
        bad = {}
        for key, text in self.texts.items():
            lowered = plain(text).lower()
            if re.search(r"\bmedia\b", key[2], re.I) and "phương tiện" in lowered \
                    and lowered.count("phương tiện") != lowered.count("đa phương tiện"):
                bad[key] = text
        self.assertEqual(bad, {})

    def test_ribbon_data_uses_the_shown_names(self):
        def walk(node):
            if isinstance(node, dict):
                for name, value in node.items():
                    if name in ("hst_tab", "hst_group", "tab", "group") and isinstance(value, str):
                        yield value
                    else:
                        yield from walk(value)
            elif isinstance(node, list):
                for value in node:
                    yield from walk(value)
        for name in ("office-parity.json", "launchers.json"):
            with open(os.path.join(ROOT, "data", "ribbon", name), encoding="utf-8") as handle:
                labels = set(walk(json.load(handle)))
            # "Kiểu WordArt" names the Office group the parity spec maps; it is not a label HST shows
            self.assertEqual(sorted(v for v in labels if capitalised_words(v) and v != "Kiểu WordArt"), [], name)
            self.assertNotIn("Phương tiện", labels, name)


class HelpTermsTest(unittest.TestCase):
    def test_help_and_menu_texts_say_thanh_trinh_don(self):
        folder = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
        paths = glob.glob(os.path.join(folder, "help", "*.html")) + glob.glob(os.path.join(folder, "locales", "*.json"))
        paths.append(os.path.join(folder, "Addons.xcu"))
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                self.assertNotIn("thanh menu", handle.read().lower(), path)


if __name__ == "__main__":
    unittest.main()
