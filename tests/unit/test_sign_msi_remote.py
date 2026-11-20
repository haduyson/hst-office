# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/windows/sign-msi-remote.py: the server side of the Windows signing step."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sign_msi_remote", ROOT / "scripts/windows/sign-msi-remote.py")
remote = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(remote)
NAME = "HSTOffice_1.0.2_Win_x86-64_en-US_vi.msi"


class Recorder:
    def __init__(self, returncode=0):
        self.calls, self.returncode = [], returncode

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[0] == "scp" and not args[-1].startswith("kiemtra@"):
            target = Path(args[-1])  # a pull: create the file scp would have copied
            (target / Path(args[-2].split(":", 1)[1]).name).write_bytes(b"signed")
        return subprocess.CompletedProcess(args, self.returncode)


class Paths(unittest.TestCase):
    def test_writes_stay_in_the_test_folders(self):
        for path in ("C:\\hst-test\\sign", "D:\\hst-test", "c:\\HST-TEST\\sign\\signed"):
            self.assertTrue(remote.inside_root(path), path)
        for path in ("C:\\Users\\kiemtra", "C:\\hst-test-other", "C:\\hst-test\\..\\Windows", "hst-test\\sign", "C:\\"):
            self.assertFalse(remote.inside_root(path), path)

    def test_only_installer_names(self):
        self.assertEqual(remote.checked_name(f"/tmp/x/{NAME}"), NAME)
        self.assertEqual(remote.checked_name(f"C:\\hst-test\\sign\\{NAME}"), NAME)
        for bad in ("evil.msi", "HSTOffice_1.0.2_Win_x86-64_en-US_vi.msi.exe", 'HSTOffice_1"&calc_Win_x86-64_en-US_vi.msi'):
            with self.assertRaises(ValueError):
                remote.checked_name(bad)

    def test_bad_host_or_folder_is_refused(self):
        with self.assertRaises(ValueError):
            remote.Remote("kiemtra@pc; rm -rf /", None, remote.DEFAULT_DIR)
        with self.assertRaises(ValueError):
            remote.Remote("kiemtra@pc", None, "C:\\Windows\\Temp")


class Commands(unittest.TestCase):
    def test_desktop_command_signs_into_signed_with_the_same_name(self):
        command = remote.sign_command("C:\\hst-test\\sign", NAME)
        self.assertIn(f'-Msi "C:\\hst-test\\sign\\{NAME}"', command)
        self.assertIn(f'-OutMsi "C:\\hst-test\\sign\\signed\\{NAME}"', command)
        self.assertNotIn("-Thumbprint", command)
        chosen = remote.sign_command("C:\\hst-test\\sign", NAME, "AB" * 20, "http://tsa.example.vn/tsa")
        self.assertIn("-Thumbprint " + "AB" * 20, chosen)
        self.assertIn("-TimestampUrl http://tsa.example.vn/tsa", chosen)

    def test_cmd_file_is_crlf_and_pauses(self):
        text = remote.cmd_file("C:\\hst-test\\sign", NAME)
        self.assertTrue(text.startswith("@echo off\r\n"))
        self.assertIn("\r\npause\r\n", text)
        text.encode("ascii")

    def test_verify_needs_no_certificate(self):
        command = remote.verify_command("C:\\hst-test\\sign", NAME)
        self.assertIn("-VerifyOnly", command)
        self.assertIn(f"signed\\{NAME}", command)

    def test_sha256_line_matches_sha256sum_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / NAME
            path.write_bytes(b"msi")
            self.assertEqual(remote.sha256_line(path), f"{hashlib.sha256(b'msi').hexdigest()}  {NAME}\n")


class Transfers(unittest.TestCase):
    def test_push_copies_msi_scripts_and_cmd_then_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            msi = Path(tmp) / NAME
            msi.write_bytes(b"msi")
            run = Recorder()
            remote.Remote("kiemtra@pc", "/k", remote.DEFAULT_DIR, run).push(msi, temp_dir=tmp)
            self.assertEqual(run.calls[0][0], "ssh")
            self.assertIn("mkdir", run.calls[0][-1])
            scp = run.calls[1]
            self.assertEqual(scp[-1], "kiemtra@pc:C:/hst-test/sign/")
            self.assertIn(str(msi), scp)
            for script in remote.SCRIPTS:
                self.assertTrue(any(arg.endswith(script) for arg in scp), script)
            self.assertTrue(any(arg.endswith(f"sign-{msi.stem}.cmd") for arg in scp))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [NAME])

    def test_push_refuses_a_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            remote.Remote("kiemtra@pc", None, remote.DEFAULT_DIR, Recorder()).push(Path(tmp) / NAME, temp_dir=tmp)

    def test_pull_fetches_msi_and_log_and_writes_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Recorder()
            remote.Remote("kiemtra@pc", None, remote.DEFAULT_DIR, run).pull(NAME, tmp)
            sources = [call[-2] for call in run.calls]
            self.assertEqual(sources, [f"kiemtra@pc:C:/hst-test/sign/signed/{NAME}",
                                       f"kiemtra@pc:C:/hst-test/sign/signed/{Path(NAME).stem}.sign.log"])
            self.assertEqual((Path(tmp) / f"{NAME}.sha256").read_text(), remote.sha256_line(Path(tmp) / NAME))

    def test_verify_returns_the_remote_exit_code(self):
        run = Recorder(returncode=1)
        self.assertEqual(remote.Remote("kiemtra@pc", None, remote.DEFAULT_DIR, run).verify(NAME), 1)
        self.assertIn("-VerifyOnly", run.calls[0][-1])

    def test_main_rejects_a_bad_thumbprint(self):
        with self.assertRaises(SystemExit):
            remote.main(["--host", "kiemtra@pc", "push", NAME, "--thumbprint", "xyz"])


if __name__ == "__main__":
    unittest.main()
