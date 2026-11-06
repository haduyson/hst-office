# SPDX-License-Identifier: AGPL-3.0-only
"""hst-windows-own-progids.patch: HST Office's own ProgIDs and UNO install-path key next to LibreOffice."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-windows-own-progids.patch"
HST_KEY = r"HASON TECH\HST Office\UNO\InstallPath"


def files():
    """{path: (removed lines, added lines)} of the patch."""
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current[0].append(line[1:])
        elif current is not None and line.startswith("+"):
            current[1].append(line[1:])
    return out


def progids(lines):
    return re.findall(r"(?<!TheDocumentFoundation\.)LibreOffice\.[A-Za-z,]", "\n".join(lines))


class OwnProgIds(unittest.TestCase):
    def test_in_series(self):
        self.assertIn(PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())

    def test_scp2_registers_only_hst_progids(self):
        scp = {p: v for p, v in files().items() if p.startswith("scp2/") and "registryitem_ooo" not in p}
        self.assertIn("scp2/inc/macros.inc", scp)
        for path, (removed, added) in scp.items():
            self.assertTrue(progids(removed), path)
            self.assertEqual(progids(added), [], path)
            self.assertEqual(len(re.findall(r"HSTOffice\.", "\n".join(added))), len(progids(removed)), path)

    def test_app_user_model_ids_unchanged(self):
        for path, (removed, added) in files().items():
            self.assertEqual("\n".join(removed).count("TheDocumentFoundation"), "\n".join(added).count("TheDocumentFoundation"), path)

    def test_install_path_key_is_hst_owned_everywhere(self):
        patched = files()
        for path in ("scp2/source/ooo/registryitem_ooo.scp", "cppuhelper/source/findsofficepath.c",
                     "cli_ure/source/native/native_bootstrap.cxx", "vcl/win/app/fileregistration.cxx"):
            removed, added = patched[path]
            text = "\n".join(added).replace("\\\\", "\\")
            self.assertIn(HST_KEY, text, path)
            self.assertNotIn(r"LibreOffice\UNO", text, path)
            self.assertIn(r"LibreOffice\UNO", "\n".join(removed).replace("\\\\", "\\"), path)

    def test_custom_action_leaves_libreoffice_formats_alone(self):
        removed, added = files()["setup_native/source/win32/customactions/reg4allmsdoc/reg4allmsi.cxx"]
        self.assertNotIn('L"LibreOffice.', "\n".join(added))
        self.assertIn('L"HSTOffice.", 10', "\n".join(added))
        self.assertTrue(any("lostub" in line for line in removed))
        self.assertIn("HSTBackupAssociation", "\n".join(added))


if __name__ == "__main__":
    unittest.main()
