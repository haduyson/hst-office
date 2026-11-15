# SPDX-License-Identifier: AGPL-3.0-only
<#
Regression check (Windows): the first start of a new profile must not run the OpenCL self-test.

Usage (the console user's session, or SSH; no window interaction is needed):
    powershell -File check-first-start-no-opencl.ps1 -Program <instdir>\program -Profile <empty dir> [-Wait 25]
        [-KeepUseOpenCL]

Upstream Desktop::CheckOpenCLCompute ran on the main thread of a new profile's first start: opencltest.exe, then
share\opencl\cl-test.ods loaded hidden and computed with OpenCL kernels. A driver fault inside it ended the office
with the restart code and no trace (error reports HSTO-000010/11). hst-no-startup-opencl-test.patch removes the call.

By default the profile is seeded with UseOpenCL=true (as Expert Configuration or an administrator could set it), so
the check proves the patch and not only the UseOpenCL=false default; -KeepUseOpenCL leaves the build's default.
FAIL when, during the first start, opencltest.exe runs, a soffice.bin of this profile loads OpenCL.dll, or the
profile gets a SelectedOpenCLDeviceIdentifier (the test's stored result). Exit 1 on FAIL.
Only processes of this profile are stopped at the end.
#>
param([Parameter(Mandatory)][string]$Program, [Parameter(Mandatory)][string]$Profile, [int]$Wait = 25,
      [switch]$KeepUseOpenCL)
$ErrorActionPreference = 'Stop'
$Program = (Resolve-Path $Program).Path
New-Item -ItemType Directory -Force "$Profile\user" | Out-Null
$Profile = (Resolve-Path $Profile).Path
if (-not $KeepUseOpenCL) {
    Set-Content -Encoding UTF8 "$Profile\user\registrymodifications.xcu" @'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="UseOpenCL" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
'@
}
$url = 'file:///' + ($Profile -replace '\\', '/')
$t0 = Get-Date
function Log($m) { Write-Output ("+{0,5:N1}s {1}" -f ((Get-Date) - $t0).TotalSeconds, $m) }
function Mine {
    Get-CimInstance Win32_Process -Filter "Name='soffice.bin' OR Name='soffice.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($url) }
}
$failures = @()
Start-Process "$Program\soffice.exe" -ArgumentList "-env:UserInstallation=$url"
Log "started soffice.exe with $url (UseOpenCL seeded: $(-not $KeepUseOpenCL))"
$end = (Get-Date).AddSeconds($Wait + 10)  # + the first-start restart
$seen = @{}
while ((Get-Date) -lt $end) {
    foreach ($t in @(Get-Process opencltest -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Program\*" })) {
        if (-not $seen["t$($t.Id)"]) { $seen["t$($t.Id)"] = 1; $failures += "opencltest.exe ran (pid $($t.Id))"; Log "opencltest.exe pid $($t.Id)" }
    }
    foreach ($w in @(Mine | Where-Object { $_.Name -eq 'soffice.bin' })) {
        try {
            $p = Get-Process -Id $w.ProcessId -ErrorAction Stop
            if ($p.Modules | Where-Object { $_.ModuleName -ieq 'OpenCL.dll' }) {
                if (-not $seen["m$($w.ProcessId)"]) { $seen["m$($w.ProcessId)"] = 1; $failures += "soffice.bin $($w.ProcessId) loaded OpenCL.dll"; Log "OpenCL.dll in soffice.bin $($w.ProcessId)" }
            }
        } catch { }
    }
    Start-Sleep -Milliseconds 100
}
$bins = @(Mine)
Log "office processes of this profile still running: $($bins.Count)"
if (-not ($bins | Where-Object { $_.Name -eq 'soffice.bin' })) { $failures += "the office did not stay up" }
foreach ($b in $bins) { Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2
$reg = Get-Content "$Profile\user\registrymodifications.xcu" -Raw -ErrorAction SilentlyContinue
if ($reg -match 'SelectedOpenCLDeviceIdentifier') { $failures += "the profile stored an OpenCL test result (SelectedOpenCLDeviceIdentifier)" }
if ($failures.Count) { $failures | ForEach-Object { Write-Output "FAIL $_" }; exit 1 }
Write-Output "PASS first start without the OpenCL self-test"
exit 0
