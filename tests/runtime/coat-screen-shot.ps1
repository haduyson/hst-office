# SPDX-License-Identifier: AGPL-3.0-only
# PNG of a screen rectangle as the user sees it (the system's rounded corners, outline and shadow included; needs
# an active console session). Usage: coat-screen-shot.ps1 -Left <x> -Top <y> -Width <w> -Height <h> -Path <file.png>
param([Parameter(Mandatory = $true)][int]$Left, [Parameter(Mandatory = $true)][int]$Top,
      [Parameter(Mandatory = $true)][int]$Width, [Parameter(Mandatory = $true)][int]$Height,
      [Parameter(Mandatory = $true)][string]$Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class CoatScreenDpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[CoatScreenDpi]::SetProcessDPIAware() | Out-Null  # physical pixels, like the window rectangles passed in
New-Item -ItemType Directory -Force (Split-Path -Parent $Path) | Out-Null
$bmp = New-Object System.Drawing.Bitmap $Width, $Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
try { $g.CopyFromScreen($Left, $Top, 0, 0, $bmp.Size) } finally { $g.Dispose() }
$bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"saved $Path"
