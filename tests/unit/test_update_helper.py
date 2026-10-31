# SPDX-License-Identifier: AGPL-3.0-only
"""External updater contracts and shell execution with isolated local tool stubs."""
import ast
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from hst_office import update_launch as launch

SHELL_TOOLS = ("sh", "date", "sleep", "nohup", "env", "mktemp", "mkdir", "rmdir", "rm", "mv", "cp", "grep", "sed")
HASH_TOOLS = ("sha256sum", "shasum", "openssl")
SHA256 = hashlib.sha256(b"installer").hexdigest()
HAS_SHELL = os.name == "posix" and Path("/bin/sh").exists() and all(shutil.which(t) for t in SHELL_TOOLS)


def build(system="Linux", **kwargs):
    values = {"pid": 123, "installer": "/tmp/package.deb", "soffice": "/opt/HST Office/program/soffice",
              "log": "/tmp/update.log", "app_dest": "/Applications/HST Office.app", "sha256": SHA256}
    if system == "Windows":
        values.update(installer=r"C:\Downloads\HST Office.msi", soffice=r"C:\HST Office\program\soffice.exe",
                      log=r"C:\Users\Someone\update.log")
    values.update(kwargs)
    return cmd.build_helper(system, **values)


class HelperContract(unittest.TestCase):
    def test_preflight_matrix(self):
        cases = [("Linux", (), "no-installer-tool"), ("Linux", ("pkexec",), "no-installer-tool"),
                 ("Linux", ("apt-get",), "no-installer-tool"), ("Linux", ("pkexec", "apt-get"), None),
                 ("Linux", ("pkcon",), None), ("Windows", (), "no-powershell"),
                 ("Windows", ("powershell",), None), ("Windows", ("powershell.exe",), None)]
        mac = ("hdiutil", "codesign", "spctl", "osascript", "ditto", "open")
        cases.append(("Darwin", mac, None))
        cases.extend(("Darwin", tuple(t for t in mac if t != missing), "no-tools") for missing in mac)
        for system, tools, expected in cases:
            with self.subTest(system=system, tools=tools):
                self.assertEqual(cmd.preflight(system, lambda t: "/bin/" + t if t in tools else None), expected)

    def test_argv_per_os_and_dry_run(self):
        for system in ("Linux", "Darwin", "Windows"):
            helper = build(system, dry_run=True)
            script = r"C:\Private\hst-update.ps1" if system == "Windows" else "/tmp/private/hst-update.sh"
            args = cmd.argv(helper, script)
            self.assertNotIn(cmd.SCRIPT_PATH, args)
            self.assertIn(cmd.SCRIPT_PATH, helper["argv_for"])
            if system == "Windows":
                self.assertEqual(args, ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                        "-WindowStyle", "Hidden", "-File", script, "-ProcessId", "123", "-Installer",
                                        r"C:\Downloads\HST Office.msi", "-Soffice", r"C:\HST Office\program\soffice.exe",
                                        "-Log", r"C:\Users\Someone\update.log", "-Sha256", SHA256, "-DryRun"])
                self.assertEqual((helper["name"], helper["encoding"]), ("hst-update.ps1", "utf-8-sig"))
            else:
                target = "/Applications/HST Office.app" if system == "Darwin" else "/opt/HST Office/program/soffice"
                self.assertEqual(args, ["/bin/sh", script, "123", "/tmp/package.deb", target, "/tmp/update.log", SHA256, "--dry-run"])
                self.assertEqual((helper["name"], helper["encoding"]), ("hst-update.sh", "utf-8"))
            self.assertNotIn(args[-1], cmd.argv(build(system), script))

    def test_windows_script_parameters_and_install(self):
        text = build("Windows", installer=r"C:\a ' $(unsafe)\office.msi")["text"]
        for part in ("param(", "[int]$ProcessId", "[string]$Installer", "[string]$Soffice", "[string]$Log", "[switch]$DryRun",
                     "[Parameter(Mandatory=$true)][string]$Sha256", "Get-FileHash -Algorithm SHA256 -LiteralPath $Installer",
                     "$hash.Hash -ine $Sha256", "SHA256 mismatch", "SHA256 verification failed: installer missing",
                     "Get-Process -Id $ProcessId", "Start-Sleep -Seconds 1", "$seconds -ge 1800", "finally {",
                     "Start-Process msiexec.exe -Verb RunAs -Wait -PassThru", "Start-Process $Soffice",
                     "3010", "UAC was declined", "DRYRUN install:", "DRYRUN relaunch:", "Remove-Item -LiteralPath $Installer"):
            self.assertIn(part, text)
        self.assertIn("-ArgumentList '/i', \"`\"$Installer`\"\", '/passive', '/norestart'", text)
        self.assertNotIn("$(unsafe)", text)
        self.assertLess(text.index("Write-Step 'Process exited'"), text.index("Get-FileHash"))
        self.assertLess(text.index("Get-FileHash"), text.index("if ($DryRun)"))

    def test_sha256_is_required_and_validated(self):
        with self.assertRaises(TypeError):
            cmd.build_helper("Linux", pid=123, installer="/tmp/package.deb", soffice="/opt/soffice", log="/tmp/update.log")
        for system in ("Linux", "Darwin", "Windows"):
            for bad in (None, 123, b"a" * 64, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"):
                with self.subTest(system=system, sha256=bad), self.assertRaisesRegex(ValueError, "sha256"):
                    build(system, sha256=bad)
            self.assertIn("0123456789abcdef" * 4, build(system, sha256="0123456789abcdef" * 4)["argv_for"])

    def test_shell_command_contracts(self):
        linux = build()["text"]
        self.assertIn('pkexec env DEBIAN_FRONTEND=noninteractive apt-get install -y "$INSTALLER"', linux)
        self.assertIn('pkcon install-local "$INSTALLER"', linux)
        self.assertNotIn("pkcon install-local -y", linux)
        for tool in ("zenity", "kdialog", "notify-send", "setsid", "nohup"):
            self.assertIn(tool, linux)
        mac = build("Darwin")["text"]
        for part in ('hdiutil attach -nobrowse -readonly -noverify -mountpoint "$MOUNT" "$INSTALLER"',
                     'codesign --verify --deep --strict "$1"', 'codesign -dv --verbose=4 "$1"',
                     'spctl --assess --type execute "$app"', "TeamIdentifier=" + cmd.TEAM_ID, "swap()",
                     'ditto "$source" "$staged"', '/bin/sh "$0" --swap "$app" "$SOFFICE"',
                     "quoted form of", "with administrator privileges", 'hdiutil detach -force "$MOUNT"'):
            self.assertIn(part, mac)

    def test_invalid_paths_and_parameters(self):
        for system in ("Windows", "Linux", "Darwin"):
            keys = ("installer", "log", "app_dest") if system == "Darwin" else ("installer", "log", "soffice")
            for key in keys:
                for bad in ("relative", "", None, "/tmp/a\0b", "/tmp/a\nb", "/tmp/a\rb", "/tmp/a\tb",
                            "/tmp/a\x1bb", "/tmp/a\x7fb", "/tmp/a\x85b", "/tmp/a\u2028b"):
                    with self.subTest(system=system, key=key, bad=bad), self.assertRaises(ValueError):
                        build(system, **{key: bad})
            with self.assertRaises(ValueError):
                cmd.argv(build(system), "/tmp/bad\nscript")
        for key in ("installer", "app_dest"):
            for bad in ('/tmp/a"b.app', "/tmp/a\\b.app"):
                with self.assertRaises(ValueError):
                    build("Darwin", **{key: bad})
        for bad in ('/tmp/a"b.sh', "/tmp/a\\b.sh"):
            with self.assertRaises(ValueError):
                cmd.argv(build("Darwin"), bad)
        for pid in (0, -1, True, "123", 1.2, 2147483648):
            with self.assertRaises(ValueError):
                build(pid=pid)
        for operation in (lambda: build("Other"), lambda: cmd.preflight("Other"), lambda: build(dry_run="yes")):
            with self.assertRaises(ValueError):
                operation()

    def test_python_38_syntax_and_module_sizes(self):
        for module in (cmd, launch, cmd.scripts):
            source = Path(module.__file__).read_text(encoding="utf-8")
            ast.parse(source, feature_version=(3, 8))
            self.assertLessEqual(len(source.splitlines()), 199)

    @unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
    def test_shell_syntax(self):
        for system in ("Darwin", "Linux"):
            result = subprocess.run(["/bin/sh", "-n"], input=build(system)["text"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class LaunchContract(unittest.TestCase):
    def test_write_modes_and_encoding(self):
        with tempfile.TemporaryDirectory() as root:
            for system in ("Linux", "Darwin", "Windows"):
                directory = Path(root) / system
                helper = build(system)
                path = Path(launch.write_helper(helper, directory))
                self.assertEqual(path.read_text(encoding=helper["encoding"]), helper["text"])
                self.assertEqual(path.read_bytes().startswith(b"\xef\xbb\xbf"), system == "Windows")
                if os.name == "posix":
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600 if system == "Windows" else 0o700)
            self.assertEqual(launch.log_path(root), os.path.join(root, "update.log"))

    def test_spawn_detaches_without_shell(self):
        for system in ("Linux", "Darwin", "Windows"):
            with mock.patch.object(launch.subprocess, "Popen") as popen:
                self.assertIs(launch.spawn(["helper", "some argument"], system), popen.return_value)
                args, options = popen.call_args
                self.assertEqual(args[0], ["helper", "some argument"])
                self.assertIs(options["shell"], False)
                self.assertIs(options["close_fds"], True)
                for stream in ("stdin", "stdout", "stderr"):
                    self.assertEqual(options[stream], subprocess.DEVNULL)
                if system == "Windows":
                    self.assertEqual(options["creationflags"], 0x08000208)
                    self.assertNotIn("start_new_session", options)
                else:
                    self.assertIs(options["start_new_session"], True)

    def test_cancel_exited_running_and_stubborn(self):
        proc = mock.Mock(pid=123)
        proc.poll.return_value = 0
        self.assertFalse(launch.cancel(proc))
        proc.terminate.assert_not_called()
        proc.poll.return_value = None
        for operating_system in ("posix", "nt"):
            proc.reset_mock()
            proc.wait.side_effect = [subprocess.TimeoutExpired("helper", 5), 0]
            with mock.patch.object(launch.os, "name", operating_system), mock.patch.object(launch.os, "killpg", create=True) as killpg:
                self.assertTrue(launch.cancel(proc))
                self.assertEqual(proc.wait.call_args_list, [mock.call(timeout=5), mock.call()])
                if operating_system == "posix":
                    self.assertEqual(killpg.call_args_list, [mock.call(123, signal.SIGTERM), mock.call(123, signal.SIGKILL)])
                else:
                    proc.terminate.assert_called_once_with()
                    proc.kill.assert_called_once_with()

    @unittest.skipUnless(HAS_SHELL, "POSIX process groups required")
    def test_real_spawn_and_cancel(self):
        proc = launch.spawn(["/bin/sh", "-c", "sleep 30"], "Linux")
        try:
            self.assertEqual(os.getpgid(proc.pid), proc.pid)
            self.assertTrue(launch.cancel(proc))
            self.assertIsNotNone(proc.returncode)
            self.assertFalse(launch.cancel(proc))
        finally:
            if proc.poll() is None:
                launch.cancel(proc)


class ShellHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hst-helper's ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Restrict PATH so tests cannot invoke a host package manager or GUI.
        for tool in SHELL_TOOLS + HASH_TOOLS + ("setsid",):
            found = shutil.which(tool)
            if found:
                (self.bin / tool).symlink_to(found)
        self.installer = self.root / "HST installer's package.deb"
        self.installer.write_text("installer", encoding="utf-8")
        self.soffice = self.root / "HST Office" / "program" / "soffice"
        self.destination = self.root / "Applications" / "HST Office.app"
        self.log = self.root / "update.log"
        self.process_vars = dict(os.environ, PATH=str(self.bin), RECORDS=str(self.root), TEAM_ID=cmd.TEAM_ID)
        self.stub(self.soffice, 'printf "relaunched\\n" > "$RECORDS/relaunch"\n')
        with subprocess.Popen(["/bin/sh", "-c", "exit 0"]) as exited:
            exited.wait()
            self.exited_pid = exited.pid

    def stub(self, name, body):
        path = Path(name) if Path(name).is_absolute() else self.bin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o700)

    def prepare(self, system="Linux", **kwargs):
        values = dict(pid=self.exited_pid, installer=str(self.installer), soffice=str(self.soffice),
                      log=str(self.log), app_dest=str(self.destination), sha256=SHA256)
        values.update(kwargs)
        helper = cmd.build_helper(system, **values)
        path = launch.write_helper(helper, self.root / "helper's directory")
        return cmd.argv(helper, path)

    def execute(self, system="Linux", expected=0, **kwargs):
        result = subprocess.run(self.prepare(system, **kwargs), env=self.process_vars, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, self.log.read_text() if self.log.exists() else result.stderr)
        return self.log.read_text(encoding="utf-8")

    def wait_for_file(self, name):
        path = self.root / name
        deadline = time.monotonic() + 3
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), name)
        return path


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class LinuxExecution(ShellHarness):
    def setUp(self):
        super().setUp()
        self.stub("pkexec", 'exec "$@"\n')
        self.stub("apt-get", 'printf "%s\\n" "$@" > "$RECORDS/apt-args"\n'
                  'printf "%s\\n" "$DEBIAN_FRONTEND" > "$RECORDS/frontend"\nexit "${APT_EXIT:-0}"\n')

    def test_success_quotes_logging_and_deletion(self):
        self.installer = self.root / 'installer "double" \'single\' $(touch INJECTED);.deb'
        self.installer.write_bytes(b"installer")
        self.soffice = self.root / 'soffice "double" \'single\' $(touch INJECTED);'
        self.stub(self.soffice, 'printf "relaunched\\n" > "$RECORDS/relaunch"\n')
        self.log.write_text("previous log\n", encoding="utf-8")
        log = self.execute()
        self.assertTrue(log.startswith("previous log\n"))
        self.assertRegex(log, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*Waiting for process")
        self.assertEqual((self.root / "apt-args").read_text().splitlines(), ["install", "-y", str(self.installer)])
        self.assertEqual((self.root / "frontend").read_text().strip(), "noninteractive")
        self.assertIn("Installer exited with code 0", log)
        self.assertFalse(self.installer.exists())
        self.wait_for_file("relaunch")
        self.assertFalse((self.root / "INJECTED").exists())

    def test_dry_run(self):
        log = self.execute(dry_run=True)
        command = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        self.assertEqual(shlex.split(command), ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", str(self.installer)])
        self.assertIn("DRYRUN relaunch:", log)
        self.assertTrue(self.installer.exists())
        self.assertFalse((self.root / "apt-args").exists())
        self.assertFalse((self.root / "relaunch").exists())

    def test_wrong_sha256_skips_both_installers_and_relaunches(self):
        self.stub("pkcon", 'printf "%s\\n" "$@" > "$RECORDS/pkcon-args"\n')
        for package_manager in ("apt-get", "pkcon"):
            with self.subTest(package_manager=package_manager):
                if package_manager == "pkcon":
                    (self.bin / "pkexec").unlink()
                log = self.execute(expected=1, sha256="0" * 64)
                self.assertIn("SHA256 mismatch", log)
                self.assertFalse((self.root / "apt-args").exists())
                self.assertFalse((self.root / "pkcon-args").exists())
                self.assertEqual(self.installer.read_bytes(), b"installer")
                self.wait_for_file("relaunch").unlink()

    def test_dry_run_rejects_wrong_sha256(self):
        log = self.execute(dry_run=True, expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertNotIn("DRYRUN install:", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertFalse((self.root / "relaunch").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")

    def test_missing_installer_relaunches_without_install(self):
        self.installer.unlink()
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: installer missing", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.wait_for_file("relaunch")

    def test_missing_hash_tool_keeps_installer_and_relaunches(self):
        for tool in HASH_TOOLS:
            if (self.bin / tool).exists():
                (self.bin / tool).unlink()
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: no hash tool", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.wait_for_file("relaunch")

    def test_hash_tool_failure_keeps_installer_and_relaunches(self):
        # Even output matching the expected hash cannot hide a hashing error.
        self.stub("sha256sum", 'printf "%s  -\\n" ' + SHA256 + '\nexit 1\n')
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: hash tool failed", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.wait_for_file("relaunch")

    def test_hash_tool_fallbacks(self):
        for tool in HASH_TOOLS:
            with self.subTest(tool=tool):
                if not shutil.which(tool):
                    continue
                for name in HASH_TOOLS:
                    if (self.bin / name).exists():
                        (self.bin / name).unlink()
                (self.bin / tool).symlink_to(shutil.which(tool))
                self.installer.write_bytes(b"installer")
                self.execute()
                self.assertEqual((self.root / "apt-args").read_text().splitlines(), ["install", "-y", str(self.installer)])
                self.assertFalse(self.installer.exists())
                self.wait_for_file("relaunch").unlink()

    def test_installer_changed_while_waiting_is_rejected(self):
        self.stub("sleep", 'printf waiting > "$RECORDS/waiting"\n'
                  'exec ' + shlex.quote(shutil.which("sleep")) + ' "$@"\n')
        child = subprocess.Popen([shutil.which("sleep"), "30"])
        helper = subprocess.Popen(self.prepare(pid=child.pid), env=self.process_vars)
        try:
            self.wait_for_file("waiting")
            self.assertIsNone(helper.poll())
            self.assertFalse((self.root / "apt-args").exists())
            self.installer.write_bytes(b"changed while waiting")
            child.terminate()
            child.wait(timeout=5)
            self.assertEqual(helper.wait(timeout=5), 1)
            self.assertIn("SHA256 mismatch", self.log.read_text())
            self.assertFalse((self.root / "apt-args").exists())
            self.assertEqual(self.installer.read_bytes(), b"changed while waiting")
            self.wait_for_file("relaunch")
        finally:
            for proc in (child, helper):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)

    def test_install_failure_keeps_installer_and_relaunches(self):
        self.process_vars["APT_EXIT"] = "1"
        log = self.execute(expected=1)
        self.assertIn("Installer exited with code 1", log)
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")

    def test_waits_for_process_before_install(self):
        child = subprocess.Popen([shutil.which("sleep"), "2"])
        helper = subprocess.Popen(self.prepare(pid=child.pid), env=self.process_vars)
        start = time.monotonic()
        try:
            time.sleep(0.3)
            self.assertFalse((self.root / "apt-args").exists())
            self.assertIsNone(helper.poll())
            child.wait(timeout=4)
            self.assertEqual(helper.wait(timeout=5), 0)
            self.assertGreaterEqual(time.monotonic() - start, 1.7)
            self.assertTrue((self.root / "apt-args").exists())
            self.wait_for_file("relaunch")
        finally:
            for proc in (child, helper):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)

    def test_wait_timeout_skips_install_and_keeps_installer(self):
        self.stub("sleep", 'exit 0\n')
        log = self.execute(pid=os.getpid(), expected=1)
        self.assertIn("Timed out after 30 minutes; installation skipped", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")

    def test_pkcon_fallback(self):
        (self.bin / "pkexec").unlink()
        self.stub("pkcon", 'printf "%s\\n" "$@" > "$RECORDS/pkcon-args"\n')
        self.execute()
        self.assertEqual((self.root / "pkcon-args").read_text().splitlines(), ["install-local", str(self.installer)])
        self.wait_for_file("relaunch")

    def test_missing_installer_tool(self):
        (self.bin / "pkexec").unlink()
        self.stub("zenity", 'printf "%s\\n" "$@" > "$RECORDS/message"\nexit 1\n')
        log = self.execute(expected=1)
        self.assertIn("install the downloaded package manually", log)
        self.assertTrue((self.root / "message").exists())
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class MacExecution(ShellHarness):
    def setUp(self):
        super().setUp()
        self.destination.mkdir(parents=True)
        (self.destination / "version").write_text("old", encoding="utf-8")
        self.process_vars["APP_NAME"] = "X's app.app"
        self.stub("hdiutil", r'''printf '%s\n' "$@" >> "$RECORDS/hdiutil-args"
case "$1" in
attach)
    [ "${ATTACH_FAIL:-0}" = 0 ] || exit 9
    while [ "$1" != -mountpoint ]; do shift; done
    mkdir -p "$2/$APP_NAME"
    printf new > "$2/$APP_NAME/version"
    [ "${TWO_APPS:-0}" = 0 ] || mkdir "$2/Other.app"
    ;;
detach)
    if [ "$2" = -force ]; then shift; elif [ "${DETACH_RETRY:-0}" = 1 ]; then exit 1; fi
    rm -rf "$2/$APP_NAME" "$2/Other.app"
    ;;
esac
''')
        self.stub("codesign", r'''printf '%s\n' "$@" >> "$RECORDS/codesign-args"
case "$1" in
--verify) exit "${VERIFY_FAIL:-0}" ;;
-dv)
    team=$TEAM_ID
    case "$3" in *.hst-new) team=${STAGED_TEAM:-$team} ;; esac
    printf 'TeamIdentifier=%s\n' "$team" >&2
    exit "${DETAILS_FAIL:-0}"
    ;;
esac
''')
        self.stub("spctl", 'printf "%s\\n" "$@" > "$RECORDS/spctl-args"\nexit "${SPCTL_FAIL:-0}"\n')
        self.stub("ditto", 'printf "%s\\n" "$@" > "$RECORDS/ditto-args"\ncp -R "$1" "$2"\n')
        self.stub("open", 'printf "%s\\n" "$@" > "$RECORDS/open-args"\n')
        self.stub("mv", 'case "$1" in *.hst-new) [ "${FAIL_SWAP:-0}" = 0 ] || exit 1 ;; esac\n'
                  'exec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n')

    def assert_old_reopened(self):
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        self.assertTrue(self.installer.exists())
        self.assertFalse(Path(str(self.destination) + ".hst-new").exists())
        self.assertFalse(Path(str(self.destination) + ".hst-old").exists())
        self.assertIn("detach", (self.root / "hdiutil-args").read_text())

    def test_success_swaps_verifies_detaches_and_opens(self):
        self.process_vars["DETACH_RETRY"] = "1"
        self.execute("Darwin")
        self.assertEqual((self.destination / "version").read_text(), "new")
        self.assertFalse(self.installer.exists())
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        calls = (self.root / "codesign-args").read_text()
        self.assertEqual(calls.count("--verify\n"), 2)
        self.assertIn(str(self.destination) + ".hst-new", calls)
        self.assertIn("-force", (self.root / "hdiutil-args").read_text())
        self.assertFalse(Path(str(self.destination) + ".hst-old").exists())
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_wrong_sha256_never_attaches_and_reopens_old_app(self):
        log = self.execute("Darwin", expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertFalse((self.root / "ditto-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_dry_run_rejects_wrong_sha256_before_attaching(self):
        log = self.execute("Darwin", dry_run=True, expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertNotIn("DRYRUN install:", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertFalse((self.root / "open-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")

    def test_missing_shasum_never_attaches_and_reopens_old_app(self):
        if (self.bin / "shasum").exists():
            (self.bin / "shasum").unlink()
        log = self.execute("Darwin", expected=1)
        self.assertIn("SHA256 verification failed: no hash tool", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])

    def test_team_mismatch_keeps_old_app(self):
        self.process_vars["TEAM_ID"] = cmd.TEAM_ID + "INVALID"
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()
        self.assertFalse((self.root / "ditto-args").exists())

    def test_signature_assessment_and_details_failures(self):
        for failure in ("VERIFY_FAIL", "SPCTL_FAIL", "DETAILS_FAIL", "ATTACH_FAIL", "TWO_APPS"):
            with self.subTest(failure=failure):
                self.process_vars[failure] = "1"
                self.execute("Darwin", expected=1)
                self.assert_old_reopened()
                del self.process_vars[failure]

    def test_staged_team_mismatch_keeps_old_app(self):
        self.process_vars["STAGED_TEAM"] = "WRONG"
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()

    def test_swap_failure_restores_old_app(self):
        self.process_vars["FAIL_SWAP"] = "1"
        log = self.execute("Darwin", expected=1)
        self.assertIn("restoring old app", log)
        self.assert_old_reopened()

    def test_interrupted_swap_restores_old_app(self):
        self.stub("mv", 'case "$1" in *.hst-new) kill -TERM "$PPID"; exit 1 ;; esac\n'
                  'exec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n')
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()

    def test_dry_run_quotes_exact_swap_without_changes(self):
        log = self.execute("Darwin", dry_run=True)
        command = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        args = shlex.split(command)
        self.assertEqual(args[:3], ["/bin/sh", str(self.root / "helper's directory" / "hst-update.sh"), "--swap"])
        self.assertEqual(Path(args[3]).name, self.process_vars["APP_NAME"])
        self.assertEqual(args[4], str(self.destination))
        self.assertIn("DRYRUN relaunch: open " + shlex.quote(str(self.destination)), log)
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertTrue(self.installer.exists())
        self.assertFalse((self.root / "ditto-args").exists())
        self.assertFalse((self.root / "open-args").exists())
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_administrator_command_quoting_and_denial(self):
        # A missing bundle is never writable, even when tests run as root.
        destination = str(self.root / "Absent HST Office's.app")
        log = self.execute("Darwin", dry_run=True, app_dest=destination)
        line = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        args = shlex.split(line)
        self.assertEqual(args[:2], ["osascript", "-e"])
        self.assertEqual(len(args), 3)
        script = str(self.root / "helper's directory" / "hst-update.sh")
        self.assertIn('quoted form of "' + script + '"', args[2])
        self.assertIn('quoted form of "' + destination + '"', args[2])
        self.assertTrue(args[2].endswith('with administrator privileges'))
        self.stub("osascript", 'printf "%s\\n" "$@" > "$RECORDS/osascript-args"\nexit 1\n')
        self.execute("Darwin", expected=1, app_dest=destination)
        request = (self.root / "osascript-args").read_text().splitlines()
        self.assertEqual(request[0], "-e")
        self.assertIn('quoted form of "' + destination + '"', request[1])
        self.assertTrue(self.installer.exists())
        self.assertEqual((self.destination / "version").read_text(), "old")

    def test_failed_restore_retains_and_reopens_backup(self):
        self.stub("mv", 'case "$1" in *.hst-new|*.hst-old) exit 1 ;; esac\n'
                  'exec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n')
        self.execute("Darwin", expected=1)
        backup = Path(str(self.destination) + ".hst-old")
        self.assertEqual((backup / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), ["-a", str(backup)])
        self.assertTrue(self.installer.exists())

    def test_unsafe_discovered_app_is_rejected(self):
        for name in ('X"bad.app', "X\\bad.app", "X\nbad.app", "X\x85bad.app", "X\u2028bad.app"):
            with self.subTest(name=name):
                self.process_vars["APP_NAME"] = name
                self.execute("Darwin", expected=1)
                self.assert_old_reopened()


if __name__ == "__main__":
    unittest.main()
