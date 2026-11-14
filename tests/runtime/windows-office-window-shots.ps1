# SPDX-License-Identifier: AGPL-3.0-only
# PNG of every visible top-level window of the given processes through PrintWindow (works in a disconnected session,
# where screen copies fail), plus <Tag>.txt with each window's class, title and titled child windows.
# Usage: windows-office-window-shots.ps1 -Out DIR -Tag NAME [-Procs soffice.bin]
param([Parameter(Mandatory = $true)][string]$Out, [string]$Tag = 'state', [string]$Procs = 'soffice.bin')
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Drawing; using System.Drawing.Imaging;
public static class Snap {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  public static List<string> Run(uint[] pids, string prefix) {
    var res = new List<string>(); int n = 0;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (Array.IndexOf(pids, p) >= 0 && IsWindowVisible(h)) {
        var t = new StringBuilder(512); GetWindowText(h, t, 512); var c = new StringBuilder(256); GetClassName(h, c, 256);
        RECT r; GetWindowRect(h, out r); int w = r.R - r.L, ht = r.B - r.T;
        string line = n + "|" + h + "|" + c + "|" + t;
        EnumChildWindows(h, (ch, l2) => { if (IsWindowVisible(ch)) { var ct = new StringBuilder(512); GetWindowText(ch, ct, 512); var cc = new StringBuilder(256); GetClassName(ch, cc, 256);
            if (ct.Length > 0) line += "\n    " + ch + "|" + cc + "|" + ct; } return true; }, IntPtr.Zero);
        res.Add(line);
        if (w > 40 && ht > 40) using (var bmp = new Bitmap(w, ht)) { using (var g = Graphics.FromImage(bmp)) { IntPtr dc = g.GetHdc(); PrintWindow(h, dc, 2); g.ReleaseHdc(dc); } bmp.Save(prefix + "-" + n + ".png", ImageFormat.Png); }
        n++; }
      return true; }, IntPtr.Zero);
    return res;
  }
}
'@ -ReferencedAssemblies System.Drawing
$pids = [uint32[]]@(Get-Process -Name ($Procs -split ',') -EA SilentlyContinue | % { [uint32]$_.Id })
New-Item -ItemType Directory -Force $Out | Out-Null
[Snap]::Run($pids, "$Out\$Tag") | Set-Content -Encoding UTF8 "$Out\$Tag.txt"
