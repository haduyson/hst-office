# SPDX-License-Identifier: AGPL-3.0-only
"""Pure construction and validation of the external updater's scripts and arguments."""
import hashlib
import ntpath
import os
import re
import shlex
import shutil
import unicodedata

from . import update_helper_scripts as scripts
from . import update_helper_scripts_mac as mac_scripts

TEAM_ID = "74AT34P945"
SCRIPT_PATH = "{script}"

POWERSHELL = r'''# SPDX-License-Identifier: AGPL-3.0-only
param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$Soffice,
    [Parameter(Mandatory=$true)][string]$Log,
    [Parameter(Mandatory=$true)][string]$Sha256,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
function Write-Step([string]$Message) {
    Add-Content -LiteralPath $Log -Encoding UTF8 -Value ((Get-Date -Format o) + ' ' + $Message)
}
$state = Join-Path (Split-Path -Parent $Log) 'update-result.json'
# The start-up job shows this once (update_outcome.py); it stays on this machine.
function Write-Failure([string]$Reason, [int]$ExitCode) {
    try {
        $json = @{schema=1; code=$Reason; exit=$ExitCode; from='@FROM_RELEASE@'; to='@TO_RELEASE@'} | ConvertTo-Json -Compress
        Set-Content -LiteralPath "$state.tmp" -Encoding ASCII -Value $json
        Move-Item -LiteralPath "$state.tmp" -Destination $state -Force
        Write-Step ("Recorded failure: $Reason ($ExitCode)")
    } catch { Write-Step 'Failure not recorded' }
}
$code = 1
$fail = 'wait'
try {
    Write-Step "Waiting for process $ProcessId"
    $seconds = 0
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        if ($seconds -ge 1800) {
            Write-Step 'Timed out after 30 minutes; installation skipped'
            throw 'wait-timeout'
        }
        Start-Sleep -Seconds 1
        $seconds++
    }
    Write-Step 'Process exited'
    Remove-Item -LiteralPath $state -ErrorAction SilentlyContinue
    $fail = 'verify'
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
        throw 'SHA256 verification failed: installer missing'
    }
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Installer
    if ($hash.Hash -ine $Sha256) { throw 'SHA256 mismatch; installation skipped' }
    $fail = 'install'
    if ($DryRun) {
        Write-Step ('DRYRUN install: msiexec.exe /i "' + $Installer + '" /passive /norestart')
        $code = 0
    } else {
        Write-Step 'Installing with msiexec'
        try {
            $result = Start-Process msiexec.exe -Verb RunAs -Wait -PassThru -ArgumentList '/i', "`"$Installer`"", '/passive', '/norestart'
            Write-Step ("Installer exited with code " + $result.ExitCode)
            if ($result.ExitCode -eq 0 -or $result.ExitCode -eq 3010) {
                $code = 0
                Remove-Item -LiteralPath $Installer
                Write-Step 'Deleted installer'
            } else {
                $code = $result.ExitCode
                if ($code -eq 1602) { $fail = 'cancel' }  # the installer's own Cancel button
            }
        } catch {
            # Start-Process only fails here when the UAC question is declined: the user's choice.
            Write-Step 'Installer failed or UAC was declined; exit code 1'
            $code = 1
            $fail = 'cancel'
        }
    }
} catch {
    Write-Step ('Helper failed; exit code 1: ' + $_.Exception.Message)
} finally {
    if ($code -ne 0 -and $fail -ne 'cancel') { Write-Failure $fail $code }
    if ($DryRun) {
        Write-Step ('DRYRUN relaunch: Start-Process "' + $Soffice + '"')
    } elseif (Test-Path -LiteralPath $Soffice) {
        Write-Step 'Relaunching HST Office'
        try { Start-Process $Soffice | Out-Null }
        catch { Write-Step 'Relaunch failed' }
    } else { Write-Step 'Relaunch unavailable: executable missing' }
}
exit $code
'''


def preflight(system, which=shutil.which):
    """Return the missing-tool error, or None when installation is available."""
    if system == "Linux":
        return None if (which("pkexec") and which("apt-get")) or which("pkcon") else "no-installer-tool"
    if system == "Windows":
        return None if which("powershell.exe") or which("powershell") else "no-powershell"
    if system == "Darwin":
        return None if all(which(t) for t in ("hdiutil", "codesign", "spctl", "osascript", "ditto", "open")) else "no-tools"
    raise ValueError("unsupported system")


def _path(value, windows=False, applescript=False):
    try:
        value = os.fspath(value)
    except TypeError:
        raise ValueError("path must be an absolute text path") from None
    if not isinstance(value, str) or not value or any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in value):
        raise ValueError("path must be nonempty text without control characters")
    if not (ntpath if windows else os.path).isabs(value):
        raise ValueError("path must be absolute")
    if applescript and ('"' in value or "\\" in value):
        raise ValueError("AppleScript paths cannot contain double quotes or backslashes")
    return value


def mac_swap():
    """MAC_SWAP with the team and the C1 / line-separator path patterns filled in (updater and start-up move)."""
    controls = "|".join("*" + shlex.quote(chr(c)) + "*" for c in tuple(range(128, 160)) + (0x2028, 0x2029))
    return mac_scripts.MAC_SWAP.replace("@TEAM_ID@", TEAM_ID).replace("@PATH_CONTROLS@", controls)


def mac_path(value):
    """A macOS helper path: absolute, no control characters, and safe inside the AppleScript administrator command."""
    return _path(value, applescript=True)


def mac_bundle(value):
    target = mac_path(value).rstrip("/")
    if not target.endswith(".app"):
        raise ValueError("app_dest must name an .app bundle")
    return target


def build_helper(system, *, pid, installer, soffice, log, sha256, dry_run=False, app_dest=None, release_from="", release_to="",
                 app_origin=None):
    """Build a script and argv template without inspecting or changing the filesystem.

    release_from / release_to go into the failure record, so that update_outcome can name the version and ignore a
    record made stale by an update installed some other way. macOS: app_dest is the bundle to replace or create;
    app_origin, when it differs (the running copy on a .dmg, say), is reopened if the install fails."""
    if system not in ("Windows", "Darwin", "Linux"):
        raise ValueError("unsupported system")
    if type(pid) is not int or pid <= 0 or pid > 2147483647:
        raise ValueError("pid must be a positive process ID")
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be a bool")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    for release in (release_from, release_to):
        if not isinstance(release, str) or not re.fullmatch(r"[0-9A-Za-z.+~-]{0,64}", release):
            raise ValueError("release must be a version text")
    installer = _path(installer, system == "Windows", system == "Darwin")
    log = _path(log, system == "Windows")
    origin = ""
    if system == "Darwin":
        target = mac_bundle(app_dest)
        origin = "" if app_origin is None else mac_bundle(app_origin)
    else:
        target = _path(soffice, system == "Windows")
    if system == "Windows":
        arguments = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                     "-WindowStyle", "Hidden", "-File", SCRIPT_PATH, "-ProcessId", str(pid),
                     "-Installer", installer, "-Soffice", target, "-Log", log, "-Sha256", sha256]
        text = POWERSHELL.replace("@FROM_RELEASE@", release_from).replace("@TO_RELEASE@", release_to)
        return {"name": "hst-update.ps1", "text": text, "encoding": "utf-8-sig",
                "argv_for": arguments + (["-DryRun"] if dry_run else [])}
    arguments = ["/bin/sh", SCRIPT_PATH, str(pid), installer, target, log, sha256]
    relaunch = "open " + shlex.quote(target) if system == "Darwin" else "nohup " + shlex.quote(target) + " >/dev/null 2>&1 &"
    text = scripts.HEADER
    if system == "Darwin":
        text += mac_swap()
    text += scripts.SETUP + "FROM_RELEASE=" + shlex.quote(release_from) + "\nTO_RELEASE=" + shlex.quote(release_to) + "\n"
    text += "RELAUNCH=" + shlex.quote(relaunch) + "\n" + ("ORIGIN=" + shlex.quote(origin) + "\nSCRIPT_SHA256=${7-}\n" if system == "Darwin" else "")
    text += "HASH_TOOLS=" + shlex.quote("shasum" if system == "Darwin" else "sha256sum shasum openssl") + "\n"
    if system == "Linux":
        text += "APT_COMMAND=" + shlex.quote("pkexec env DEBIAN_FRONTEND=noninteractive apt-get install -y " + shlex.quote(installer)) + "\n"
        text += "PKCON_COMMAND=" + shlex.quote("pkcon install-local " + shlex.quote(installer)) + "\n"
    text += mac_scripts.MAC_INSTALL if system == "Darwin" else scripts.LINUX
    text += scripts.RUN
    # macOS: the root step runs only a copy of the script with this digest (admin_command).
    extra = ["--dry-run" if dry_run else "", hashlib.sha256(text.encode("utf-8")).hexdigest()] if system == "Darwin" else ["--dry-run"] * dry_run
    return {"name": "hst-update.sh", "text": text, "encoding": "utf-8", "argv_for": arguments + extra}


def argv(helper, script_path):
    """Substitute the validated script path, preserving each argument verbatim."""
    path = _path(script_path, helper["encoding"] == "utf-8-sig", "quoted form of" in helper["text"])
    return [path if item == SCRIPT_PATH else item for item in helper["argv_for"]]
