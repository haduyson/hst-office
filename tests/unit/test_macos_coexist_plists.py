# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/macos/check-coexist-plists.py: HST's bundle declares nothing that clashes with LibreOffice."""
import contextlib
import importlib.util
import io
import plistlib
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_coexist_plists", ROOT / "scripts/macos/check-coexist-plists.py")
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)

ODT = "org.oasis-open.opendocument.text"
LO_FACTORY = "A3FCC88D-B9A6-4364-8B93-92123C8A2D18"


def doc_type(rank, *types):
    return {"CFBundleTypeName": "t", "CFBundleTypeRole": "Editor", "LSHandlerRank": rank, "LSItemContentTypes": list(types)}


def lo_info():
    return {"CFBundleIdentifier": "org.libreoffice.script", "CFBundleName": "LibreOffice", "CFBundleSignature": "LibO",
            "UTExportedTypeDeclarations": [{"UTTypeIdentifier": ODT}], "CFBundleDocumentTypes": [doc_type("Owner", ODT)],
            "CFBundleURLTypes": [{"CFBundleURLSchemes": ["vnd.libreoffice.command", "ms-word"]}]}


def hst_info():
    return {"CFBundleIdentifier": "vn.hasontech.hstoffice", "CFBundleName": "HST Office", "CFBundleSignature": "????",
            "UTImportedTypeDeclarations": [{"UTTypeIdentifier": ODT}], "CFBundleDocumentTypes": [doc_type("Default", ODT)],
            "CFBundleURLTypes": [{"CFBundleURLSchemes": ["ms-word", "ms-excel"]}]}


def make_app(base, name, info, importer_id, factory, profile):
    app = base / f"{name}.app"
    (app / "Contents/Resources").mkdir(parents=True)
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    importer = app / "Contents/Library/Spotlight/OOoSpotlightImporter.mdimporter/Contents"
    importer.mkdir(parents=True)
    (importer / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": importer_id,
                                                         "CFPlugInFactories": {factory: "MetadataImporterPluginFactory"}}))
    (app / "Contents/Resources/bootstraprc").write_text(f"[Bootstrap]\nUserInstallation={profile}\n", encoding="utf-8")
    return MOD.Bundle(app)


class CoexistPlistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.lo = make_app(self.base, "LibreOffice", lo_info(), "org.libreoffice.mdimporter", LO_FACTORY,
                           "$SYSUSERCONFIG/LibreOffice/4")

    def tearDown(self):
        self.tmp.cleanup()

    def hst(self, info=None, importer="vn.hasontech.hstoffice.mdimporter", factory="82F385A2-7B27-450D-9836-EA4DC4E6E9F9",
            profile="$SYSUSERCONFIG/hst%20office/4"):
        self.count = getattr(self, "count", 0) + 1  # each fixture in its own directory
        return make_app(self.base / f"h{self.count}", "HST Office", info or hst_info(), importer, factory, profile)

    def failed(self, hst, lo=None):
        return [message for ok, message in MOD.check(hst, lo) if not ok]

    def test_clean_bundle_passes_alone_and_against_libreoffice(self):
        self.assertEqual(self.failed(self.hst()), [])
        self.assertEqual(self.failed(self.hst(), self.lo), [])

    def test_libreoffice_bundle_fails_every_hst_rule(self):
        failed = " | ".join(self.failed(self.lo))
        for word in ("bundle id", "CFBundleSignature", "exports", "Owner", "URL scheme", "plug-ins", "profile"):
            self.assertIn(word, failed)

    def test_exported_foreign_type_and_owner_rank_fail(self):
        info = hst_info()
        info["UTExportedTypeDeclarations"] = [{"UTTypeIdentifier": ODT}, {"UTTypeIdentifier": "vn.hasontech.hstoffice.x"}]
        info["CFBundleDocumentTypes"] = [doc_type("Owner", ODT)]
        failed = " | ".join(self.failed(self.hst(info), self.lo))
        self.assertIn(f"exports {ODT}", failed)
        self.assertNotIn("vn.hasontech.hstoffice.x", failed)  # HST may export its own types
        self.assertIn(f"Owner of {ODT}", failed)
        self.assertIn(f"no UTI exported by both: {ODT}", failed)

    def test_libreoffice_scheme_and_plugin_clash_fail(self):
        info = hst_info()
        info["CFBundleURLTypes"] = [{"CFBundleURLSchemes": ["ms-word", "vnd.libreoffice.command"]}]
        failed = " | ".join(self.failed(self.hst(info, importer="org.libreoffice.mdimporter", factory=LO_FACTORY), self.lo))
        self.assertIn("no LibreOffice URL scheme: vnd.libreoffice.command", failed)
        self.assertIn("shared URL schemes only from the Office URI set", failed)
        self.assertIn("org.libreoffice.mdimporter", failed)
        self.assertIn(LO_FACTORY, failed)

    def test_same_profile_or_identity_fails(self):
        failed = " | ".join(self.failed(self.hst(profile="$SYSUSERCONFIG/LibreOffice/4"), self.lo))
        self.assertIn("is not LibreOffice's", failed)
        self.assertIn("profiles differ", failed)
        info = hst_info()
        info["CFBundleName"] = "LibreOffice"
        self.assertIn("bundle names differ", " | ".join(self.failed(self.hst(info), self.lo)))

    def test_main_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(MOD.main(["--hst", str(self.hst().app), "--lo", str(self.lo.app)]), 0)
        self.assertIn("PASS no UTI exported by both", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MOD.main(["--hst", str(self.lo.app)]), 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MOD.main(["--hst", str(self.base / "missing.app")]), 2)


if __name__ == "__main__":
    unittest.main()
