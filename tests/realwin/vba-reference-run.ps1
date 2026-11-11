# SPDX-License-Identifier: AGPL-3.0-only
# Run the VBA comparison corpus in the installed reference office suite through COM (Application.Run).
# Runs in the console user's session (interactive-task.ps1). Settings are not changed: automation security
# stays at the COM default (low), no Trust Center or VBA project access is needed. It refuses to start when the
# user already has Excel or Word open (COM would attach to the user's instance). Results are saved after every
# call; a watchdog job kills only the Office processes this script started when a call hangs (modal dialog).
param(
    [Parameter(Mandatory = $true)][string]$Corpus,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$HangSec = 120
)
$ErrorActionPreference = 'Stop'
$work = Join-Path (Split-Path $Out) 'reference-work'
$beat = Join-Path (Split-Path $Out) 'reference-heartbeat.txt'
$pidFile = Join-Path (Split-Path $Out) 'reference-pids.txt'
New-Item -ItemType Directory -Force $work | Out-Null
$manifest = Get-Content (Join-Path $Corpus 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$sessionId = (Get-Process -Id $PID).SessionId
$report = [ordered]@{ suite = 'reference'; computer = $env:COMPUTERNAME; started = (Get-Date).ToString('s'); files = @() }

function Save-Report { $report | ConvertTo-Json -Depth 8 | Set-Content -Path $Out -Encoding UTF8 }
function Beat([string]$what) {
    for ($i = 0; $i -lt 20; $i++) {  # the watchdog may be reading the file
        try { Set-Content -Path $beat -Value "$([DateTime]::UtcNow.Ticks)|$what" -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 100 }
    }
}

$existing = Get-Process EXCEL, WINWORD -ErrorAction SilentlyContinue | Where-Object SessionId -eq $sessionId
if ($existing) { $report.error = 'user has Excel or Word open; not attaching'; Save-Report; exit 3 }
Remove-Item $pidFile -ErrorAction SilentlyContinue

$watchdog = Start-Job -ArgumentList $beat, $pidFile, $HangSec -ScriptBlock {
    param($beat, $pidFile, $hang)
    while ($true) {
        Start-Sleep -Seconds 5
        if (-not (Test-Path $beat)) { continue }
        $text = Get-Content $beat -Raw -ErrorAction SilentlyContinue
        if (-not $text) { continue }
        $ticks, $what = $text.Trim().Split('|', 2)
        if ($what -eq 'idle') { continue }
        if (([DateTime]::UtcNow.Ticks - [long]$ticks) / 1e7 -gt $hang -and (Test-Path $pidFile)) {
            foreach ($id in Get-Content $pidFile) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
            Set-Content -Path $beat -Value "$([DateTime]::UtcNow.Ticks)|killed:$what"
        }
    }
}

function Start-App([string]$progId, [string]$processName) {
    $before = @(Get-Process $processName -ErrorAction SilentlyContinue | ForEach-Object Id)
    $app = New-Object -ComObject $progId
    $new = Get-Process $processName -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id -and $_.SessionId -eq $sessionId }
    $new | ForEach-Object { Add-Content -Path $pidFile -Value $_.Id }
    # Another suite can register itself under the same CLSID in the user's 64-bit class view (seen: WPS Office);
    # run this script from 32-bit PowerShell and verify the server. A foreign server may be the user's own
    # running instance: release it without Quit.
    if ($app.Path -notlike '*\Microsoft Office\*') {
        $path = $app.Path
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
        throw "COM $progId resolved to '$path', not Microsoft Office"
    }
    $app.Visible = $false
    $app.DisplayAlerts = 0
    return $app
}

$apps = @{}
function Get-App([string]$hostName) {
    if (-not $apps[$hostName]) {
        $apps[$hostName] = if ($hostName -eq 'excel') { Start-App 'Excel.Application' 'EXCEL' } else { Start-App 'Word.Application' 'WINWORD' }
        $report["version_$hostName"] = $apps[$hostName].Version + ' build ' + $apps[$hostName].Build + ' at ' + $apps[$hostName].Path
    }
    return $apps[$hostName]
}
function Reset-App([string]$hostName) {
    # Word: never write the user's Normal template; quit without saving anything.
    if ($hostName -eq 'word') { try { $apps[$hostName].NormalTemplate.Saved = $true; $apps[$hostName].Quit(0) } catch {} }
    else { try { $apps[$hostName].Quit() } catch {} }
    $apps[$hostName] = $null
}

function Open-Doc($app, [string]$hostName, [string]$path) {
    if ($hostName -eq 'excel') { return $app.Workbooks.Open($path, 0, $false) }
    return $app.Documents.Open($path, $false, $false, $false)
}
function Close-Doc($doc, [string]$hostName) {
    if ($hostName -eq 'excel') { $doc.Close($false) } else { $doc.Close(0) }
}

# Binary variants first: the reference suite's own Save As of the generated macro files.
if ([IntPtr]::Size -ne 4) { $report.error = 'run from 32-bit PowerShell (SysWOW64)'; Save-Report; exit 4 }
foreach ($entry in $manifest | Where-Object derive_from) {
    $target = Join-Path $Corpus $entry.file
    if (Test-Path $target) { continue }
    try {
        Beat "derive $($entry.file)"
        $app = Get-App $entry.host
        $source = Join-Path $work ('derive-' + $entry.derive_from)
        Copy-Item (Join-Path $Corpus $entry.derive_from) $source -Force
        # Macros off for this automation session only, so open events do not write into the saved copy.
        $app.AutomationSecurity = 3
        try {
            $doc = Open-Doc $app $entry.host $source
            $doc.SaveAs([string]$target, [int]$entry.save_format)
            Close-Doc $doc $entry.host
        } finally { $app.AutomationSecurity = 1 }
    } catch { $report.files += [ordered]@{ file = $entry.file; status = 'derive-failed'; error = "$_" }; Reset-App $entry.host }
}

foreach ($entry in $manifest) {
    $row = [ordered]@{ file = $entry.file; host = $entry.host; status = 'not-run'; functions = [ordered]@{} }
    $report.files += $row
    $source = Join-Path $Corpus $entry.file
    if (-not (Test-Path $source)) { $row.status = 'missing'; Save-Report; continue }
    $copy = Join-Path $work $entry.file
    Copy-Item $source $copy -Force
    try {
        Beat "open $($entry.file)"
        $app = Get-App $entry.host
        $doc = Open-Doc $app $entry.host $copy
        # Automation skips Excel's Auto_Open, which a user's double click runs. Word's RunAutoMacro(wdAutoOpen)
        # fires Document_Open a second time instead of AutoOpen, so Word AutoOpen stays unmeasured here.
        if ($entry.events -and $entry.host -eq 'excel') { $doc.RunAutoMacros(1) }
        $row.status = 'opened'
        foreach ($name in $entry.functions) {
            Beat "run $($entry.file) $name"
            $macro = if ($entry.host -eq 'excel') { "'$($entry.file)'!Cases.$name" } else { "Cases.$name" }
            try {
                $value = $app.Run($macro)
                $row.functions[$name] = [ordered]@{ status = 'ok'; value = [string]$value }
            } catch {
                $row.functions[$name] = [ordered]@{ status = 'error'; value = "$($_.Exception.Message)" }
                if ((Get-Content $beat -Raw -ErrorAction SilentlyContinue) -like '*killed:*') { throw "hung and killed during $name" }
            }
            Save-Report
        }
        Beat 'close'
        Close-Doc $doc $entry.host
        $row.status = 'done'
    } catch {
        $row.status = 'failed'; $row.error = "$_"
        Reset-App $entry.host
    }
    Save-Report
}
Beat 'idle'
foreach ($key in @($apps.Keys)) { Reset-App $key }
Start-Sleep -Seconds 3
if (Test-Path $pidFile) { foreach ($id in Get-Content $pidFile) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue } }
Stop-Job $watchdog; Remove-Job $watchdog -Force
$report.finished = (Get-Date).ToString('s')
Save-Report
exit 0
