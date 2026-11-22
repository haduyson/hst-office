# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Run one command line in the logged-on console user's desktop session through a temporary scheduled task
# (SSH runs in session 0 without a desktop). The command runs hidden (wscript wrapper, no console window on the
# user's screen). Before it starts, the console must have had no keyboard/mouse input for IdleMinutes, measured
# in the session itself with GetLastInputInfo (`query user` reports "none" for console sessions). Enforces a
# timeout, returns the command's exit code and always deletes the task. Output must be written by the command
# itself under C:\hst-test.
# COMMANDLINE runs with `call`, so a .cmd/.bat returns to the wrapper: without `call`, cmd.exe hands control to the
# batch file for good and nothing after it runs (that lost every exit code of `remote.py ui run.cmd` as 93). The exit
# code is written by the wscript wrapper from the exit status of the whole cmd.exe, so it is recorded even when the
# command ends cmd.exe itself (`exit N` in a batch file). Codes of this script besides the command's own: 90 no
# console user, 91 console not idle, 93 the task ended or timed out without an exit code (stopped, or never ran).
param(
    [Parameter(Mandatory = $true)][string]$CommandLine,
    [int]$TimeoutSec = 900,
    [int]$IdleMinutes = 1,
    [int]$MaxWaitIdleSec = 1800
)
$ErrorActionPreference = 'Stop'
$dir = 'C:\hst-test\ps'
New-Item -ItemType Directory -Force $dir | Out-Null

function Get-ConsoleUser {
    foreach ($row in (query user 2>$null) | Select-Object -Skip 1) {
        if ($row.TrimStart('>').Trim() -match '^(\S+)\s+console\s+\d+\s+Active') { return $Matches[1] }
    }
    return $null
}

$hidden = Join-Path $dir 'run-hidden.vbs'
Set-Content -Path $hidden -Encoding ASCII -Value @'
' Runs a .cmd file without a window, writes its exit code to the file named by argument 2 (written to a
' temporary name, then renamed: the reader never sees a half-written file) and returns it.
Set shell = CreateObject("WScript.Shell")
rc = shell.Run("cmd.exe /c """ & WScript.Arguments(0) & """", 0, True)
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile(WScript.Arguments(1) & ".tmp", True)
f.WriteLine rc
f.Close
If fso.FileExists(WScript.Arguments(1)) Then fso.DeleteFile WScript.Arguments(1), True
fso.MoveFile WScript.Arguments(1) & ".tmp", WScript.Arguments(1)
WScript.Quit rc
'@

function Invoke-InSession([string]$user, [string]$commandLine, [int]$timeout) {
    $name = 'hst-test-ui-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $wrapper = Join-Path $dir "$name.cmd"
    $exitFile = Join-Path $dir "$name.exit"
    Set-Content -Path $wrapper -Encoding ASCII -Value "@echo off`r`ncd /d C:\hst-test`r`ncall $commandLine`r`nexit /b %ERRORLEVEL%`r`n"
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "//B //NoLogo `"$hidden`" `"$wrapper`" `"$exitFile`""
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Seconds ($timeout + 120)) -MultipleInstances IgnoreNew
    try {
        Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Principal $principal -Settings $settings | Out-Null
        Start-ScheduledTask -TaskName $name
        $deadline = (Get-Date).AddSeconds($timeout)
        $stopped = 0  # the task can read Ready before it starts and after it ends; only a lasting stop counts
        while ((Get-Date) -lt $deadline -and -not (Test-Path $exitFile)) {
            Start-Sleep -Seconds 2
            if ((Get-ScheduledTask -TaskName $name).State -ne 'Running') { $stopped += 2 } else { $stopped = 0 }
            if ($stopped -ge 12) { break }
        }
        for ($i = 0; $i -lt 10 -and (Test-Path $exitFile); $i++) {
            $text = Get-Content $exitFile -Raw -ErrorAction SilentlyContinue  # empty while cmd is still writing it
            if ($text -and $text.Trim()) { return [int]$text.Trim() }
            Start-Sleep -Milliseconds 300
        }
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        return 93
    } finally {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item $wrapper, $exitFile, "$exitFile.tmp" -ErrorAction SilentlyContinue
    }
}

$user = Get-ConsoleUser
if (-not $user) { Write-Output 'NO_CONSOLE_USER'; exit 90 }
foreach ($root in 'C:\hst-test', 'D:\hst-test') {
    if (Test-Path $root) { icacls $root /grant "${user}:(OI)(CI)M" /Q | Out-Null }
}

$probe = Join-Path $dir 'idle-probe.ps1'
$idleFile = Join-Path $dir 'idle-seconds.txt'
Set-Content -Path $probe -Encoding ASCII -Value @'
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class HstIdle { [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; } [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p); public static uint Seconds() { var l = new LII(); l.cbSize = 8; GetLastInputInfo(ref l); return ((uint)Environment.TickCount - l.dwTime) / 1000; } }'
Set-Content -Path 'C:\hst-test\ps\idle-seconds.txt' -Value ([HstIdle]::Seconds())
'@
$waited = 0
while ($true) {
    Remove-Item $idleFile -ErrorAction SilentlyContinue
    $null = Invoke-InSession $user "powershell -NoProfile -ExecutionPolicy Bypass -File `"$probe`"" 60
    $text = if (Test-Path $idleFile) { Get-Content $idleFile -Raw -ErrorAction SilentlyContinue } else { $null }
    $idle = if ($text -and $text.Trim()) { [int]$text.Trim() } else { -1 }
    if ($idle -ge $IdleMinutes * 60) { break }
    if ($waited -ge $MaxWaitIdleSec) { Write-Output "CONSOLE_BUSY user=$user idle=${idle}s"; exit 91 }
    Start-Sleep -Seconds 30; $waited += 30
}
Write-Output "console=$user idle=${idle}s waited=${waited}s"
$code = Invoke-InSession $user $CommandLine $TimeoutSec
Write-Output "EXIT=$code"
exit $code
