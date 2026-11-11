# SPDX-License-Identifier: AGPL-3.0-only
# Capture only HST Office (soffice) or reference office windows, never the desktop: each visible top-level window
# of an allowed process is copied from the screen inside its own frame rectangle, at real pixels, and every 4x4
# block whose visible top-level window (WindowFromPoint) belongs to another process is filled black, so nothing
# else (other apps, notifications, the desktop) can leak into the image.
# (PrintWindow cannot render the office's GPU/Skia surfaces: black canvas, duplicated bars.)
# Writes <Prefix>-<n>.png and <Prefix>.json (title, process, rect, DPI, black-filled area).
# Must run in the user's interactive session (interactive-task.ps1).
param(
    [Parameter(Mandatory = $true)][string]$Prefix,
    [string[]]$Processes = @('soffice.bin', 'soffice'),
    [int]$MinSize = 120
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class HstShot {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    public static string Describe(uint pid) {
        var parts = new List<string>();
        EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
            if (p == pid && IsWindowVisible(h)) { var c = new StringBuilder(256); GetClassName(h, c, 256); RECT r; GetWindowRect(h, out r);
                parts.Add(c + "@" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom); }
            return true; }, IntPtr.Zero);
        return string.Join(";", parts);
    }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out int v, int size);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
    // Blocks (x, y, w, h) inside rect whose visible window belongs to a process not in pids.
    public static List<int[]> Foreign(RECT r, HashSet<uint> pids, int step) {
        var outList = new List<int[]>();
        for (int y = r.Top; y < r.Bottom; y += step)
            for (int x = r.Left; x < r.Right; x += step) {
                var p = new POINT(); p.X = x + step / 2; p.Y = y + step / 2;
                IntPtr top = GetAncestor(WindowFromPoint(p), 2);
                uint pid = 0;
                if (top != IntPtr.Zero) GetWindowThreadProcessId(top, out pid);
                if (top == IntPtr.Zero || !pids.Contains(pid)) outList.Add(new int[] { x - r.Left, y - r.Top, step, step, (int)pid });
            }
        return outList;
    }
    public static List<IntPtr> Top() {
        var list = new List<IntPtr>();
        EnumWindows((h, l) => {
            int cloaked = 0;  // DWMWA_CLOAKED: "visible" but not drawn (suspended store apps, other desktops)
            DwmGetWindowAttribute(h, 14, out cloaked, 4);
            if (IsWindowVisible(h) && !IsIconic(h) && cloaked == 0) list.Add(h);
            return true; }, IntPtr.Zero);
        return list;
    }
}
'@
[void][HstShot]::SetProcessDpiAwarenessContext([IntPtr]-4)  # per-monitor v2: real pixels at the user's scaling
$allowed = $Processes | ForEach-Object { $_.ToLower() -replace '\.exe$', '' }
$pids = New-Object 'System.Collections.Generic.HashSet[uint32]'
Get-Process | Where-Object { $allowed -contains $_.ProcessName.ToLower() } | ForEach-Object { [void]$pids.Add([uint32]$_.Id) }
$records = @()
$index = 0
foreach ($hwnd in [HstShot]::Top()) {
    $procId = [uint32]0
    [void][HstShot]::GetWindowThreadProcessId($hwnd, [ref]$procId)
    if (-not $pids.Contains($procId)) { continue }
    $rect = New-Object HstShot+RECT
    if ([HstShot]::DwmGetWindowAttribute($hwnd, 9, [ref]$rect, 16) -ne 0) { [void][HstShot]::GetWindowRect($hwnd, [ref]$rect) }
    $width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
    if ($width -lt $MinSize -or $height -lt $MinSize) { continue }
    $title = New-Object System.Text.StringBuilder 512
    [void][HstShot]::GetWindowText($hwnd, $title, 512)
    $image = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($image)
    # Visibility is scanned before and after the copy (a window can slide in meanwhile) and both are masked.
    $foreign = [HstShot]::Foreign($rect, $pids, 4)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $width, $height))
    $foreign.AddRange([HstShot]::Foreign($rect, $pids, 4))
    foreach ($b in $foreign) { $graphics.FillRectangle([System.Drawing.Brushes]::Black, $b[0], $b[1], $b[2], $b[3]) }
    # Notification toasts animate in at the bottom right of the work area; that corner is always masked.
    $area = [System.Windows.Forms.Screen]::FromHandle($hwnd).WorkingArea
    $scale = [HstShot]::GetDpiForWindow($hwnd) / 96.0
    $toastW = [int](400 * $scale); $toastH = [int](300 * $scale)
    $graphics.FillRectangle([System.Drawing.Brushes]::Black, $area.Right - $toastW - $rect.Left, $area.Bottom - $toastH - $rect.Top, $toastW, $toastH)
    $owners = @($foreign | ForEach-Object { $_[4] } | Sort-Object -Unique | ForEach-Object { "$((Get-Process -Id $_ -ErrorAction SilentlyContinue).ProcessName) [$([HstShot]::Describe([uint32]$_))]" })
    $graphics.Dispose()
    $index++
    $file = "$Prefix-$index.png"
    $image.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $image.Dispose()
    $records += [ordered]@{ file = (Split-Path $file -Leaf); title = $title.ToString(); process = (Get-Process -Id $procId).ProcessName
        left = $rect.Left; top = $rect.Top; width = $width; height = $height; dpi = [HstShot]::GetDpiForWindow($hwnd)
        masked_fraction = [math]::Round($foreign.Count * 16 / [double]($width * $height), 3); masked_by = $owners }
}
$records | ConvertTo-Json -Depth 3 | Set-Content -Path "$Prefix.json" -Encoding UTF8
exit ($(if ($records.Count) { 0 } else { 2 }))
