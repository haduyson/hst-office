# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese user interface by default on every system: the configuration default and the Windows installer rule.

Read from the patches themselves (the new side of each hunk), so no LibreOffice tree is needed:
- UILocale's schema default is "vi", a plain default (not finalized), so the user's profile and an administrator win;
- the MSI's SelectLanguage always keeps the vi and en-US packs, also over a migrated "absent" state of an upgrade;
- the runtime checks start from a profile without a stored UILocale, so they measure this default.
"""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
OOR = "{http://openoffice.org/2001/registry}"


def new_side(patch, path):
    """Text of every hunk of `path` as it reads after the patch (context and added lines)."""
    lines, inside, keep = [], False, False
    for line in (PATCHES / patch).read_text(encoding="utf-8").splitlines():
        if line.startswith("--- "):
            inside = False
        elif line.startswith("+++ "):
            inside = line[4:].split("\t")[0].strip() == "b/" + path
        elif inside and line.startswith("@@"):
            keep = True
        elif inside and keep and line[:1] in (" ", "+"):
            lines.append(line[1:])
        elif inside and keep and line == "":
            lines.append("")
    if not lines:
        raise AssertionError(f"{patch} does not change {path}")
    return "\n".join(lines)


def series():
    text = (PATCHES / "series").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in text if line.strip() and not line.startswith("#")]


class ConfigurationDefault(unittest.TestCase):
    PATCH = "hst-ui-language-vi-default.patch"
    XCS = "officecfg/registry/schema/org/openoffice/Office/Linguistic.xcs"

    def uilocale(self):
        text = new_side(self.PATCH, self.XCS)
        match = re.search(r'<prop oor:name="UILocale".*?</prop>', text, re.S)
        self.assertIsNotNone(match, "the hunk must carry the whole UILocale property")
        return ET.fromstring(match.group(0).replace("oor:", "xmlns:oor='http://openoffice.org/2001/registry' oor:", 1))

    def test_patch_is_in_the_series(self):
        self.assertIn(self.PATCH, series())

    def test_default_is_vietnamese(self):
        prop = self.uilocale()
        self.assertEqual(prop.get(OOR + "type"), "xs:string")
        values = prop.findall("value")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].text, "vi")

    def test_user_and_administrator_still_win(self):
        prop = self.uilocale()
        # A schema default is the lowest layer: a finalized default would lock every user to Vietnamese.
        self.assertIsNone(prop.get(OOR + "finalized"))
        self.assertIsNone(prop.get(OOR + "mandatory"))
        # Empty stays a valid stored choice ("Default": the system's language), so the string may not be nillable.
        self.assertEqual(prop.get(OOR + "nillable"), "false")

    def test_no_other_layer_sets_uilocale(self):
        # Another shipped layer above the schema (data .xcu, extension, Windows policy template) would hide this
        # default or, worse, be taken for a user's choice.
        for name in series():
            if name == self.PATCH:
                continue
            text = (PATCHES / name).read_text(encoding="utf-8")
            added = [l for l in text.splitlines() if l.startswith("+") and 'oor:name="UILocale"' in l]
            self.assertEqual(added, [], name)
        for path in (ROOT / "extensions").rglob("*.xcu"):
            self.assertNotIn('"UILocale"', path.read_text(encoding="utf-8"), str(path))


class WindowsInstaller(unittest.TestCase):
    PATCH = "hst-msi-vi-langpack.patch"
    CXX = "setup_native/source/win32/customactions/sellang/sellang.cxx"
    SCP = "scp2/source/ooo/windowscustomaction_ooo.scp"

    def test_patch_is_last_and_after_the_default(self):
        names = series()
        self.assertIn(self.PATCH, names)
        self.assertLess(names.index(ConfigurationDefault.PATCH), names.index(self.PATCH))

    def test_vi_and_en_are_always_relevant_without_ui_langs(self):
        text = new_side(self.PATCH, self.CXX)
        branch = text.split("} else {", 1)[1]
        first = re.findall(r'add_ui_lang\((.*?)\);', branch)[:2]
        self.assertEqual(first, ['"vi"', '"en"'])
        # An administrator's UI_LANGS list keeps selecting exactly what it names.
        self.assertIn('GetMsiPropA( handle, "UI_LANGS", &pVal )', text)

    def test_selected_packs_and_dictionaries_are_installed_locally(self):
        text = new_side(self.PATCH, self.CXX)
        self.assertRegex(text, r'if \(langs\[i\]\.install\) \{[^}]*"gm_Langpack_r_%s"[^}]*INSTALLSTATE_LOCAL')
        self.assertIn("dicts[i].install ? INSTALLSTATE_LOCAL : INSTALLSTATE_ABSENT", text)

    def test_runs_after_feature_state_migration(self):
        text = new_side(self.PATCH, self.SCP)
        block = re.search(r"WindowsCustomAction gid_Customaction_SelectLanguage.*?\nEnd", text, re.S).group(0)
        assignments = re.findall(r'Assignment\d = \("(\w+)", "(.*?)", "(\w+)"\);', block)
        self.assertEqual({a[0] for a in assignments}, {"InstallExecuteSequence", "InstallUISequence"})
        for _, condition, position in assignments:
            self.assertEqual(position, "behind_MigrateFeatureStates")
            # first install only, and never over a feature choice made in Custom Setup or on the command line
            self.assertEqual(condition, 'NOT Installed And (ADDLOCAL=\\"\\" Or NOT UI_LANGS=\\"\\")')


class RuntimeChecksMeasureTheDefault(unittest.TestCase):
    def test_r1_profile_does_not_store_a_ui_language(self):
        text = (ROOT / "tests/runtime/r1auto/office.py").read_text(encoding="utf-8")
        seed = re.search(r"hst_gui\.seed_profile\(.*?\]\)", text, re.S)
        self.assertIsNotNone(seed)
        self.assertIn("Welcome", seed.group(0))
        self.assertNotIn("UILocale", seed.group(0))

    def test_language_selection_has_the_default_phase(self):
        text = (ROOT / "tests/runtime/check-language-selection.py").read_text(encoding="utf-8")
        self.assertIn('"default": phase_default', text)


if __name__ == "__main__":
    unittest.main()
