# SPDX-License-Identifier: AGPL-3.0-only
# CI probe of sign-msi.ps1 on a disposable runner: a throwaway self-signed certificate, trusted on this runner
# only, stands in for the USB token. Signs the MSI with Windows PowerShell 5.1 (as on the signing PC), signs
# the result again (must change nothing), installs it and checks the installed programs' signatures and
# `soffice --version`. Logs go to -Out.
#   sign-msi-ci-probe.ps1 -Msi <unsigned.msi> -Out <dir>
param(
    [Parameter(Mandatory = $true)][string]$Msi,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Out | Out-Null
$signer = Join-Path $PSScriptRoot 'sign-msi.ps1'

$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=HST Office signing probe (throwaway)' `
    -CertStoreLocation Cert:\CurrentUser\My -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddDays(2)
$cer = Join-Path $env:RUNNER_TEMP 'probe-signing.cer'
Export-Certificate -Cert $cert -FilePath $cer | Out-Null
foreach ($store in 'Root', 'TrustedPublisher') { Import-Certificate -FilePath $cer -CertStoreLocation "Cert:\LocalMachine\$store" | Out-Null }

function Invoke-Signer([string]$In, [string]$Target) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $signer -Msi $In -OutMsi $Target -Thumbprint $cert.Thumbprint
    if ($LASTEXITCODE -ne 0) { throw "sign-msi.ps1 failed ($LASTEXITCODE) for $In" }
    Write-Host ("sign-msi.ps1 took {0:n0} s" -f $clock.Elapsed.TotalSeconds)
}

$signed = Join-Path $env:RUNNER_TEMP ('signed\' + (Split-Path $Msi -Leaf))
New-Item -ItemType Directory -Force (Split-Path $signed) | Out-Null
Invoke-Signer $Msi $signed
Copy-Item ([IO.Path]::ChangeExtension($signed, '.sign.log')) (Join-Path $Out 'first-run.sign.log')
$before = (Get-FileHash -LiteralPath $signed).Hash
Invoke-Signer $signed $signed
Copy-Item ([IO.Path]::ChangeExtension($signed, '.sign.log')) (Join-Path $Out 'second-run.sign.log')
if ((Get-FileHash -LiteralPath $signed).Hash -ne $before) { throw 'signing an already signed MSI changed it' }
Write-Host 'second run: unchanged'

$log = Join-Path $Out 'install.log'
$run = Start-Process msiexec.exe -ArgumentList "/i `"$signed`" /qn /norestart /l*v `"$log`"" -Wait -PassThru
if ($run.ExitCode -ne 0) { throw "install of the signed MSI failed: msiexec exit $($run.ExitCode)" }
$soffice = Get-ChildItem 'C:\Program Files' -Recurse -Depth 3 -Filter soffice.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $soffice) { throw 'soffice.exe not found after install' }
$program = $soffice.DirectoryName
$bad = @(Get-ChildItem $program -Recurse -File -Include *.exe, *.dll, *.pyd, *.com, *.bin | Where-Object {
        $sig = Get-AuthenticodeSignature -LiteralPath $_.FullName
        $sig.Status -ne 'Valid' -or "$($sig.SignatureType)" -ne 'Authenticode' })
$bad | Select-Object -First 20 | ForEach-Object { Write-Host "unsigned after install: $($_.FullName)" }
if ($bad.Count) { throw "$($bad.Count) installed programs are not validly signed" }
$version = & (Join-Path $program 'soffice.com') --version
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "soffice --version failed ($LASTEXITCODE)" }
Write-Host "installed and signed: $version"
Set-Content -LiteralPath (Join-Path $Out 'version.txt') -Value $version
