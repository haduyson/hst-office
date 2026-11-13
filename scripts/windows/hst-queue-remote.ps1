# SPDX-License-Identifier: AGPL-3.0-only
<#
Windows side of the local build queue (scripts/build-queue-dispatcher.py), run over SSH through
tests/realwin/remote.py <host> ps. Prints one JSON line as its result.
  -Action Deploy                         copy D:\hst-test\hst-build-tools\scripts\* to <ToolsRoot>\tools\scripts\
  -Action Probe  -Root R                 {"busy": <build.lock held or a queue task running on R>, free space, memory}
  -Action Start  -Root R -Job q-... -Ref <sha> -Jobs N [-Modules a,b]
                                         hst4-detach.ps1 task hst-build-<Job> running hst4-build.ps1 -OutName <Job>
  -Action Status -Root R -Job q-...      {"state": running|done|failed, "out": R\out\<Job>, "log": task log tail}
  -Action Cancel -Root R -Job q-...      stops the task and its process tree (only processes of that task)
  -Action Cleanup -Root R -Job q-...     deletes R\out\<Job> after the dispatcher pulled it
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Deploy', 'Probe', 'Start', 'Status', 'Cancel', 'Cleanup')][string]$Action,
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$Root = 'D:\hst-build',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$ToolsRoot = 'D:\hst-build',
    [ValidatePattern('^q-[0-9a-f-]{6,40}$')][string]$Job = '',
    [ValidatePattern('^[0-9a-f]{40}$')][string]$Ref = '',
    [ValidateRange(1, 64)][int]$Jobs = 28,
    [ValidatePattern('^$|^[A-Za-z0-9][A-Za-z0-9_.+-]*(,[A-Za-z0-9][A-Za-z0-9_.+-]*)*$')][string]$Modules = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Scripts = Join-Path $ToolsRoot 'tools\scripts'
$Task = "hst-build-$Job"

function Out-Json($Object) { $Object | ConvertTo-Json -Compress -Depth 4 }
function Need-Job { if (-not $Job) { throw "-Job is required for -Action $Action" } }

function Test-LockHeld {
    $path = Join-Path $Root 'build.lock'
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try { $f = [IO.File]::Open($path, 'Open', 'ReadWrite', 'None'); $f.Dispose(); return $false } catch { return $true }
}

function Get-TaskProcessTree {
    # The runner powershell started by the task, then every descendant (bash, make, cl, link, ...).
    $all = @(Get-CimInstance Win32_Process)
    $roots = @($all | Where-Object { $_.CommandLine -and $_.CommandLine -like "*\tasks\$Task.ps1*" })
    $ids = [Collections.Generic.List[int]]::new()
    $queue = [Collections.Generic.Queue[int]]::new()
    foreach ($r in $roots) { $queue.Enqueue([int]$r.ProcessId) }
    while ($queue.Count -gt 0) {
        $id = $queue.Dequeue()
        if ($ids.Contains($id)) { continue }
        $ids.Add($id)
        foreach ($c in $all | Where-Object { $_.ParentProcessId -eq $id }) { $queue.Enqueue([int]$c.ProcessId) }
    }
    , $ids
}

function Get-LogTail([int]$Lines = 60) {
    $log = Join-Path $Root "logs\task-$Job.log"
    if (Test-Path -LiteralPath $log) { (Get-Content -LiteralPath $log -Tail $Lines) -join "`n" } else { '' }
}

switch ($Action) {
    'Deploy' {
        $src = 'D:\hst-test\hst-build-tools\scripts'
        if (-not (Test-Path -LiteralPath $src)) { throw "nothing staged at $src" }
        New-Item -ItemType Directory -Force -Path $Scripts | Out-Null
        Copy-Item -Recurse -Force -Path "$src\*" -Destination $Scripts
        Remove-Item -Recurse -Force -LiteralPath $src
        Out-Json @{ deployed = $true; scripts = $Scripts }
    }
    'Probe' {
        $queueTask = @(Get-ScheduledTask -TaskName 'hst-build-q-*' -ErrorAction SilentlyContinue | Where-Object {
                $_.State -eq 'Running' -and ($_.Actions.Arguments -join ' ') -match [regex]::Escape($Root) })
        $os = Get-CimInstance Win32_OperatingSystem
        $drive = Get-PSDrive $Root.Substring(0, 1)
        Out-Json @{ busy = ((Test-LockHeld) -or $queueTask.Count -gt 0); root = $Root
            free_gib = [math]::Round($drive.Free / 1GB, 1); c_free_gib = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
            mem_free_gib = [math]::Round($os.FreePhysicalMemory / 1MB, 1) }
    }
    'Start' {
        Need-Job
        if (-not $Ref) { throw '-Ref (full sha) is required' }
        if (Test-LockHeld) { Out-Json @{ started = $false; reason = "$Root\build.lock is held" }; break }
        New-Item -ItemType Directory -Force -Path $Root | Out-Null
        $scriptArgs = "-Ref $Ref -Root $Root -ToolsRoot $ToolsRoot -Jobs $Jobs -OutName $Job"
        if ($Modules) { $scriptArgs += " -Modules $Modules" }
        $msg = & (Join-Path $Scripts 'windows\hst4-detach.ps1') -Name $Job -Root $Root `
            -Script (Join-Path $Scripts 'windows\hst4-build.ps1') -ScriptArgs $scriptArgs
        Out-Json @{ started = $true; task = $Task; message = "$msg" }
    }
    'Status' {
        Need-Job
        $t = Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        $log = Join-Path $Root "logs\task-$Job.log"
        $ended = (Test-Path -LiteralPath $log) -and (Select-String -LiteralPath $log -Pattern "end $Task rc=" -Quiet)
        if ($t -and -not $ended) { Out-Json @{ state = 'running'; task = "$($t.State)" }; break }
        $out = Join-Path $Root "out\$Job"
        $info = $null
        $statusFile = Join-Path $Root 'status.json'
        if (Test-Path -LiteralPath $statusFile) { $info = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json }
        $ok = $ended -and (Select-String -LiteralPath $log -Pattern "end $Task rc=0" -Quiet) -and
            $info -and $info.state -eq 'done' -and $info.out -eq $out -and (Test-Path -LiteralPath $out)
        $err = if ($ok) { '' } elseif ($info -and $info.PSObject.Properties['error']) { "$($info.error)" } elseif (-not $ended) { 'task vanished' } else { 'build failed' }
        Out-Json @{ state = $(if ($ok) { 'done' } else { 'failed' }); out = $out; error = $err; log = (Get-LogTail) + "`n" }
    }
    'Cancel' {
        Need-Job
        $ids = Get-TaskProcessTree
        foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
        if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
        }
        "[$(Get-Date -Format s)] end $Task rc=130 (cancelled)" | Out-File -LiteralPath (Join-Path $Root "logs\task-$Job.log") -Append -Encoding utf8
        Out-Json @{ cancelled = $true; killed = $ids.Count }
    }
    'Cleanup' {
        Need-Job
        $out = Join-Path $Root "out\$Job"
        if (Test-Path -LiteralPath $out) { cmd.exe /c rd /s /q "$out" | Out-Null }
        Out-Json @{ removed = -not (Test-Path -LiteralPath $out) }
    }
}
