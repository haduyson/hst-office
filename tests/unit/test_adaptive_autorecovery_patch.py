# SPDX-License-Identifier: AGPL-3.0-only
"""hst-adaptive-autorecovery.patch: AutoRecovery saves every 3 minutes (RecoveryDefaults.xcu); documents
larger than 5 MB wait 10 minutes (never less than the user's own interval). Crash and shutdown saves are unchanged.

Offline: reads the patch hunks per file (defaults, the per-document interval in the timer and in the save
loop, where the size is refreshed) and checks the Options tooltip against its Vietnamese translation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
PATCH = PATCHES / "hst-adaptive-autorecovery.patch"
XCS = "officecfg/registry/schema/org/openoffice/Office/Recovery.xcs"
CXX = "framework/source/services/autorecovery.cxx"
UI = "cui/uiconfig/ui/optsavepage.ui"
PO = "translations/source/vi/cui/messages.po"
RECOVERY_DEFAULTS = ROOT / "extensions/hst-vietnamese-tools/RecoveryDefaults.xcu"


def changes(patch):
    """{path: (removed lines, added lines, hunk lines after the patch)} of a unified diff."""
    out, current = {}, None
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], [], []))
        elif current is None or line.startswith(("@@", "--- a/")):
            continue
        elif line.startswith("-"):
            current[0].append(line[1:])
        elif line.startswith("+"):
            current[1].append(line[1:])
            current[2].append(line[1:])
        elif line.startswith(" "):
            current[2].append(line[1:])
    return out


def prop_default(lines, name):
    """Default <value> of an xcs prop in the patched hunk text."""
    text = "\n".join(lines)
    match = re.search(r'oor:name="%s"(?:(?!</prop>).)*?<value>(\d+)</value>' % name, text, re.S)
    return int(match.group(1)) if match else None


class AdaptiveAutoRecovery(unittest.TestCase):
    def setUp(self):
        self.changes = changes(PATCH)

    def test_touches_only_the_expected_files(self):
        self.assertEqual(set(self.changes), {XCS, CXX, UI, PO})

    def test_defaults(self):
        removed, added, after = self.changes[XCS]
        # The 3-minute interval stays with the bundled extension's RecoveryDefaults.xcu.
        self.assertEqual(removed, [])
        self.assertEqual(prop_default(after, "TimeIntervall"), 10)
        self.assertEqual(prop_default(RECOVERY_DEFAULTS.read_text(encoding="utf-8").splitlines(),
                                      "TimeIntervall"), 3)
        self.assertEqual(prop_default(after, "HstLargeDocumentSize"), 5)
        self.assertEqual(prop_default(after, "HstLargeDocumentTimeIntervall"), 10)
        text = "\n".join(added)
        self.assertIn('<minInclusive oor:value="0">', text)  # 0 switches the rule off

    def test_interval_rule(self):
        added = "\n".join(self.changes[CXX][1])
        self.assertIn("sal_Int64 KnownSize = 0;", added)
        self.assertIn("HstLargeDocumentSize::get()", added)
        self.assertIn("HstLargeDocumentTimeIntervall::get()", added)
        self.assertIn("nLargeMB <= 0 || rInfo.KnownSize <= nLargeMB * sal_Int64(1024 * 1024)", added)
        self.assertIn("return std::max(nNormalMs, nLargeMs);", added)

    def test_timer_and_save_loop_use_the_document_interval(self):
        removed, added, _ = self.changes[CXX]
        added = "\n".join(added)
        self.assertIn("hst_docAutoSaveInterval(docInfo, nConfiguredAutoSaveInterval)", added)
        self.assertIn("nMilliSeconds = std::min(nMilliSeconds, nDocInterval - nDirtyDuration);", added)
        self.assertIn("nDirtyDuration + 999 < hst_docAutoSaveInterval(aInfo, nConfiguredAutoSaveInterval)",
                      added)
        # The check stays inside the timer-only branch: emergency and session saves run with
        # bAllowUserIdleLoop=false and still save large documents at once.
        self.assertNotIn("        if (bAllowUserIdleLoop)", removed)

    def test_size_is_refreshed_on_load_save_and_backup(self):
        added = "\n".join(self.changes[CXX][1])
        self.assertIn("hst_refreshKnownSize(aNew);", added)  # registration
        self.assertIn("hst_refreshKnownSize(aInfo);", added)  # user save
        self.assertIn("hst_refreshKnownSize(rInfo);", added)  # after a recovery backup
        self.assertIn("std::max(hst_localFileSize(rInfo.OrgURL), hst_localFileSize(rInfo.OldTempURL))", added)
        self.assertIn('if (!rURL.startsWithIgnoreAsciiCase("file:"))', added)  # no network stat

    def test_cxx_removes_nothing_but_the_old_timer_lines(self):
        removed = [line.strip() for line in self.changes[CXX][0] if line.strip()]
        for line in removed:
            self.assertTrue("nConfiguredAutoSaveInterval" in line or line == "nMilliSeconds", line)

    def test_tooltip_is_translated(self):
        ui = "\n".join(self.changes[UI][1])
        match = re.search(r'name="tooltip-text" translatable="yes" context="([^"]+)">([^<]+)<', ui)
        self.assertIsNotNone(match)
        context, english = match.groups()
        po = "\n".join(self.changes[PO][1])
        self.assertIn('msgctxt "%s"\nmsgid "%s"' % (context, english), po)
        vietnamese = re.search(r'msgstr "([^"]+)"', po).group(1)
        self.assertEqual(vietnamese, "Tài liệu lớn hơn 5 MB được lưu mỗi 10 phút, hoặc theo khoảng này nếu dài hơn.")
        self.assertIn("5 MB", english)
        self.assertIn("10 minutes", english)

    def test_no_foreign_product_names_in_user_text(self):
        user_text = "\n".join(self.changes[UI][1] + self.changes[PO][1])
        for name in ("Microsoft", "Word", "Excel", "PowerPoint", "LibreOffice"):
            self.assertNotIn(name, user_text)

    def test_series_order(self):
        series = (PATCHES / "series").read_text(encoding="utf-8").split()
        if PATCH.name not in series:
            self.skipTest("hst-adaptive-autorecovery.patch is not in the series yet")
        # Both patches below also edit autorecovery.cxx; this patch is made against their result.
        for earlier in ("hst-language-selection.patch", "hst-document-tabs.patch"):
            self.assertLess(series.index(earlier), series.index(PATCH.name))


if __name__ == "__main__":
    unittest.main()
