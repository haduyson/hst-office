# SPDX-License-Identifier: AGPL-3.0-only
# Authenticode-sign an HST Office MSI completely: every PE file inside the embedded cabinets, every PE in the
# Binary table (custom-action DLLs) and finally the MSI itself, each with SHA-256 and an RFC 3161 timestamp.
# Built-in tools only (no SDK, no admin rights): msi.dll and mssign32.dll through the helper in
# msi-authenticode-native.cs, expand.exe and makecab.exe for the cabinets, msiexec /a for the check.
#
#   sign-msi.ps1 -Msi <unsigned.msi> -OutMsi <signed.msi> [-Thumbprint <hex>] [-TimestampUrl <url>]
#   sign-msi.ps1 -Msi <signed.msi> -VerifyOnly            (no certificate or token needed)
#
# The certificate comes from Cert:\CurrentUser\My (code signing, with a private key; a USB token's certificate
# appears there while the token is connected in this user's session). The key provider asks for the token PIN
# itself; this script never reads, stores or prints a PIN or key. Files that already carry a valid embedded
# signature (vendor runtimes, or a previous run) are left as they are, so running it again on its own output
# changes nothing. Exit code 0 only when the final check finds every PE and the MSI validly signed and timestamped.
# Docs: docs/WINDOWS_SIGNING.md
param(
    [Parameter(Mandatory = $true)][string]$Msi,
    [string]$OutMsi,
    [string]$Thumbprint,
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [string]$Description = 'HST Office',
    [string]$InfoUrl = 'https://office.hasontech.vn',
    [string]$WorkDir,
    [ValidateSet('LZX', 'MSZIP')][string]$Compression = 'LZX',
    [switch]$VerifyOnly,
    [switch]$KeepWork
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
# Background priority: the signing PC may be in use (makecab and expand inherit it).
try { [Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal' } catch { }
Add-Type -Path (Join-Path $PSScriptRoot 'msi-authenticode-native.cs')
. (Join-Path $PSScriptRoot 'sign-msi-steps.ps1')

$Msi = (Resolve-Path -LiteralPath $Msi).Path
if (-not $OutMsi) { $OutMsi = if ($VerifyOnly) { $Msi } else { [IO.Path]::ChangeExtension($Msi, $null).TrimEnd('.') + '-signed.msi' } }
$OutMsi = [IO.Path]::GetFullPath($OutMsi)
if (-not $WorkDir) { $WorkDir = Join-Path (Split-Path $OutMsi) ('sign-work-' + [IO.Path]::GetFileNameWithoutExtension($OutMsi)) }
$WorkDir = [IO.Path]::GetFullPath($WorkDir)
if (Test-Path -LiteralPath $WorkDir) { Remove-Item -LiteralPath $WorkDir -Recurse -Force }
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$script:LogPath = Join-Path (Split-Path $OutMsi) ([IO.Path]::GetFileNameWithoutExtension($OutMsi) + '.sign.log')
Set-Content -LiteralPath $script:LogPath -Value "sign-msi $(Get-Date -Format s) input=$Msi output=$OutMsi" -Encoding UTF8
$clock = [Diagnostics.Stopwatch]::StartNew()

if (-not $VerifyOnly) {
    if (-not $TimestampUrl.StartsWith('http')) { throw "the timestamp URL must be http(s): $TimestampUrl" }
    $cert = Get-SigningCertificate $Thumbprint
    if ($OutMsi -ne $Msi) { Copy-Item -LiteralPath $Msi -Destination $OutMsi -Force }
    Initialize-Signer $cert $TimestampUrl $Description $InfoUrl
    $db = New-Object HstMsiDb $OutMsi, $true
    try {
        $changed = Invoke-CabinetSigning $db $WorkDir $Compression
        $changed += Invoke-BinaryTableSigning $db $WorkDir
        $db.Commit()
    } finally { $db.Dispose() }
    $msiSig = Get-AuthenticodeSignature -LiteralPath $OutMsi
    if ($changed -gt 0 -or -not (Test-TimestampedSignature $msiSig)) {
        Invoke-Sign $OutMsi
        Write-Log "signed the MSI ($changed embedded files changed)"
    } else { Write-Log 'the MSI and its contents were already signed: nothing changed' }
    Write-Log ("signing took {0:n0} s; {1} files signed in total" -f $clock.Elapsed.TotalSeconds, $script:SignedCount)
}

$failures = Test-SignedMsi $OutMsi (Join-Path $WorkDir 'verify')
Write-Log ("done in {0:n0} s: {1}" -f $clock.Elapsed.TotalSeconds, $(if ($failures) { "$failures FAILURES" } else { 'all signatures valid' }))
if (-not $KeepWork -and -not $failures) { Remove-Item -LiteralPath $WorkDir -Recurse -Force }
if ($failures) { exit 1 }
exit 0
