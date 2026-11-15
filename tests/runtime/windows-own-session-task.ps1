# SPDX-License-Identifier: AGPL-3.0-only
# Run one command line in the CALLING user's own interactive session (connected or disconnected) through a temporary
# scheduled task. SSH runs in session 0, which has no desktop; GUI checks (run-check-windows.py --ui,
# check-windows-nd30-wizard-fit.py) need a session. This never touches another user's (e.g. the console user's)
# session. The caller must have logged on once (the session may stay disconnected; screen capture with CopyFromScreen
# fails there, PrintWindow works). The command runs hidden, the timeout is enforced, the task is always deleted.
# Usage:
#   powershell -File windows-own-session-task.ps1 -CommandLine '<cmd line>' -WorkDir <dir> [-TimeoutSec 900]
# The command line runs in cmd.exe from WorkDir; it writes its own output (redirect it into WorkDir).
# Prints EXIT=<code> (or TIMEOUT) and exits with that code (124 on timeout).
param(
    [Parameter(Mandatory = $true)][string]$CommandLine,
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [int]$TimeoutSec = 900
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if (-not (Get-Process -IncludeUserName -Name explorer -ErrorAction SilentlyContinue | Where-Object UserName -eq $me)) {
    throw "$me has no interactive session on this machine; log on once (it may stay disconnected)"
}
$name = 'hst-test-own-session-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$wrapper = Join-Path $WorkDir "$name.cmd"; $exitFile = Join-Path $WorkDir "$name.exit"; $vbs = Join-Path $WorkDir 'run-hidden.vbs'
Set-Content -Path $vbs -Encoding ASCII -Value "Set s = CreateObject(""WScript.Shell"")`r`nWScript.Quit s.Run(""cmd.exe /c """""" & WScript.Arguments(0) & """""""", 0, True)"
# redirect first: `echo 0> f` would redirect a stream instead of writing 0
Set-Content -Path $wrapper -Encoding ASCII -Value ("@echo off`r`ncd /d `"$WorkDir`"`r`nset PYTHONIOENCODING=utf-8`r`n" +
    "$CommandLine`r`n> `"$exitFile`" echo %ERRORLEVEL%`r`n")
$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "//B //NoLogo `"$vbs`" `"$wrapper`""
$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Seconds ($TimeoutSec + 120))
try {
    Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $name
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline -and -not (Test-Path $exitFile)) { Start-Sleep 2 }
    Start-Sleep 1
    if (Test-Path $exitFile) { $code = [int](Get-Content $exitFile -Raw).Trim(); "EXIT=$code"; exit $code }
    'TIMEOUT'
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    exit 124
} finally {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $wrapper, $exitFile -ErrorAction SilentlyContinue
}
