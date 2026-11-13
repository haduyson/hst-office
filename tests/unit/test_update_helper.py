# SPDX-License-Identifier: AGPL-3.0-only
"""External updater contracts: argument and script construction, validation and shell syntax."""
import ast
import hashlib
from pathlib import Path
import shutil
import subprocess
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from hst_office import update_launch as launch
from update_helper_harness import HAS_SHELL, SHA256, build


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
                expected = ["/bin/sh", script, "123", "/tmp/package.deb", target, "/tmp/update.log", SHA256, "--dry-run"]
                if system == "Darwin":  # plus the digest of the script itself, checked by the root step
                    expected.append(hashlib.sha256(helper["text"].encode("utf-8")).hexdigest())
                self.assertEqual(args, expected)
                self.assertEqual((helper["name"], helper["encoding"]), ("hst-update.sh", "utf-8"))
            if system == "Darwin":
                self.assertEqual(cmd.argv(build(system), script)[-2], "")
            else:
                self.assertNotIn(args[-1], cmd.argv(build(system), script))

    def test_windows_script_parameters_and_install(self):
        text = build("Windows", installer=r"C:\a ' $(unsafe)\office.msi")["text"]
        for part in ("param(", "[int]$ProcessId", "[string]$Installer", "[string]$Soffice", "[string]$Log", "[switch]$DryRun",
                     "[Parameter(Mandatory=$true)][string]$Sha256", "Get-FileHash -Algorithm SHA256 -LiteralPath $Installer",
                     "$hash.Hash -ine $Sha256", "SHA256 mismatch", "SHA256 verification failed: installer missing",
                     "Get-Process -Id $ProcessId", "Start-Sleep -Seconds 1", "$seconds -ge 1800", "finally {",
                     "Start-Process msiexec.exe -Wait -PassThru", "Start-Process explorer.exe -ArgumentList \"`\"$Soffice`\"\"",
                     "3010", "DRYRUN install:", "DRYRUN relaunch:", "Remove-Item -LiteralPath $Installer",
                     "'update-cancel'", "'msi-install.log'"):
            self.assertIn(part, text)
        self.assertIn("-ArgumentList '/i', \"`\"$Installer`\"\", '/passive', '/norestart', '/l*v', \"`\"$msiLog`\"\"", text)
        # Elevation is requested by the office before it closes (update_launch.run_elevated); one asked for by this
        # hidden helper after the office has gone is only a blinking taskbar button.
        self.assertNotIn("RunAs", text)
        self.assertNotIn("Start-Process $Soffice", text)
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
        from hst_office import update_helper_scripts_windows as windows
        for module in (cmd, launch, cmd.scripts, windows):
            source = Path(module.__file__).read_text(encoding="utf-8")
            ast.parse(source, feature_version=(3, 8))
            self.assertLessEqual(len(source.splitlines()), 199)

    @unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
    def test_shell_syntax(self):
        for system in ("Darwin", "Linux"):
            result = subprocess.run(["/bin/sh", "-n"], input=build(system)["text"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            if shutil.which("shellcheck"):
                result = subprocess.run(["shellcheck", "-s", "sh", "-"], input=build(system)["text"], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
