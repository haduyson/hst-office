# SPDX-License-Identifier: AGPL-3.0-only
"""hst-user-autosave-{filter,toggle,test}.patch: "Tự động lưu" (AutoSave into the document's own file).

Offline checks of the patch text: the series order, the default only together with the filter, the framework store
through storeSelf with HstUserAutoSave (never the questioning store()), every string with its Vietnamese
translation, and a toggle without any other suite's names or images."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
FILTER, TOGGLE, TEST = (PATCHES / ("hst-user-autosave-%s.patch" % n) for n in ("filter", "toggle", "test"))
RECOVERY_DEFAULTS = ROOT / "extensions/hst-vietnamese-tools/RecoveryDefaults.xcu"
OOR = "{http://openoffice.org/2001/registry}"


def changes(patch):
    """{path: (removed lines, added lines)} of a unified diff."""
    out, current = {}, None
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is None or line.startswith(("@@", "--- ")):
            continue
        elif line.startswith("-"):
            current[0].append(line[1:])
        elif line.startswith("+"):
            current[1].append(line[1:])
    return out


def series():
    return [n.strip() for n in (PATCHES / "series").read_text(encoding="utf-8").splitlines()
            if n.strip() and not n.startswith("#")]


class UserAutoSavePatches(unittest.TestCase):
    def test_series_order(self):
        names = series()
        filt, toggle, test = (names.index(p.name) for p in (FILTER, TOGGLE, TEST))
        self.assertLess(filt, toggle)
        self.assertLess(toggle, test)
        # built on: the macro test, the adaptive interval, the first copy rule, the quick access toolbar, the tab row
        for before in ("hst-macro-save-guard.patch", "hst-adaptive-autorecovery.patch",
                       "hst-recovery-first-copy-registered-modified.patch", "hst-ribbon-adaptive-qat.patch",
                       "hst-ribbon-tabs-fit-row.patch"):
            self.assertLess(names.index(before), filt, before)

    def test_default_on_only_with_the_filter(self):
        root = ET.fromstring(RECOVERY_DEFAULTS.read_text(encoding="utf-8"))
        props = {p.get(OOR + "name"): p.find("value").text for p in root.iter("prop")}
        self.assertEqual(props["UserAutoSaveEnabled"], "true")
        self.assertIn(FILTER.name, series())

    def test_framework_stores_through_the_document(self):
        removed, added = changes(FILTER)["framework/source/services/autorecovery.cxx"]
        self.assertIn("            xDocSave->store();", removed)
        text = "\n".join(added)
        self.assertIn('storeSelf({ comphelper::makePropertyValue(u"HstUserAutoSave"_ustr, true) })', text)
        self.assertIn('getArgs2({ u"HstUserAutoSave"_ustr })', text)
        # session restart / session end clear the global flag: originals stay untouched there
        self.assertIn("(!(m_eJob & Job::SessionSave) || (m_eJob & Job::UserAutoSave))", text)
        self.assertNotIn("->store()", text)

    def test_store_is_silent_and_pauses(self):
        added = "\n".join(changes(FILTER)["sfx2/source/doc/hstuserautosave.cxx"][1])
        self.assertIn("ChangedByOthersRequest", added)
        self.assertIn("State::PausedConflict", added)
        self.assertIn('aHandler.Name = "InteractionHandler"', added)
        model = "\n".join(changes(FILTER)["sfx2/source/doc/sfxbasemodel.cxx"][1])
        self.assertIn("oHstAutoSave->Done(bRet);", model)
        self.assertIn("hst::autosave::ManualSaveDone", model)

    def test_only_safe_formats(self):
        added = "\n".join(changes(FILTER)["sfx2/source/doc/hstuserautosave.cxx"][1])
        names = set(re.findall(r'rName != "([^"]+)"', added))
        self.assertEqual(names, {"MS Word 2007 XML", "Calc MS Excel 2007 XML", "Impress MS PowerPoint 2007 XML"})
        self.assertIn("pFilter->IsOwnFormat() && !pFilter->IsAlienFormat()", added)
        self.assertIn("INetProtocol::File", added)

    def test_every_string_is_translated(self):
        hrc = "\n".join(changes(FILTER)["include/sfx2/strings.hrc"][1])
        ids = dict(re.findall(r'#define (STR_HST_AUTOSAVE\w*)\s+NC_\("\1", "((?:[^"\\]|\\.)*)"\)', hrc))
        self.assertGreaterEqual(len(ids), 17)
        po = "\n".join(changes(FILTER)["translations/source/vi/sfx2/messages.po"][1])
        for key, english in ids.items():
            match = re.search(r'msgctxt "%s"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"' % key, po)
            self.assertIsNotNone(match, key)
            self.assertEqual(match.group(1), english, key)
            self.assertTrue(match.group(2) and match.group(2) != english, key)
        self.assertIn('msgstr "Tự động lưu"', po)
        self.assertIn('msgstr "Hãy lưu tệp trước\\n', po)

    def test_toggle_is_clean_room(self):
        text = "\n".join(changes(TOGGLE)["sfx2/source/notebookbar/HstAutoSaveToggle.cxx"][1])
        for word in ("Microsoft", "Office 365", "OneDrive", ".png", "Image("):
            self.assertNotIn(word, text)

    def test_toggle_cell_before_the_quick_access_toolbar(self):
        added = "\n".join(changes(TOGGLE)["vcl/source/control/tabctrl.cxx"][1])
        self.assertIn('pChild->get_id() == u"hst-autosave-toggle"', added)
        self.assertIn("m_pShortcuts->SetPosPixel(Point(nHstLead, nPosY));", added)
        # the banner's reserves are not part of the cell's computation
        self.assertNotIn("m_nHstPageReserve", added)

    def test_cppunit_target_registered(self):
        test = changes(TEST)
        self.assertIn("    CppunitTest_sfx2_hst_autosave \\", test["sfx2/Module_sfx2.mk"][1])
        self.assertIn("sfx2/qa/cppunit/test_hstautosave.cxx", test)


if __name__ == "__main__":
    unittest.main()
