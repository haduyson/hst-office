# SPDX-License-Identifier: AGPL-3.0-only
# Crash evidence for the Windows runtime checks: attach ProcDump to every soffice.bin that starts, so an unhandled
# fault is written as a full dump at the ORIGINAL fault. With a debugger attached Windows hands the exception to the
# debugger before the office's own crash handler, which on a close crash faults again and exits with 255 without a
# Windows Error Reporting dump. print-office-crashes.ps1 reads the dumps.
# Usage: pwsh -File attach-procdump.ps1 -Dumps D:\a\_temp\r1-evidence\crash
#   downloads ProcDump (Microsoft-signed), starts this script again as a hidden watcher and prints its process id;
# pwsh -File attach-procdump.ps1 -Dumps <dir> -Stop [-Watcher <id>]: stops that watcher and every ProcDump (the
# dumps stay); nothing to stop is not an error.
param(
    [Parameter(Mandatory = $true)][string]$Dumps,
    [string]$ProcDump = '',
    [switch]$Stop,
    [int]$Watcher = 0
)
if ($Stop) {
    if ($Watcher) { Stop-Process -Id $Watcher -Force -ErrorAction SilentlyContinue }
    Get-Process procdump64 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    exit 0
}
$ErrorActionPreference = 'Stop'
if (-not $ProcDump) {
    $pd = Join-Path $env:RUNNER_TEMP 'procdump'
    Invoke-WebRequest https://download.sysinternals.com/files/Procdump.zip -OutFile "$pd.zip"
    Expand-Archive "$pd.zip" -DestinationPath $pd -Force
    $exe = Join-Path $pd 'procdump64.exe'
    $signature = Get-AuthenticodeSignature $exe
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        throw "procdump64.exe: unexpected signature $($signature.Status) $($signature.SignerCertificate.Subject)"
    }
    New-Item -ItemType Directory -Force -Path $Dumps | Out-Null
    $watcher = Start-Process pwsh -ArgumentList @('-NoProfile', '-File', $PSCommandPath, '-Dumps', $Dumps, '-ProcDump', $exe) `
        -WindowStyle Hidden -PassThru
    $watcher.Id
    exit 0
}
$seen = @{}
$log = Join-Path $Dumps 'procdump-attach.log'
while ($true) {
    foreach ($p in @(Get-Process -Name soffice.bin -ErrorAction SilentlyContinue)) {
        if ($seen.ContainsKey($p.Id)) { continue }
        $seen[$p.Id] = $true
        "$(Get-Date -Format o) attach $($p.Id)" | Out-File -FilePath $log -Append -Encoding utf8
        $out = Join-Path $Dumps "procdump-$($p.Id).log"
        # -e: unhandled exceptions only; -n 2: the fault and, if the crash handler faults as well, that one too
        Start-Process -FilePath $ProcDump -ArgumentList @('-accepteula', '-ma', '-e', '-n', '2', "$($p.Id)", $Dumps) `
            -WindowStyle Hidden -RedirectStandardOutput $out
    }
    Start-Sleep -Milliseconds 150
}
