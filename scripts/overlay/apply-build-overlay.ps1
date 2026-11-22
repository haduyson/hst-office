# SPDX-License-Identifier: AGPL-3.0-only
<#
TEST ONLY: copy a module-build patch overlay (scripts/windows/hst4-build.ps1 -Modules) over an administrative
install image of a reference HST Office MSI. Never use the result as a release or on a user's machine.
  msiexec /a HSTOffice_<release>_Win_x86-64_en-US_vi.msi /qn TARGETDIR=C:\hst-test\ref
  powershell -File apply-build-overlay.ps1 -Image C:\hst-test\ref      (run from the unpacked overlay folder)
The install root is the folder holding program\soffice.exe under -Image.
#>
param([Parameter(Mandatory)][string]$Image)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$files = Join-Path $PSScriptRoot 'files'
$list = @(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'FILES.txt') | Where-Object { $_ })
foreach ($line in Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SHA256SUMS')) {
    $hash, $rel = $line -split '\s+\*?', 2
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $files $rel)).Hash -ne $hash.ToUpper()) { throw "checksum mismatch: $rel" }
}
$roots = @(Get-ChildItem -LiteralPath $Image -Recurse -Depth 4 -Filter soffice.exe -File |
        Where-Object { $_.Directory.Name -eq 'program' } | ForEach-Object { $_.Directory.Parent.FullName })
if ($roots.Count -ne 1) { throw "expected one program\soffice.exe under $Image, found $($roots.Count)" }
$new = 0
foreach ($rel in $list) {
    $dest = Join-Path $roots[0] $rel
    if (-not (Test-Path -LiteralPath $dest)) { "new file (not in the reference image): $rel"; $new++ }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath (Join-Path $files $rel) -Destination $dest -Force
}
"applied $($list.Count) files onto $($roots[0]) ($new new); TEST ONLY"
