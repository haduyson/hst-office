# SPDX-License-Identifier: AGPL-3.0-only
"""English UI strings name the apps Sheets and Slides (hst-app-names-en-us.patch), in step with the vi catalogue.

Every English string the patch renames has a l10n/vi-overrides.jsonl row whose "msgid_new" is the new English text,
so the Vietnamese translation keeps matching; no renamed source text (msgid_new) names Calc or Impress.
"""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches" / "libreoffice" / "hst-app-names-en-us.patch"
APP_WORD = re.compile(r"(?<![%\w])(?<!%PRODUCTNAME )(Calc|Impress)\b")
# Identifiers and legacy format names that keep the engine's words.
KEPT = re.compile(r"\.uno:|StarCalc|STARCALC|STARIMPRESS|MS Excel|MS PowerPoint|org\.openoffice\.Office")


def patch_lines(sign):
    return [line[1:] for line in PATCH.read_text(encoding="utf-8").splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


def override_rows():
    lines = (ROOT / "l10n" / "vi-overrides.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def forms(text):
    """The text as it appears in .hrc/.ulf (po escapes) and in .ui/.xcu (XML escapes)."""
    plain = text.replace('\\"', '"').replace("\\n", "\n")
    return {text, plain, plain.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}


class EnglishAppNames(unittest.TestCase):
    def test_patch_removes_the_old_names_and_adds_none(self):
        self.assertIn("hst-app-names-en-us.patch", (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8"))
        removed, added = patch_lines("-"), patch_lines("+")
        self.assertGreaterEqual(sum(bool(APP_WORD.search(line)) for line in removed), 60)
        leftovers = [line.strip()[:120] for line in added if APP_WORD.search(KEPT.sub("", line))]
        self.assertEqual(leftovers, [])
        self.assertFalse(any("BluetoothServiceRecord" in line for line in patch_lines("+") + patch_lines("-")))

    def test_every_renamed_english_string_has_its_vietnamese_row(self):
        added = "\n".join(patch_lines("+"))
        ours = [row for row in override_rows() if row.get("msgid_new") and APP_WORD.search(row["msgid"])
                and any(form in added for form in forms(row["msgid_new"]))]
        self.assertGreaterEqual(len(ours), 60)
        for row in ours:
            self.assertNotRegex(row["msgstr"], APP_WORD, row["msgctxt"])  # "%PRODUCTNAME Calc" reads "Sheets"

    def test_no_renamed_source_text_names_calc_or_impress(self):
        bad = [(row["msgctxt"], row["msgid_new"]) for row in override_rows()
               if row.get("msgid_new") and APP_WORD.search(KEPT.sub("", row["msgid_new"]))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
