# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke diagnostics: print every soffice.bin crash of this runner session, the Application log entry
# (faulting module, offset, exception code) and, when the Windows SDK debugger is present, the crashing thread's stack
# from each minidump that Windows Error Reporting wrote into -Dumps (LocalDumps key set by the workflow).
# Usage: pwsh -File print-office-crashes.ps1 -Install "C:\Program Files\HSTOffice" -Dumps D:\a\_temp\out\crash
param(
    [Parameter(Mandatory = $true)][string]$Install,
    [Parameter(Mandatory = $true)][string]$Dumps
)
$ErrorActionPreference = 'Continue'

$events = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000, 1001, 1026 } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'soffice' })
"$($events.Count) Application log event(s) about soffice"
foreach ($e in $events) {
    "--- $($e.TimeCreated.ToString('o')) id $($e.Id) $($e.ProviderName)"
    $e.Message
}

$files = @(Get-ChildItem -LiteralPath $Dumps -Filter '*.dmp' -ErrorAction SilentlyContinue)
"$($files.Count) minidump(s) in $Dumps"
$cdb = @(
    "${env:ProgramFiles(x86)}\Windows Kits\10\Debuggers\x64\cdb.exe",
    "$env:ProgramFiles\Windows Kits\10\Debuggers\x64\cdb.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($files.Count -and -not $cdb) { 'cdb.exe not found: stacks not printed (the dumps are in the evidence artifact)' }
foreach ($f in $files) {
    "=== $($f.Name) ($($f.Length) bytes)"
    if (-not $cdb) { continue }
    # Microsoft's symbols for the system DLLs; the office's own DLLs resolve to their exported names only.
    $symbols = "srv*$env:RUNNER_TEMP\symbols*https://msdl.microsoft.com/download/symbols;$Install\program"
    $stack = @(& $cdb -z $f.FullName -y $symbols -i "$Install\program" -c '.ecxr; .exr -1; kn 60; lm o; q' 2>&1 |
        Where-Object { $_ -notmatch '^\s*$' } | Select-Object -First 400)
    $stack
    # A fault the office's own handler caught (it then aborts from inside the handler) shows up as a nested
    # exception: the original fault's CONTEXT record lies at the Child-SP of the KiUserExceptionDispatch frame.
    # Print that context's registers, the code around the faulting instruction and the call sites of the next
    # frames, so the faulting function can be identified from its disassembly without the office's PDBs.
    $frames = @($stack | Select-String -Pattern '^\s*([0-9a-f]{2})\s+([0-9a-f`]+)\s+([0-9a-f`]+)\s+(\S+)')
    $dispatch = $frames | Where-Object { $_.Matches[0].Groups[4].Value -like 'ntdll!KiUserExceptionDispatch*' } | Select-Object -First 1
    if ($dispatch) {
        $index = [array]::IndexOf($frames, $dispatch)
        $commands = @(".cxr $($dispatch.Matches[0].Groups[2].Value)", 'r', 'ub @rip L40', 'u @rip L12')
        # the return addresses of the faulting frame and the four frames above it: their call instructions
        $last = [Math]::Min($index + 5, $frames.Count - 1)
        foreach ($frame in $(if ($last -gt $index) { $frames[($index + 1)..$last] } else { @() })) {
            $commands += "ub $($frame.Matches[0].Groups[3].Value) L12"
        }
        "--- original fault context (.cxr at the KiUserExceptionDispatch frame)"
        & $cdb -z $f.FullName -y $symbols -i "$Install\program" -c (($commands + 'q') -join '; ') 2>&1 |
            Where-Object { $_ -notmatch '^\s*$' } | Select-Object -First 400
    }
}
