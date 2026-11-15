# SPDX-License-Identifier: AGPL-3.0-only
# Run the citation dialog check (check-citations-dialogs.py --windows) in the CALLING user's own interactive
# session, connected or not, through a temporary scheduled task. It never touches the console user's session.
# SSH runs in session 0, which has no desktop; the task needs the tester to have a session (a disconnected one is fine).
# The task runs hidden, the timeout is enforced, and the task is always deleted.
# Usage (as the test user, e.g. over SSH):
#   powershell -File citations-dialogs-own-session.ps1 -Root D:\hst-test\citations-ui -InstDir D:\hst-test\citations-ui\inst
# Root holds tests\ (a copy of the repo's tests/runtime and tests/fixtures/citations); results go to Root\run-dialogs.
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$InstDir,
    [int]$TimeoutSec = 900
)
$ErrorActionPreference = 'Stop'
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$mine = (Get-Process -IncludeUserName -Name explorer -ErrorAction SilentlyContinue | Where-Object UserName -eq $me)
if (-not $mine) { throw "$me has no interactive session on this machine; log on once (it may stay disconnected)" }
$name = 'hst-test-citations-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$wrapper = Join-Path $Root "$name.cmd"; $exitFile = Join-Path $Root "$name.exit"; $vbs = Join-Path $Root 'run-hidden.vbs'
$log = Join-Path $Root 'run-dialogs.log'
$python = Join-Path $InstDir 'program\python.exe'
$check = Join-Path $Root 'tests\runtime\check-citations-dialogs.py'
Set-Content -Path $vbs -Encoding ASCII -Value "Set s = CreateObject(""WScript.Shell"")`r`nWScript.Quit s.Run(""cmd.exe /c """""" & WScript.Arguments(0) & """""""", 0, True)"
Set-Content -Path $wrapper -Encoding ASCII -Value ("@echo off`r`ncd /d `"$Root`"`r`nset PYTHONIOENCODING=utf-8`r`n" +
    "`"$python`" `"$check`" --instdir `"$InstDir`" --out `"$Root\run-dialogs`" --windows > `"$log`" 2>&1`r`n" +
    "> `"$exitFile`" echo %ERRORLEVEL%`r`n")
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
    if (Test-Path $log) { Get-Content $log -Encoding UTF8 }
    if (Test-Path $exitFile) { $code = [int](Get-Content $exitFile -Raw).Trim(); "EXIT=$code"; exit $code }
    'TIMEOUT'
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    exit 124
} finally {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $wrapper, $exitFile -ErrorAction SilentlyContinue
}
