# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

from _paths import ROOT
from banner_fixtures import KEY
from hst_office.banner_verify import valid_key


class ReleaseGateTests(unittest.TestCase):
    def test_package_key_is_inspected_without_executing_source(self):
        with patch.object(sys, "path", [str(Path(ROOT) / "scripts")] + sys.path):
            import extension_contract as contract
            for expression, expected in [('b""', b""), ('bytes.fromhex("' + KEY.hex() + '")', KEY),
                                         ('b"\\x01" + bytes(31)', None), ('__import__("os").abort()', None)]:
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w") as archive:
                    archive.writestr("python/hst_office/banner_verify.py", "PUBLIC_KEY = " + expression)
                with zipfile.ZipFile(stream) as archive:
                    if expected is None:
                        with self.assertRaises(ValueError):
                            contract.banner_key(archive)
                    else:
                        self.assertEqual(contract.banner_key(archive), expected)
                        self.assertEqual(valid_key(expected), bool(expected))

    def test_release_gate_rejects_placeholder_and_accepts_generated_key(self):
        with patch.object(sys, "path", [str(Path(ROOT) / "scripts")] + sys.path):
            spec = importlib.util.spec_from_file_location("extension_check", Path(ROOT) / "scripts/check-extensions.py")
            checker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(checker)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("placeholder", b"")
        with patch.object(checker, "check_zip", return_value=set()), patch.object(checker, "check_registration"), \
                patch.object(checker, "check_content"), patch.object(checker, "check_labels"), \
                patch.object(checker, "check_banners"), patch.object(checker, "banner_key", return_value=b"") as key:
            self.assertEqual(checker.check_oxt(stream), [])
            self.assertIn("release requires", checker.check_oxt(stream, True)[0])
            key.return_value = KEY
            self.assertEqual(checker.check_oxt(stream, True), [])
