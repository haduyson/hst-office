# SPDX-License-Identifier: AGPL-3.0-only
# Close-crash probe: attach ProcDump to every soffice.bin that starts, so the ORIGINAL fault is written as a full dump
# (with a debugger attached Windows hands the unhandled exception to the debugger before the office's own handler).
# Usage: pwsh -File probe-attach-procdump.ps1 -ProcDump C:\pd\procdump64.exe -Dumps D:\a\_temp\r1-evidence\crash
param(
    [Parameter(Mandatory = $true)][string]$ProcDump,
    [Parameter(Mandatory = $true)][string]$Dumps
)
$seen = @{}
$log = Join-Path $Dumps 'procdump-attach.log'
while ($true) {
    foreach ($p in @(Get-Process -Name soffice.bin -ErrorAction SilentlyContinue)) {
        if ($seen.ContainsKey($p.Id)) { continue }
        $seen[$p.Id] = $true
        "$(Get-Date -Format o) attach $($p.Id)" | Out-File -FilePath $log -Append -Encoding utf8
        $out = Join-Path $Dumps "procdump-$($p.Id).log"
        Start-Process -FilePath $ProcDump -ArgumentList @('-accepteula', '-ma', '-e', '-n', '2', "$($p.Id)", $Dumps) `
            -WindowStyle Hidden -RedirectStandardOutput $out
    }
    Start-Sleep -Milliseconds 150
}
