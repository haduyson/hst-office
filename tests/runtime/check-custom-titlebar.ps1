# SPDX-License-Identifier: AGPL-3.0-only
# Own title bar of the Tabbed document windows (hst-custom-titlebar.patch), checked through Win32 on a real
# window: client area up to the window's top edge, the hit test of every part of the top row (WM_NCHITTEST, the
# same answer the system uses for drag, Aero Snap, Snap Layouts and the system menu), maximized client inside
# the monitor work area, the caption buttons (WM_NCLBUTTONDOWN/UP), double-click on the caption, UI
# Automation of the title bar, window size across restarts and the opt-out setting.
# Runs in the caller's own session (windows-own-session-task.ps1); a fresh profile per case under OutDir.
# Usage: powershell -File check-custom-titlebar.ps1 -Soffice <...\program\soffice.exe> -OutDir C:\hst-test\ct
#        [-App writer|calc|impress] [-SystemTitleBar] [-Appearance 0|1|2] [-Restarts 2]
# Writes <OutDir>\<case>.json and prints PASS/FAIL lines; exit 1 on any failure.
param(
    [Parameter(Mandatory = $true)][string]$Soffice,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [ValidateSet('writer', 'calc', 'impress')][string]$App = 'writer',
    [switch]$SystemTitleBar,
    [int]$Appearance = 0,
    [int]$Restarts = 2
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class Ct {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct MONITORINFO { public int cb; public RECT mon, work; public uint flags; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint f);
    [DllImport("user32.dll")] public static extern bool GetMonitorInfo(IntPtr m, ref MONITORINFO i);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
    public static IntPtr Find(uint pid) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
            var c = new StringBuilder(64); GetClassName(h, c, 64);
            if (p == pid && IsWindowVisible(h) && c.ToString() == "SALFRAME") { RECT r; GetWindowRect(h, out r);
                if (r.R - r.L > 400 && r.B - r.T > 300) { found = h; return false; } }
            return true; }, IntPtr.Zero);
        return found;
    }
    public static int Hit(IntPtr h, int x, int y) {
        return (int)SendMessage(h, 0x84, IntPtr.Zero, (IntPtr)((y << 16) | (x & 0xFFFF)));
    }
    public static IntPtr Lp(int x, int y) { return (IntPtr)((y << 16) | (x & 0xFFFF)); }
}
'@
$failures = 0
$report = [ordered]@{ app = $App; systemTitleBar = [bool]$SystemTitleBar; appearance = $Appearance; checks = @() }
function Check($name, $ok, $detail) {
    $script:report.checks += [ordered]@{ name = $name; ok = [bool]$ok; detail = "$detail" }
    if ($ok) { "PASS $name $detail" } else { "FAIL $name $detail"; $script:failures++ }
}
function Rects($h) {
    $w = New-Object Ct+RECT; $c = New-Object Ct+RECT; $p = New-Object Ct+POINT
    [void][Ct]::GetWindowRect($h, [ref]$w); [void][Ct]::GetClientRect($h, [ref]$c); [void][Ct]::ClientToScreen($h, [ref]$p)
    [ordered]@{ win = @($w.L, $w.T, $w.R, $w.B); client = @($p.X, $p.Y, $p.X + $c.R, $p.Y + $c.B) }
}
$case = "$App-" + $(if ($SystemTitleBar) { 'system' } else { 'own' }) + "-a$Appearance"
$profile = Join-Path $OutDir "profile-$case"
Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $profile 'user') | Out-Null
$items = "<item oor:path=`"/org.openoffice.Office.Common/Misc`"><prop oor:name=`"HstSystemTitleBar`" oor:op=`"fuse`"><value>$(([string][bool]$SystemTitleBar).ToLower())</value></prop></item>"
$items += "<item oor:path=`"/org.openoffice.Office.Common/Misc`"><prop oor:name=`"Appearance`" oor:op=`"fuse`"><value>$Appearance</value></prop></item>"
Set-Content -Encoding UTF8 (Join-Path $profile 'user\registrymodifications.xcu') ("<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n" +
    "<oor:items xmlns:oor=`"http://openoffice.org/2001/registry`" xmlns:xs=`"http://www.w3.org/2001/XMLSchema`" " +
    "xmlns:xsi=`"http://www.w3.org/2001/XMLSchema-instance`">$items</oor:items>")
$profileUrl = 'file:///' + ($profile -replace '\\', '/')

function Start-Hst {
    $proc = Start-Process -FilePath $Soffice -PassThru -ArgumentList @("-env:UserInstallation=$profileUrl", '--norestore', '--nologo', "--$App")
    $deadline = (Get-Date).AddSeconds(120); $h = [IntPtr]::Zero
    while ((Get-Date) -lt $deadline) {
        foreach ($p in Get-Process soffice.bin -ErrorAction SilentlyContinue) { $h = [Ct]::Find([uint32]$p.Id); if ($h -ne [IntPtr]::Zero) { break } }
        if ($h -ne [IntPtr]::Zero) { break }; Start-Sleep 1
    }
    if ($h -eq [IntPtr]::Zero) { throw 'no document window' }
    Start-Sleep 8  # first-start dialogs, notebookbar, the asynchronous title bar switch
    foreach ($p in Get-Process soffice.bin -ErrorAction SilentlyContinue) { $h2 = [Ct]::Find([uint32]$p.Id); if ($h2 -ne [IntPtr]::Zero) { $h = $h2 } }
    return $h
}
function Stop-Hst($h) {
    [void][Ct]::PostMessage($h, 0x10, [IntPtr]::Zero, [IntPtr]::Zero)  # WM_CLOSE: the window state is saved
    Start-Sleep 6
    Get-Process soffice.bin, soffice -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$(Split-Path $Soffice)*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
}

try {
    $h = Start-Hst
    if ([Ct]::IsZoomed($h)) { [void][Ct]::ShowWindow($h, 9); Start-Sleep 2 }
    $r = Rects $h; $report.dpi = [Ct]::GetDpiForWindow($h); $report.restored = $r
    $scale = $report.dpi / 96.0
    $topDeco = $r.client[1] - $r.win[1]
    if ($SystemTitleBar) {
        Check 'system-caption' ($topDeco -ge [int](20 * $scale)) "top decoration $topDeco px"
    } else {
        Check 'client-at-top' ($topDeco -eq 0) "top decoration $topDeco px"
        $cx = $r.client[0]; $cy = $r.client[1]; $right = $r.client[2]
        $btn = [int][math]::Round(46 * $scale)
        Check 'hit-top-edge' ([Ct]::Hit($h, $cx + 300, $cy + 1) -eq 12) 'HTTOP'
        Check 'hit-band' ([Ct]::Hit($h, $cx + 300, $cy + [int](9 * $scale)) -eq 2) 'HTCAPTION'
        $y = $cy + [int](24 * $scale)
        Check 'hit-close' ([Ct]::Hit($h, $right - $btn / 2, $y) -eq 20) 'HTCLOSE'
        Check 'hit-max' ([Ct]::Hit($h, $right - $btn * 3 / 2, $y) -eq 9) 'HTMAXBUTTON'
        Check 'hit-min' ([Ct]::Hit($h, $right - $btn * 5 / 2, $y) -eq 8) 'HTMINBUTTON'
        # the tab row line: runs of client (tabs, quick access, search) and caption (empty parts, title)
        $row = $cy + [int](30 * $scale); $runs = @(); $last = -1
        for ($x = $cx + 2; $x -lt $right - 3 * $btn; $x += 2) {
            $code = [Ct]::Hit($h, $x, $row)
            if ($code -ne $last) { $runs += "$($x - $cx):$code"; $last = $code }
        }
        $report.tabRowRuns = $runs
        Check 'tab-row-has-controls-and-caption' (($runs -match ':1$').Count -ge 1 -and ($runs -match ':2$').Count -ge 1) ($runs -join ' ')
        Check 'hit-document' ([Ct]::Hit($h, $cx + 300, $cy + [int](300 * $scale)) -eq 1) 'HTCLIENT'
        # caption buttons through the non-client messages the system sends
        [void][Ct]::PostMessage($h, 0xA1, [IntPtr]9, [Ct]::Lp($right - $btn * 3 / 2, $y)); [void][Ct]::PostMessage($h, 0xA2, [IntPtr]9, [Ct]::Lp($right - $btn * 3 / 2, $y))
        Start-Sleep 3; Check 'max-button-maximizes' ([Ct]::IsZoomed($h)) ''
        $m = New-Object Ct+MONITORINFO; $m.cb = [Runtime.InteropServices.Marshal]::SizeOf($m)
        [void][Ct]::GetMonitorInfo([Ct]::MonitorFromWindow($h, 2), [ref]$m); $rm = Rects $h; $report.maximized = $rm
        Check 'maximized-inside-work-area' ($rm.client[1] -ge $m.work.T -and $rm.client[0] -ge $m.work.L -and $rm.client[2] -le $m.work.R -and $rm.client[3] -le $m.work.B -and $rm.client[1] -le $m.work.T + 1) "client $($rm.client -join ',') work $($m.work.L),$($m.work.T),$($m.work.R),$($m.work.B)"
        Check 'maximized-close-at-corner' ([Ct]::Hit($h, $rm.client[2] - 2, $rm.client[1] + 2) -eq 20) 'HTCLOSE at the top-right pixel'
        [void][Ct]::PostMessage($h, 0xA1, [IntPtr]9, [Ct]::Lp($rm.client[2] - $btn * 3 / 2, $rm.client[1] + 20)); [void][Ct]::PostMessage($h, 0xA2, [IntPtr]9, [Ct]::Lp($rm.client[2] - $btn * 3 / 2, $rm.client[1] + 20))
        Start-Sleep 3; Check 'max-button-restores' (-not [Ct]::IsZoomed($h)) ''
        [void][Ct]::PostMessage($h, 0xA3, [IntPtr]2, [Ct]::Lp($cx + 300, $cy + 8))  # WM_NCLBUTTONDBLCLK on the band
        Start-Sleep 3; Check 'double-click-maximizes' ([Ct]::IsZoomed($h)) ''
        [void][Ct]::ShowWindow($h, 9); Start-Sleep 2
        [void][Ct]::PostMessage($h, 0xA1, [IntPtr]8, [Ct]::Lp($right - $btn * 5 / 2, $y)); [void][Ct]::PostMessage($h, 0xA2, [IntPtr]8, [Ct]::Lp($right - $btn * 5 / 2, $y))
        Start-Sleep 3; Check 'min-button-minimizes' ([Ct]::IsIconic($h)) ''
        [void][Ct]::ShowWindow($h, 9); Start-Sleep 3
        # UI Automation: the system title bar provider reports the drawn buttons where they are
        $el = [Windows.Automation.AutomationElement]::FromHandle($h)
        $bar = $el.FindFirst([Windows.Automation.TreeScope]::Children,
            (New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::TitleBar)))
        $uia = @()
        if ($bar) {
            foreach ($b in $bar.FindAll([Windows.Automation.TreeScope]::Children, [Windows.Automation.Condition]::TrueCondition)) {
                $br = $b.Current.BoundingRectangle
                $uia += [ordered]@{ name = $b.Current.Name; id = $b.Current.AutomationId; rect = @([int]$br.Left, [int]$br.Top, [int]$br.Right, [int]$br.Bottom); offscreen = $b.Current.IsOffscreen }
            }
        }
        $report.uia = $uia; $report.uiaWindowName = $el.Current.Name
        $closeUia = $uia | Where-Object { $_.id -eq 'Close' }
        Check 'uia-title-bar-buttons' ($uia.Count -ge 3 -and $closeUia -and [math]::Abs($closeUia.rect[2] - $right) -le 2 -and [math]::Abs($closeUia.rect[1] - $cy) -le 2) (($uia | ForEach-Object { "$($_.id)@$($_.rect -join ',')" }) -join ' ')
        Check 'uia-window-name' ($el.Current.Name -like '*HST*') $el.Current.Name
    }
    # window size across restarts: no drift from the switch between caption terms
    $before = (Rects $h).win
    for ($i = 1; $i -le $Restarts; $i++) {
        Stop-Hst $h; $h = Start-Hst
        $after = (Rects $h).win
        Check "restart-$i-same-window-rect" ((Compare-Object $before $after) -eq $null) "$($before -join ',') -> $($after -join ',')"
    }
    Stop-Hst $h
} catch {
    Check 'run' $false $_.Exception.Message
    Get-Process soffice.bin, soffice -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$(Split-Path $Soffice)*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}
$report.failures = $failures
$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutDir "$case.json")
if ($failures) { exit 1 }
