# SPDX-License-Identifier: AGPL-3.0-only
"""Shared fixtures of the external updater tests: argument builder and a shell harness with isolated tool stubs.

Not a test module itself (no test_ prefix): test_update_helper*.py, test_update_outcome.py and test_mac_app_location.py
import it."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest

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


class MacHarness(ShellHarness):
    """ShellHarness plus stubs of the macOS tools (hdiutil, codesign, spctl, xattr, ditto, open, mv) and an old app.

    STAGED_VERIFY_FAIL, STAGED_TEAM and STAGED_SPCTL_FAIL make only the checks of the staged copy (*.hst-new) fail."""

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
--verify)
    case "$4" in *.hst-new) exit "${STAGED_VERIFY_FAIL:-${VERIFY_FAIL:-0}}" ;; esac
    exit "${VERIFY_FAIL:-0}" ;;
-dv)
    team=$TEAM_ID
    case "$3" in *.hst-new) team=${STAGED_TEAM:-$team} ;; esac
    printf 'TeamIdentifier=%s\n' "$team" >&2
    exit "${DETAILS_FAIL:-0}"
    ;;
esac
''')
        self.stub("spctl", 'printf "%s\\n" "$@" >> "$RECORDS/spctl-args"\n'
                  'case "$4" in *.hst-new) exit "${STAGED_SPCTL_FAIL:-0}" ;; esac\nexit "${SPCTL_FAIL:-0}"\n')
        self.stub("xattr", 'printf "%s\\n" "$@" >> "$RECORDS/xattr-args"\n')
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


# Stands in for osascript: evaluates the `do shell script ("..." & quoted form of "..." & ...)` command the helpers
# build (as the current user, not root) and records `display notification` texts, so the root step runs for real.
OSASCRIPT = r'''import os, re, shlex, subprocess, sys
script = sys.argv[sys.argv.index("-e") + 1]
records = os.environ["RECORDS"]
if script.startswith("display notification"):
    with open(os.path.join(records, "notifications"), "a") as handle:
        handle.write(script + "\n")
    sys.exit(0)
with open(os.path.join(records, "osascript-args"), "w") as handle:
    handle.write(script)
body = re.fullmatch(r'do shell script \((.*)\) with administrator privileges', script, re.S).group(1)
parts = re.findall(r'(quoted form of )?"((?:[^"\\]|\\.)*)"', body)
command = ""
for quoted, text in parts:
    text = re.sub(r'\\(.)', r'\1', text)
    command += shlex.quote(text) if quoted else text
done = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
sys.stdout.write(done.stdout)
if done.returncode:
    sys.stderr.write("execution error: %s (%d)\n" % (done.stderr.strip(), done.returncode))
    sys.exit(1)
'''


def stub_osascript(harness):
    """Install the OSASCRIPT stand-in into a ShellHarness's private bin folder."""
    runner = harness.root / "osascript.py"
    runner.write_text(OSASCRIPT, encoding="utf-8")
    harness.stub("osascript", "exec %s %s \"$@\"\n" % (shlex.quote(shutil.which("python3")), shlex.quote(str(runner))))
