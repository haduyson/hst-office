# SPDX-License-Identifier: AGPL-3.0-only
"""PowerShell template of the Windows updater; update_helper_cmd.build_helper fills it in.

The office starts this script elevated (update_launch.run_elevated) before it closes, then the script waits for the
office to exit, re-checks SHA256, runs msiexec and reopens HST Office through the desktop shell (not elevated)."""

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
# The office writes this marker when its quit was cancelled at a save prompt: this elevated helper cannot be stopped
# by the (unelevated) office, so it stops itself, installs nothing and reopens nothing.
$cancel = Join-Path (Split-Path -Parent $Log) 'update-cancel'
$msiLog = Join-Path (Split-Path -Parent $Log) 'msi-install.log'
# The update folder is private to the user (os.makedirs(mode=0o700) on Windows: owner-only access). This helper runs
# elevated, so what it creates is owned by Administrators and the user's office could not read update.log nor read and
# delete update-result.json at the next start. Grant the folder's owner explicitly; new and existing files inherit it.
try {
    $folder = Split-Path -Parent $Log
    $sid = (New-Object System.Security.Principal.NTAccount((Get-Acl -LiteralPath $folder).Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($sid -ne 'S-1-5-32-544') { & icacls.exe $folder /grant "*${sid}:(OI)(CI)F" /q | Out-Null }
} catch { }
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
$stopped = $false
try {
    Write-Step "Waiting for process $ProcessId"
    $seconds = 0
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        if (Test-Path -LiteralPath $cancel) {
            $stopped = $true
            Remove-Item -LiteralPath $cancel -ErrorAction SilentlyContinue
            throw 'stopped'
        }
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
        Write-Step ('DRYRUN install: msiexec.exe /i "' + $Installer + '" /passive /norestart /l*v "' + $msiLog + '"')
        $code = 0
    } else {
        # This helper already runs elevated: the office asked for administrator rights while it was still the
        # foreground window (update_launch.run_elevated). An elevation requested from here, after the office has
        # closed, is a background request that Windows only shows as a blinking taskbar button.
        Write-Step 'Installing with msiexec'
        try {
            $result = Start-Process msiexec.exe -Wait -PassThru -ArgumentList '/i', "`"$Installer`"", '/passive', '/norestart', '/l*v', "`"$msiLog`""
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
            Write-Step ('Installer could not be started; exit code 1: ' + $_.Exception.Message)
            $code = 1
        }
    }
} catch {
    if (-not $stopped) { Write-Step ('Helper failed; exit code 1: ' + $_.Exception.Message) }
} finally {
    if ($stopped) {
        Write-Step 'Stopped before installing; the office stays open'
    } else {
        if ($code -ne 0 -and $fail -ne 'cancel') { Write-Failure $fail $code }
        # Reopen through the desktop shell, so that HST Office runs with the user's normal rights, not elevated.
        if ($DryRun) {
            Write-Step ('DRYRUN relaunch: explorer.exe "' + $Soffice + '"')
        } elseif (Test-Path -LiteralPath $Soffice) {
            Write-Step 'Relaunching HST Office'
            try { Start-Process explorer.exe -ArgumentList "`"$Soffice`"" | Out-Null }
            catch { Write-Step 'Relaunch failed' }
        } else { Write-Step 'Relaunch unavailable: executable missing' }
    }
}
exit $code
'''
