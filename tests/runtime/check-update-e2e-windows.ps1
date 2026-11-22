# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# "Cập nhật ngay" end to end on a Windows test PC (TEST ONLY: replaces the installed HST Office).
#   -Phase install  -OldMsi <msi> -NewMsi <msi>      (SSH session, elevated) remove HST Office, install <OldMsi> silently,
#                                                    put <NewMsi> into the console user's update cache
#   -Phase drive    -Out <dir> [-DriveArgs '...']    (console user's session) update-e2e-drive.py with the office's own
#                                                    Python: start it with a document, dispatch the update command
#   -Phase collect  -Out <dir>                       (SSH session) installed version, update.log, msi log, processes
# The NewMsi must be the installer the published manifest names (or pass -DriveArgs '--installer <path> --to <release>').
param(
    [Parameter(Mandatory = $true)][ValidateSet('install', 'drive', 'collect')][string]$Phase,
    [string]$OldMsi, [string]$NewMsi, [string]$Out = 'C:\hst-test\update-e2e', [string]$DriveArgs = '',
    [string]$User = 'kiemtra'
)
$ErrorActionPreference = 'Stop'
$cache = "C:\Users\$User\AppData\Local\HSTOffice\update"
function Get-HstProducts {
    Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -like 'HST Office*' }
}
function Get-InstallDir {
    foreach ($p in 'C:\Program Files\HST Office', 'C:\Program Files\HSTOffice') { if (Test-Path "$p\program\soffice.exe") { return $p } }
    throw 'HST Office program folder not found'
}
New-Item -ItemType Directory -Force -Path $Out | Out-Null
switch ($Phase) {
    'install' {
        Get-Process soffice*, msiexec -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'soffice*' } | Stop-Process -Force
        foreach ($product in @(Get-HstProducts)) {
            $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList '/x', $product.PSChildName, '/qn', '/norestart'
            "removed $($product.DisplayName) $($product.DisplayVersion): $($p.ExitCode)"
        }
        $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList '/i', "`"$OldMsi`"", '/qn', '/norestart', '/l*v', "`"$Out\old-install.log`""
        "installed old: exit $($p.ExitCode); now: $((Get-HstProducts).DisplayVersion -join ',')"
        Remove-Item -Recurse -Force $cache -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $cache | Out-Null
        Copy-Item -LiteralPath $NewMsi -Destination $cache
        Remove-Item -Recurse -Force "$Out\profile" -ErrorAction SilentlyContinue
        & icacls.exe $Out /grant "${User}:(OI)(CI)F" /q | Out-Null
        & icacls.exe $cache /grant "${User}:(OI)(CI)F" /q | Out-Null
        "cache: $((Get-ChildItem $cache).Name -join ',')"
    }
    'drive' {
        $dir = Get-InstallDir
        $doc = "$Out\probe.rtf"
        Set-Content -LiteralPath $doc -Encoding ASCII -Value '{\rtf1\ansi HST update probe\par}'
        $python = "$dir\program\python.exe"
        $driver = Join-Path $PSScriptRoot 'update-e2e-drive.py'
        $arguments = @($driver, '--soffice', "$dir\program\soffice.exe", '--profile', "$Out\profile", '--document', $doc,
                       '--out', "$Out\report.json") + ($DriveArgs -split ' ' | Where-Object { $_ })
        & $python @arguments *> "$Out\drive.log"
        "driver exit $LASTEXITCODE"
    }
    'collect' {
        "installed: $((Get-HstProducts | ForEach-Object { $_.DisplayName + ' ' + $_.DisplayVersion }) -join ', ')"
        foreach ($name in 'update.log', 'update-result.json', 'update-pending.json') {
            if (Test-Path "$cache\$name") { "--- $name"; Get-Content "$cache\$name" -Tail 25 }
        }
        "--- office processes"
        Get-CimInstance Win32_Process -Filter "Name like 'soffice%'" | ForEach-Object { "$($_.ProcessId) $($_.CommandLine)" }
        if (Test-Path "$Out\report.json") { "--- report"; Get-Content "$Out\report.json" -Raw }
    }
}
