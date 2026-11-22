# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
<#
Windows side of the local build queue (scripts/build-queue-dispatcher.py), run over SSH through
tests/realwin/remote.py <host> ps. Prints one JSON line as its result.
  -Action Deploy                         copy D:\hst-test\hst-build-tools\scripts\* to <ToolsRoot>\tools\scripts\
  -Action Probe  -Root R                 {"busy": <build.lock held or a queue task running on R>, free space, memory}
  -Action Start  -Root R -Job q-... -Ref <sha> -Jobs N [-Modules a,b]
                                         hst4-detach.ps1 task hst-build-<Job> running hst4-build.ps1 -OutName <Job>
  -Action Status -Root R -Job q-...      {"state": running|done|failed, "out": R\out\<Job>, "log": task log tail}
  -Action Cancel -Root R -Job q-...      stops the task and its whole process tree: the task's descendants plus every
                                         process left whose command line names R (a compiler whose parent already
                                         died), in repeated passes so nothing started meanwhile survives; never the
                                         host-wide mspdbsrv. Then deletes the damaged object files the killed
                                         compilers left in R\lo\workdir since the task started (else the next link
                                         fails with LNK1136 "invalid or corrupt file")
  -Action Clean -Root R [-Full]          idle slot only (refused while build.lock is held or a queue task runs on R):
                                         deletes every damaged object file of R\lo\workdir; -Full deletes
                                         R\lo\workdir and R\lo\instdir (the next build there is a full build)
  -Action Cleanup -Root R -Job q-...     deletes R\out\<Job> after the dispatcher pulled it
  -Action DiskReport [-Top N]            free space of C:/D: and the largest folders under D:\hst-test (size, newest
                                         file, owner tag from the folder's .hst-owner file); read only, deletes nothing
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Deploy', 'Probe', 'Start', 'Status', 'Cancel', 'Cleanup', 'Clean', 'DiskReport')][string]$Action,
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$Root = 'D:\hst-build',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$ToolsRoot = 'D:\hst-build',
    [ValidatePattern('^q-[0-9a-f-]{6,40}$')][string]$Job = '',
    [ValidatePattern('^[0-9a-f]{40}$')][string]$Ref = '',
    [ValidateRange(1, 64)][int]$Jobs = 28,
    [ValidateRange(1, 50)][int]$Top = 15,
    [ValidatePattern('^$|^[A-Za-z0-9][A-Za-z0-9_.+-]*(,[A-Za-z0-9][A-Za-z0-9_.+-]*)*$')][string]$Modules = '',
    [switch]$Full
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

function Get-TaskProcessTree([int[]]$ExtraRoots = @()) {
    # The runner powershell started by the task (plus $ExtraRoots), then every descendant (bash, make, cl, link, ...).
    $all = @(Get-CimInstance Win32_Process)
    $roots = @($all | Where-Object { $_.CommandLine -and $_.CommandLine -like "*\tasks\$Task.ps1*" })
    $ids = [Collections.Generic.List[int]]::new()
    $queue = [Collections.Generic.Queue[int]]::new()
    foreach ($r in $roots) { $queue.Enqueue([int]$r.ProcessId) }
    foreach ($r in $ExtraRoots) { $queue.Enqueue($r) }
    while ($queue.Count -gt 0) {
        $id = $queue.Dequeue()
        if ($ids.Contains($id)) { continue }
        $ids.Add($id)
        # A child is younger than its parent: an older process whose dead parent's id was reused is not a child.
        $born = ($all | Where-Object { $_.ProcessId -eq $id } | Select-Object -First 1).CreationDate
        foreach ($c in $all | Where-Object { $_.ParentProcessId -eq $id -and (-not $born -or $_.CreationDate -ge $born) }) {
            $queue.Enqueue([int]$c.ProcessId)
        }
    }
    , $ids
}

function Test-QueueTaskRunning {
    @(Get-ScheduledTask -TaskName 'hst-build-q-*' -ErrorAction SilentlyContinue | Where-Object {
            $_.State -eq 'Running' -and ($_.Actions.Arguments -join ' ') -match [regex]::Escape("$Root\tasks\") }).Count -gt 0   # not a prefix of another root
}

function Get-SlotProcesses {
    # Processes whose command line names a path inside this slot, in any of the spellings the build uses
    # (D:\hst-build-s2\..., D:/hst-build-s2/..., /cygdrive/d/hst-build-s2/...). The trailing separator keeps
    # D:\hst-build from matching D:\hst-build-s2, and keeps out the helper calls themselves (-Root "D:\hst-build").
    # mspdbsrv serves every build on the host and ends by itself when idle: never killed here.
    # Each form is built in its own statement: in an array literal `a, b + c` adds to the array, not to b (which
    # once yielded the form "/" and matched every process).
    $base = $Root.TrimEnd('\')
    $slash = $base.Replace('\', '/')
    $cygwin = '/cygdrive/' + $base.Substring(0, 1).ToLowerInvariant() + $slash.Substring(2)
    $forms = @("$base\", "$slash/", "$cygwin/")
    if ($base.Length -lt 4 -or $forms.Count -ne 3 -or @($forms | Where-Object { $_.Length -lt 6 }).Count -gt 0) {
        throw "refusing to match processes on the slot path forms '$($forms -join "', '")'"
    }
    @(Get-CimInstance Win32_Process | Where-Object {
            $cl = $_.CommandLine
            $cl -and $_.ProcessId -ne $PID -and $_.Name -ne 'mspdbsrv.exe' -and
            @($forms | Where-Object { $cl.IndexOf($_, [StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count -gt 0
        } | ForEach-Object { [int]$_.ProcessId })
}

function Stop-SlotBuild {
    # Several passes: make and bash start new processes while their siblings are being stopped.
    $killed = [Collections.Generic.HashSet[int]]::new()
    for ($pass = 0; $pass -lt 5; $pass++) {
        $found = [Collections.Generic.HashSet[int]]::new()
        # Processes naming the slot (a compiler whose parent already died) are roots too: their children
        # (a tool started without a path on its command line) go with them.
        foreach ($id in (Get-TaskProcessTree -ExtraRoots @(Get-SlotProcesses))) { [void]$found.Add($id) }
        $ids = @($found | Where-Object {
                $_ -ne $PID -and (Get-Process -Id $_ -ErrorAction SilentlyContinue).ProcessName -notin @($null, 'mspdbsrv') })
        if ($ids.Count -eq 0) { break }
        foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; [void]$killed.Add($id) }
        Start-Sleep -Seconds 1
    }
    $killed.Count
}

function Test-ObjectFile([IO.FileInfo]$File) {
    # $false: a damaged MSVC object (truncated, or not an object at all); $true: complete; $null: a format not
    # judged here (an LTCG or other anonymous object). Complete = the symbol table and the string table that follows
    # it end inside the file: a compiler killed while it wrote the file leaves it short.
    if ($File.Length -lt 20) { return $false }
    $fs = $null
    try {
        $fs = [IO.File]::Open($File.FullName, 'Open', 'Read', 'ReadWrite')
        $h = New-Object byte[] 56
        $n = $fs.Read($h, 0, 56)
        $sig2 = [BitConverter]::ToUInt16($h, 2)
        if ([BitConverter]::ToUInt16($h, 0) -eq 0 -and $sig2 -eq 0xFFFF) {
            # bigobj (ANON_OBJECT_HEADER_BIGOBJ, version 2, ClassID d1baa1c7-baee-4ba9-af20-faf66aa4dcb8)
            if ($n -lt 56 -or [BitConverter]::ToUInt16($h, 4) -lt 2) { return $null }
            $guid = [Guid]::new([byte[]]$h[12..27])
            if ($guid -ne [Guid]'d1baa1c7-baee-4ba9-af20-faf66aa4dcb8') { return $null }
            $symPtr = [BitConverter]::ToUInt32($h, 48); $nSym = [BitConverter]::ToUInt32($h, 52); $symSize = 20
        } elseif (@(0x8664, 0x14c, 0xaa64) -contains [BitConverter]::ToUInt16($h, 0)) {
            $symPtr = [BitConverter]::ToUInt32($h, 8); $nSym = [BitConverter]::ToUInt32($h, 12); $symSize = 18
        } else { return $false }
        if ($symPtr -eq 0) { return $true }   # no symbol table: nothing to measure
        $strAt = [int64]$symPtr + [int64]$nSym * $symSize
        if ($strAt + 4 -gt $File.Length) { return $false }
        [void]$fs.Seek($strAt, 'Begin')
        $b = New-Object byte[] 4
        if ($fs.Read($b, 0, 4) -ne 4) { return $false }
        return ($strAt + [BitConverter]::ToUInt32($b, 0)) -le $File.Length
    } catch { return $null } finally { if ($fs) { $fs.Dispose() } }
}

function Remove-DamagedObjects([datetime]$Since = [datetime]::MinValue) {
    # Object files of the slot's workdir written at or after $Since that Test-ObjectFile finds damaged are deleted;
    # make then compiles them again. The modification time is read from the directory listing, so only the recent
    # files are opened.
    $removed = [Collections.Generic.List[string]]::new(); $checked = 0
    foreach ($sub in 'CxxObject', 'CObject', 'GenCxxObject', 'GenCObject', 'ObjCxxObject', 'ObjCObject') {
        $dir = Join-Path $Root "lo\workdir\$sub"
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        foreach ($f in ([IO.DirectoryInfo]$dir).EnumerateFiles('*.o', 'AllDirectories')) {
            if ($f.LastWriteTime -lt $Since) { continue }
            $checked++
            if ((Test-ObjectFile $f) -eq $false) {
                Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
                $removed.Add($f.FullName.Substring($Root.Length + 1))
            }
        }
    }
    [ordered]@{ checked = $checked; removed = $removed.Count; files = @($removed | Select-Object -First 20) }
}

function Get-TaskStart {
    $log = Join-Path $Root "logs\task-$Job.log"
    if (Test-Path -LiteralPath $log) {
        $m = Select-String -LiteralPath $log -Pattern "^\[([0-9T:-]+)\] start $Task" | Select-Object -First 1
        if ($m) { return [datetime]$m.Matches[0].Groups[1].Value }
    }
    (Get-Date).AddHours(-6)   # no start line: every object of the last hours is checked
}

function Get-LogTail([int]$Lines = 60) {
    $log = Join-Path $Root "logs\task-$Job.log"
    if (Test-Path -LiteralPath $log) { (Get-Content -LiteralPath $log -Tail $Lines) -join "`n" } else { '' }
}

switch ($Action) {
    'DiskReport' {
        $rows = foreach ($d in @(Get-ChildItem -LiteralPath 'D:\hst-test' -Directory -Force -ErrorAction SilentlyContinue)) {
            $files = @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue)
            $bytes = 0.0; foreach ($f in $files) { $bytes += $f.Length }   # (Measure-Object has no Sum for an empty folder)
            $newest = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
            $tagFile = Join-Path $d.FullName '.hst-owner'
            $tag = if (Test-Path -LiteralPath $tagFile) { (Get-Content -LiteralPath $tagFile -TotalCount 1) -replace '[^\w .@/:-]', '' } else { '' }
            [ordered]@{ name = $d.Name; gib = [math]::Round([double]$bytes / 1GB, 2); files = $files.Count
                newest = if ($newest) { $newest.LastWriteTime.ToString('s') } else { $d.LastWriteTime.ToString('s') }
                owner = $tag }
        }
        $largest = @($rows | Sort-Object { $_.gib } -Descending | Select-Object -First $Top)   # ($top would be $Top)
        Out-Json @{ d_free_gib = [math]::Round((Get-PSDrive D).Free / 1GB, 1); c_free_gib = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
            taken = (Get-Date).ToString('s'); folders = $largest }
    }
    'Deploy' {
        $src = 'D:\hst-test\hst-build-tools\scripts'
        if (-not (Test-Path -LiteralPath $src)) { throw "nothing staged at $src" }
        New-Item -ItemType Directory -Force -Path $Scripts | Out-Null
        Copy-Item -Recurse -Force -Path "$src\*" -Destination $Scripts
        Remove-Item -Recurse -Force -LiteralPath $src
        Out-Json @{ deployed = $true; scripts = $Scripts }
    }
    'Probe' {
        $os = Get-CimInstance Win32_OperatingSystem
        $drive = Get-PSDrive $Root.Substring(0, 1)
        Out-Json @{ busy = ((Test-LockHeld) -or (Test-QueueTaskRunning)); root = $Root
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
        $tail = Get-LogTail
        $buildLog = Join-Path $Root 'logs\build.log'
        if (-not $ok -and (Test-Path -LiteralPath $buildLog)) {
            # make's own error is in the slot's build.log, not in the task log.
            $tail += "`n== tail of $buildLog`n" + ((Get-Content -LiteralPath $buildLog -Tail 40) -join "`n")
        }
        Out-Json @{ state = $(if ($ok) { 'done' } else { 'failed' }); out = $out; error = $err; log = $tail + "`n" }
    }
    'Cancel' {
        Need-Job
        $since = Get-TaskStart
        if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue   # no restart while its tree is stopped
        }
        $killed = Stop-SlotBuild
        Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
        $objects = Remove-DamagedObjects $since
        $taskLog = Join-Path $Root "logs\task-$Job.log"
        "[$(Get-Date -Format s)] cancel: stopped $killed processes; checked $($objects.checked) objects written since $($since.ToString('s')), deleted $($objects.removed) damaged: $($objects.files -join ', ')" |
            Out-File -LiteralPath $taskLog -Append -Encoding utf8
        "[$(Get-Date -Format s)] end $Task rc=130 (cancelled)" | Out-File -LiteralPath $taskLog -Append -Encoding utf8
        Out-Json @{ cancelled = $true; killed = $killed; objects = $objects }
    }
    'Clean' {
        if ((Test-LockHeld) -or (Test-QueueTaskRunning)) {
            Out-Json @{ cleaned = $false; reason = "$Root is busy (build.lock held or a queue task running)" }; break
        }
        $lo = Join-Path $Root 'lo'
        if (-not (Test-Path -LiteralPath $lo)) { Out-Json @{ cleaned = $false; reason = "no tree at $lo" }; break }
        $before = [math]::Round((Get-PSDrive $Root.Substring(0, 1)).Free / 1GB, 1)
        if ($Full) {
            foreach ($d in 'workdir', 'instdir') {
                $p = Join-Path $lo $d
                if (Test-Path -LiteralPath $p) { cmd.exe /c rd /s /q "$p" | Out-Null }
            }
            $left = @('workdir', 'instdir' | Where-Object { Test-Path -LiteralPath (Join-Path $lo $_) })
            Out-Json @{ cleaned = ($left.Count -eq 0); full = $true; left = $left; free_gib_before = $before
                free_gib = [math]::Round((Get-PSDrive $Root.Substring(0, 1)).Free / 1GB, 1) }
        } else {
            $objects = Remove-DamagedObjects
            Out-Json @{ cleaned = $true; full = $false; objects = $objects }
        }
    }
    'Cleanup' {
        Need-Job
        $out = Join-Path $Root "out\$Job"
        if (Test-Path -LiteralPath $out) { cmd.exe /c rd /s /q "$out" | Out-Null }
        Out-Json @{ removed = -not (Test-Path -LiteralPath $out) }
    }
}
