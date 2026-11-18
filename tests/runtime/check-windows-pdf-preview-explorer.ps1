# SPDX-License-Identifier: AGPL-3.0-only
<#
.SYNOPSIS
  HST PDF preview and thumbnails in a real File Explorer window (run in the console user's session).

.DESCRIPTION
  Opens a folder holding a freshly written 3-page PDF in File Explorer, Large icons view, the PDF selected
  and the preview pane on, and reports which preview handler Explorer loaded (HST's draws into a window of
  class HSTOfficePdfPreview, hosted by prevhost.exe). With -ExpectHst the HST preview must be there and
  scroll (mouse wheel sent to it); without, the check only reports. Screenshots contain this Explorer window
  only (anything else on screen in its rectangle is painted black). Writes Out\explorer.log and PNGs; the
  window is closed at the end. Start it with tests/realwin/remote.py HOST ui (interactive-task.ps1).
#>
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Tag = 'explorer',
    [switch]$ExpectHst
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$log = Join-Path $Out "$Tag.log"
function Log([string]$line) { Add-Content -LiteralPath $log -Value $line -Encoding UTF8; $line }
Set-Content -LiteralPath $log -Value "start $(Get-Date -Format s)" -Encoding UTF8
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class HstExplorer {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc f, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
    public static List<string> Children(IntPtr parent, string cls) {
        var found = new List<string>();
        EnumChildWindows(parent, (h, l) => {
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            if (cls == null || c.ToString() == cls) { uint pid; GetWindowThreadProcessId(h, out pid);
                found.Add(h.ToInt64() + "|" + c + "|" + pid + "|" + IsWindowVisible(h)); }
            return true; }, IntPtr.Zero);
        return found;
    }
    // Screen copy of one top-level window; points whose root window is another window are painted black.
    public static System.Drawing.Bitmap Shot(IntPtr hwnd) {
        RECT r; if (DwmGetWindowAttribute(hwnd, 9, out r, 16) != 0) GetWindowRect(hwnd, out r);
        int w = r.Right - r.Left, h = r.Bottom - r.Top;
        var b = new System.Drawing.Bitmap(w, h);
        using (var g = System.Drawing.Graphics.FromImage(b)) {
            g.CopyFromScreen(r.Left, r.Top, 0, 0, new System.Drawing.Size(w, h));
            for (int y = 0; y < h; y += 4) for (int x = 0; x < w; x += 4) {
                POINT p; p.X = r.Left + x + 2; p.Y = r.Top + y + 2;
                if (GetAncestor(WindowFromPoint(p), 2) != hwnd) g.FillRectangle(System.Drawing.Brushes.Black, x, y, 4, 4);
            }
        }
        return b;
    }
}
'@
[void][HstExplorer]::SetProcessDpiAwarenessContext([IntPtr]-4)

# Fresh folder and file names: no cached thumbnails from an earlier run.
$stamp = Get-Date -Format 'HHmmss'
$folder = Join-Path $Out "pdf-$Tag-$stamp"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
. (Join-Path $PSScriptRoot 'pdf-preview-fixture.ps1')
$pdf = Join-Path $folder 'ba-trang.pdf'
New-TestPdf $pdf 3
Log "pdf $pdf ($((Get-Item $pdf).Length) bytes)"

$shell = New-Object -ComObject Shell.Application
$before = @($shell.Windows() | ForEach-Object { $_.HWND })
Start-Process explorer.exe -ArgumentList "`"$folder`""
$window = $null
for ($i = 0; $i -lt 40 -and -not $window; $i++) {
    Start-Sleep -Milliseconds 500
    $window = $shell.Windows() | Where-Object { $before -notcontains $_.HWND -and $_.Document -and $_.Document.Folder.Self.Path -eq $folder } | Select-Object -First 1
}
if (-not $window) { Log 'FAIL Explorer window did not open'; exit 1 }
$hwnd = [IntPtr]$window.HWND
$failures = 0
try {
    [void][HstExplorer]::ShowWindow($hwnd, 3)  # maximised: room for the preview pane
    $view = $window.Document
    $view.CurrentViewMode = 1; $view.IconSize = 256  # Large icons
    $item = $view.Folder.ParseName('ba-trang.pdf')
    $view.SelectItem($item, 1 + 4 + 8 + 16)
    [void][HstExplorer]::SetForegroundWindow($hwnd)
    Start-Sleep -Seconds 2
    $previewWindows = @()
    for ($attempt = 0; $attempt -lt 2 -and -not $previewWindows; $attempt++) {
        # Alt+P toggles the preview pane; stop as soon as a preview window appears
        [void][HstExplorer]::SetForegroundWindow($hwnd)
        [System.Windows.Forms.SendKeys]::SendWait('%p')
        Start-Sleep -Seconds 6
        $previewWindows = @([HstExplorer]::Children($hwnd, 'HSTOfficePdfPreview'))
        if (-not $previewWindows) {
            $hosts = @([HstExplorer]::Children($hwnd, $null) | Where-Object { $_ -match '\|(\d+)\|' -and (Get-Process -Id $Matches[1] -ErrorAction SilentlyContinue).ProcessName -eq 'prevhost' })
            Log "attempt ${attempt}: no HST preview window; prevhost windows: $($hosts -join '; ')"
            if ($hosts) { break }  # another handler is showing the preview
        }
    }
    $shot = [HstExplorer]::Shot($hwnd); $shot.Save((Join-Path $Out "$Tag-preview.png")); $shot.Dispose()
    Log "HST preview windows: $($previewWindows -join '; ')"
    if ($ExpectHst) {
        if (-not $previewWindows) { Log 'FAIL Explorer did not load the HST preview handler'; $failures++ }
        else {
            $child = [IntPtr][long]($previewWindows[0] -split '\|')[0]
            $hostPid = ($previewWindows[0] -split '\|')[2]
            Log "PASS HST preview handler in $((Get-Process -Id $hostPid).ProcessName) (pid $hostPid)"
            for ($n = 0; $n -lt 12; $n++) { [void][HstExplorer]::SendMessageW($child, 0x20A, [IntPtr]((-120) -shl 16), [IntPtr]::Zero) }
            Start-Sleep -Seconds 2
            $shot = [HstExplorer]::Shot($hwnd); $shot.Save((Join-Path $Out "$Tag-preview-scrolled.png")); $shot.Dispose()
            Log 'scrolled 12 wheel notches; see the -scrolled screenshot'
        }
    }
    # Thumbnails: clear the selection so the icon is drawn without the selection frame.
    $view.SelectItem($item, 0)
    Start-Sleep -Seconds 3
    $shot = [HstExplorer]::Shot($hwnd); $shot.Save((Join-Path $Out "$Tag-thumbnail.png")); $shot.Dispose()
    Log 'thumbnail screenshot written'
} finally {
    $window.Quit()
}
Log "$failures failures"
exit [int]($failures -ne 0)
