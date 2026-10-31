# SPDX-License-Identifier: AGPL-3.0-only
"""NSS records, lossless updates, registration errors and idempotence."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _paths
from hst_office import usb_token_nss as nss

ORIGINAL = ('# existing comment\r\nlibrary=\r\nname=NSS Internal PKCS #11 Module\r\n'
            'parameters=configdir=\'sql:/old\'\r\nNSS=Flags=internal,critical\r\n\r\n'
            'library=/existing path/vendor.so\r\nname=Vendor\r\nNSS=trustOrder=80\r\n\r\n')


class RecordsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name)
        self.path = self.db / "pkcs11.txt"
        self.path.write_bytes(ORIGINAL.encode())

    def test_parse_preserves_values_with_spaces(self):
        records = nss.parse(ORIGINAL)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["library"], "")
        self.assertEqual(records[1]["library"], "/existing path/vendor.so")

    def test_quoted_values_escaped_quotes_backslashes_and_equals(self):
        path = '/path with spaces/back\\slash/"token"=yes.so'
        extra, _ = nss.addition("", '"Tên token"', path)
        self.assertEqual(nss.parse(extra)[0], {"library": path, "name": '"Tên token"'})
        self.assertEqual(nss.addition(extra, "Other label", path)[0], "")

    def test_append_keeps_original_bytes_and_permissions(self):
        self.path.chmod(0o640)
        extra, _ = nss.addition(ORIGINAL, "New", "/new.so")
        nss.append_atomic(self.path, ORIGINAL, extra)
        self.assertTrue(self.path.read_bytes().startswith(ORIGINAL.encode()))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(len(nss.parse(nss.read_text(self.path))), 3)

    def test_missing_final_newline_separates_records(self):
        original = "library=/old.so\nname=Old"
        self.path.write_text(original)
        extra, _ = nss.addition(original, "New", "/new.so")
        nss.append_atomic(self.path, original, extra)
        self.assertEqual(len(nss.parse(nss.read_text(self.path))), 2)

    def test_same_library_different_name_and_symlink_are_idempotent(self):
        library = self.db / "library.so"
        library.touch()
        alias = self.db / "alias.so"
        alias.symlink_to(library)
        extra, _ = nss.addition(ORIGINAL, "Alias", str(alias))
        self.assertEqual(nss.addition(ORIGINAL + extra, "Other", str(library)), ("", "Alias"))

    def test_collision_does_not_remove_old_module(self):
        extra, label = nss.addition(ORIGINAL, "Vendor", "/new.so")
        self.assertEqual(label, "Vendor (2)")
        second, label = nss.addition(ORIGINAL + extra, "Vendor", "/third.so")
        self.assertEqual(label, "Vendor (3)")
        self.assertEqual(len(nss.parse(ORIGINAL + extra + second)), 4)

    def test_newline_nul_control_and_oversize_rejected(self):
        for value in ("line\nname=Injected", "line\r", "nul\x00", "tab\t", "a" * 1001):
            with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                nss.addition(ORIGINAL, value, "/new.so")

    def test_malformed_quotes_and_duplicate_fields_fail_without_write(self):
        for text in ('library="unterminated\n', 'library=/a\nlibrary=/b\n'):
            with self.assertRaises(ValueError):
                nss.addition(text, "new", "/new.so")
        self.assertEqual(self.path.read_bytes(), ORIGINAL.encode())

    def test_concurrent_writer_is_not_overwritten(self):
        self.path.write_text("# changed by another process\n")
        with self.assertRaises(OSError):
            nss.append_atomic(self.path, ORIGINAL, "extra")
        self.assertEqual(self.path.read_text(), "# changed by another process\n")
        self.assertEqual(list(self.db.glob(".hst-pkcs11-*")), [])

    def test_registration_no_tools_twice_changes_only_once(self):
        modules = [{"label": "New", "path": "/new.so"}]
        with patch("hst_office.usb_token_db.user_database"), patch.object(nss, "tool", return_value=None):
            self.assertEqual(nss.register(self.db, modules)[0]["status"], "added")
            content = self.path.read_bytes()
            self.assertEqual(nss.register(self.db, modules)[0]["status"], "existing")
        self.assertEqual(content, self.path.read_bytes())
        self.assertTrue(content.startswith(ORIGINAL.encode()))

    def test_modutil_arguments_and_failures_preserve_db(self):
        (self.db / "cert9.db").touch()
        with patch("hst_office.usb_token_db.user_database"), patch.object(nss, "tool", return_value="/tool"), \
                patch.object(nss, "run_tool", side_effect=OSError("failed")) as run:
            row = nss.register(self.db, [{"label": "Vendor", "path": "/new.so"}])[0]
        self.assertEqual(row["status"], "error")
        run.assert_called_once_with(["/tool", "-add", "Vendor (2)", "-libfile", "/new.so",
                                     "-dbdir", "sql:" + str(self.db), "-force"])
        self.assertEqual(self.path.read_bytes(), ORIGINAL.encode())

    def test_new_file_permissions_private(self):
        self.path.unlink()
        nss.append_atomic(self.path, "", "library=/new.so\nname=New\n\n")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_subprocess_has_no_input_shell_or_inherited_output(self):
        from types import SimpleNamespace
        with patch.object(nss.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            nss.run_tool(["modutil", "-list"])
        args, kwargs = run.call_args
        self.assertEqual(args, (["modutil", "-list"],))
        self.assertEqual(kwargs["stdin"], nss.subprocess.DEVNULL)
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(kwargs["stdout"], nss.subprocess.DEVNULL)

    def test_user_database_rejects_symlink_even_to_owned_file(self):
        from hst_office.usb_token_db import user_database
        self.path.unlink()
        self.path.symlink_to(self.db / "elsewhere")
        with patch("os.geteuid", side_effect=[2000, os.geteuid()]):
            with self.assertRaises(PermissionError):
                user_database(self.db)
