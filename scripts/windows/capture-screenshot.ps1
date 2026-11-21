# SPDX-License-Identifier: AGPL-3.0-only
# Save a PNG of the whole primary screen. Usage: pwsh -File capture-screenshot.ps1 -Path out.png [-WithCursor]
# -WithCursor draws the mouse pointer in (a screen copy leaves it out), for checks that move it.
param([Parameter(Mandatory = $true)][string]$Path, [switch]$WithCursor)
# DPI-aware first: otherwise, with a display scaling above 100 %, the screen is read in logical pixels (1536 x 864 for
# 1920 x 1080 at 125 %) while windows and accessible boxes are in physical ones
Add-Type -Namespace HstShot -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[void][HstShot.Dpi]::SetProcessDPIAware()
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
if ($WithCursor) {
    $at = [System.Windows.Forms.Cursor]::Position
    $hot = [System.Windows.Forms.Cursors]::Default.HotSpot
    $spot = New-Object System.Drawing.Rectangle (($at.X - $bounds.X - $hot.X), ($at.Y - $bounds.Y - $hot.Y), 32, 32)
    [System.Windows.Forms.Cursors]::Default.Draw($graphics, $spot)
}
$bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose(); $bitmap.Dispose()
