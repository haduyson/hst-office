# SPDX-License-Identifier: AGPL-3.0-only
# PNG of one window through PrintWindow with full content (works in a disconnected session too, where screen copies
# fail). Usage: coat-window-shot.ps1 -Hwnd <decimal handle> -Path <file.png>
param([Parameter(Mandatory = $true)][long]$Hwnd, [Parameter(Mandatory = $true)][string]$Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Drawing; using System.Drawing.Imaging;
public static class CoatShot {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
  public static void Save(IntPtr h, string path) {
    // physical pixels: without this, above 100 % scaling the rectangle is logical and the shot is cropped
    SetProcessDPIAware();
    RECT r; if (!GetWindowRect(h, out r)) throw new Exception("no such window");
    int w = r.R - r.L, ht = r.B - r.T; if (w <= 0 || ht <= 0) throw new Exception("empty window");
    using (var bmp = new Bitmap(w, ht, PixelFormat.Format32bppArgb)) {
      using (var g = Graphics.FromImage(bmp)) {
        IntPtr dc = g.GetHdc();
        try { if (!PrintWindow(h, dc, 2)) throw new Exception("PrintWindow failed"); } finally { g.ReleaseHdc(dc); }
      }
      bmp.Save(path, ImageFormat.Png);
    }
  }
}
'@ -ReferencedAssemblies System.Drawing
New-Item -ItemType Directory -Force (Split-Path -Parent $Path) | Out-Null
[CoatShot]::Save([IntPtr]$Hwnd, $Path)
"saved $Path"
