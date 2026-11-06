# SPDX-License-Identifier: AGPL-3.0-only
"""hst-own-policy-paths.patch: HST Office reads Windows policies from its own key; from the old upstream key only the
update-lock subtree of beta.4 and earlier still applies. The templates, the guide and the Windows smoke test follow
(the website copy of the guide is synced at release time by website/office.hasontech.vn/scripts/sync-help.py).
The patched logic itself runs against an in-memory registry in tests/runtime/check-winreg-policy.sh."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-own-policy-paths.patch"
HST_KEY = r"SOFTWARE\Policies\HASON TECH\HST Office"
OLD_KEY = r"SOFTWARE\Policies\LibreOffice"
TEMPLATES = ROOT / "extensions/hst-vietnamese-tools/help/files"


def hunks():
    """{path: (removed lines, added lines)} of the patch, C++ escapes folded (\\\\ -> \\)."""
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current[0].append(line[1:].replace("\\\\", "\\"))
        elif current is not None and line.startswith("+"):
            current[1].append(line[1:].replace("\\\\", "\\"))
    return out


class OwnPolicyKey(unittest.TestCase):
    def test_appended_after_the_committed_series(self):
        series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, series)
        self.assertGreater(series.index(PATCH.name), series.index("hst-windows-own-progids.patch"))

    def test_policy_layers_read_the_hst_key(self):
        removed, added = hunks()["configmgr/source/winreg.cxx"]
        code = [line for line in added if not line.lstrip().startswith("//")]
        self.assertIn('constexpr wchar_t HST_POLICY_KEY[] = L"%s";' % HST_KEY, code)
        self.assertTrue(any('L"%s"' % OLD_KEY in line for line in removed))
        # the old key is read only through LEGACY_POLICY_KEY, and only its HSTUpdate subtree
        old = [line for line in code if "LibreOffice" in line]
        self.assertEqual(old, ['constexpr wchar_t LEGACY_POLICY_KEY[] = L"%s";' % OLD_KEY])
        self.assertIn('constexpr OUString LEGACY_SUBTREE = u"org.openoffice.Office.HSTUpdate"_ustr;', code)
        self.assertIn("        dumpWindowsRegistryKey(eType, aLegacyKey.h, LEGACY_SUBTREE, aFileHandle);", code)
        self.assertTrue(any("!hasSubKey(aKey.h, LEGACY_SUBTREE)" in line for line in code))

    def test_same_vendor_key_as_the_msi(self):
        msi = (ROOT / "patches/libreoffice/hst-windows-own-progids.patch").read_text(encoding="utf-8")
        self.assertIn(r'"Software\\HASON TECH\\HST Office\\UNO\\InstallPath"', msi)
        self.assertTrue(HST_KEY.startswith(r"SOFTWARE\Policies\HASON TECH\HST Office"))

    def test_mail_client_setting_is_hst_owned(self):
        removed, added = hunks()["shell/source/win32/simplemail/smplmailclient.cxx"]
        self.assertTrue(any(r"Software\LibreOffice\SendAsEMailClient" in line for line in removed))
        self.assertTrue(any(r"Software\HASON TECH\HST Office\SendAsEMailClient" in line for line in added))
        self.assertFalse(any("LibreOffice" in line for line in added))


class Templates(unittest.TestCase):
    def reg_files(self):
        return sorted(TEMPLATES.glob("*.reg"))

    def test_reg_templates_write_only_the_hst_key(self):
        files = self.reg_files()
        self.assertEqual(len(files), 4)
        for path in files:
            text = path.read_bytes().decode("ascii")
            keys = [line.strip("[]-") for line in text.splitlines() if line.startswith("[")]
            self.assertTrue(keys, path)
            for key in keys:
                self.assertTrue(key.startswith("HKEY_LOCAL_MACHINE\\" + HST_KEY + "\\org.openoffice.Office.HSTUpdate"), (path, key))
            self.assertNotIn("LibreOffice", text, path)

    def test_unlock_leaves_an_empty_key_that_hides_the_old_lock(self):
        lines = [line for line in (TEMPLATES / "hst-office-go-khoa.reg").read_bytes().decode("ascii").splitlines() if line]
        key = "HKEY_LOCAL_MACHINE\\%s\\org.openoffice.Office.HSTUpdate" % HST_KEY
        self.assertEqual(lines[1:], ["[-%s]" % key, "[%s]" % key])

    def test_guide_names_the_hst_key_and_the_transition(self):
        text = (ROOT / "extensions/hst-vietnamese-tools/help/cap-nhat.html").read_text(encoding="utf-8")
        self.assertIn("<code>HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\HASON TECH\\HST Office</code>", text)
        self.assertIn("1.0.0-beta.4 trở về trước", text)
        self.assertNotIn("LibreOffice", text)


class WindowsSmoke(unittest.TestCase):
    def test_policy_scenario_uses_the_hst_key_and_checks_the_old_one(self):
        text = (ROOT / ".github/workflows/windows-smoke.yml").read_text(encoding="utf-8")
        self.assertIn(r"key='HKLM\SOFTWARE\Policies\HASON TECH\HST Office\org.openoffice.Office.HSTUpdate'", text)
        self.assertIn(r"old='HKLM\SOFTWARE\Policies\LibreOffice'", text)
        self.assertIn(r'lock "$old\org.openoffice.Office.Common\Misc\ShowTipOfTheDay" false', text)
        self.assertIn(r'lock "$old\org.openoffice.Office.HSTUpdate\AllowInstall" false', text)
        self.assertIn("probe chi-tai-ve --label old-key-update-lock", text)
        self.assertIn('--ignored "$foreign"', text)
        self.assertNotIn(r"Policies\LibreOffice\org.openoffice.Office.HSTUpdate'", text)


if __name__ == "__main__":
    unittest.main()
