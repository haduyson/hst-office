# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: HST Office installs next to LibreOffice, and replaces the betas installed under LibreOffice's code.
#   smoke-install-paths.ps1 -Scenario libreoffice-first|upgrade-from-beta4 -HstMsi <msi> -FirstMsi <msi> -Out <dir>
#   libreoffice-first:  FirstMsi is the official LibreOffice MSI. After both installs, both products stay
#                       registered, each has one Programs and Features entry, and each office starts.
#   upgrade-from-beta4: FirstMsi is the HST Office beta.4 MSI (LibreOffice's UpgradeCode). After the new
#                       MSI, beta.4 is gone, one HST Office entry is left, and it starts from the same folder.
param(
    [Parameter(Mandatory=$true)][ValidateSet('libreoffice-first', 'upgrade-from-beta4')][string]$Scenario,
    [Parameter(Mandatory=$true)][string]$HstMsi,
    [Parameter(Mandatory=$true)][string]$FirstMsi,
    [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$HstCode = '{A1751BCB-2603-4428-A5DE-419B438ECFBC}'   # docs/BUILD_MATRIX.md, never changes
$LibreOfficeCode = '{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$installer = New-Object -ComObject WindowsInstaller.Installer

function Get-ComProperty($Object, [string]$Name, [object[]]$Arguments) {
    # Parameterized COM property; the leading comma keeps a returned list from being unrolled.
    , ($Object.GetType().InvokeMember($Name, [Reflection.BindingFlags]::GetProperty, $null, $Object, $Arguments))
}

function Get-Related([string]$UpgradeCode) {
    # One object per installed product registered under the UpgradeCode (Installer.RelatedProducts).
    $list = Get-ComProperty $installer 'RelatedProducts' @($UpgradeCode)
    $count = Get-ComProperty $list 'Count' @()
    for ($i = 0; $i -lt $count; $i++) {
        $code = Get-ComProperty $list 'Item' @($i)
        [pscustomobject]@{
            ProductCode = $code
            Name = Get-ComProperty $installer 'ProductInfo' @($code, 'ProductName')
            Version = Get-ComProperty $installer 'ProductInfo' @($code, 'VersionString')
            Location = Get-ComProperty $installer 'ProductInfo' @($code, 'InstallLocation')
        }
    }
}

function Get-ArpEntries([string]$Prefix) {
    # Programs and Features rows (64- and 32-bit views) whose name starts with the prefix.
    $roots = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    @($roots | Where-Object { Test-Path $_ } | ForEach-Object { Get-ItemProperty -Path (Join-Path $_ '*') } |
        Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName -like "$Prefix*" })
}

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "ok: $Message"
}

function Install-Msi([string]$Msi, [string]$Name) {
    $log = Join-Path $Out "$Name-install.log"
    $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList '/i', "`"$Msi`"", '/qn', '/norestart', '/l*v', "`"$log`""
    Assert ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) "$Name installs (msiexec exit $($p.ExitCode), log $log)"
}

function Show-State([string]$Label) {
    $state = [pscustomobject]@{
        label = $Label
        hst = @(Get-Related $HstCode)
        libreoffice_code = @(Get-Related $LibreOfficeCode)
        arp = @((@(Get-ArpEntries 'HST Office') + @(Get-ArpEntries 'LibreOffice')) | Select-Object DisplayName, DisplayVersion, PSChildName)
    }
    $json = $state | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath (Join-Path $Out "state-$Label.json") -Value $json -Encoding UTF8
    Write-Host $json
    return $state
}

function Assert-Starts([string]$Location, [string]$Expect, [string]$Name) {
    # soffice.com waits for the office and prints to the console; a headless conversion proves it starts and works.
    $exe = Join-Path $Location 'program\soffice.com'
    Assert (Test-Path -LiteralPath $exe) "$Name has $exe"
    $work = Join-Path $Out $Name
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    $profileUrl = 'file:///' + ((Join-Path $work 'profile') -replace '\\', '/')
    $version = & $exe --version 2>&1 | Out-String
    Write-Host "$Name --version: $($version.Trim())"
    Assert ($version -match $Expect) "$Name reports '$Expect' from its own program folder"
    $doc = Join-Path $work 'start.txt'
    Set-Content -LiteralPath $doc -Value "$Name started" -Encoding UTF8
    $p = Start-Process $exe -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $work 'convert.log') -RedirectStandardError (Join-Path $work 'convert.err') `
        -ArgumentList '--headless', '--norestore', "`"-env:UserInstallation=$profileUrl`"", '--convert-to', 'pdf', '--outdir', "`"$work`"", "`"$doc`""
    if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "FAIL: $Name did not finish a conversion within 10 minutes" }
    Assert (Test-Path -LiteralPath (Join-Path $work 'start.pdf')) "$Name starts and converts a document (exit $($p.ExitCode))"
}

if ($Scenario -eq 'libreoffice-first') {
    Install-Msi $FirstMsi 'libreoffice'
    $before = Show-State 'after-libreoffice'
    Assert ($before.libreoffice_code.Count -eq 1) 'LibreOffice is installed under its UpgradeCode'
    Install-Msi $HstMsi 'hst-office'
    $after = Show-State 'after-hst-office'
    Assert ($after.libreoffice_code.Count -eq 1 -and $after.libreoffice_code[0].ProductCode -eq $before.libreoffice_code[0].ProductCode) 'LibreOffice is still installed after HST Office'
    Assert ($after.hst.Count -eq 1) 'HST Office is installed under its own UpgradeCode'
    Assert ((Get-ArpEntries 'LibreOffice').Count -eq 1) 'one LibreOffice entry in Programs and Features'
    Assert ((Get-ArpEntries 'HST Office').Count -eq 1) 'one HST Office entry in Programs and Features'
    Assert ($after.hst[0].Location -and $after.hst[0].Location -ne $after.libreoffice_code[0].Location) 'separate install folders'
    Assert-Starts $after.libreoffice_code[0].Location 'LibreOffice 26\.8' 'libreoffice'
    Assert-Starts $after.hst[0].Location 'HST Office' 'hst-office'
} else {
    Install-Msi $FirstMsi 'hst-office-beta4'
    $before = Show-State 'after-beta4'
    Assert ($before.libreoffice_code.Count -eq 1 -and $before.libreoffice_code[0].Version -eq '1.0.0.1' -and $before.libreoffice_code[0].Name -like 'HST Office*') 'beta.4 is installed under LibreOffice''s UpgradeCode as 1.0.0.1'
    Install-Msi $HstMsi 'hst-office'
    $after = Show-State 'after-hst-office'
    Assert ($after.libreoffice_code.Count -eq 0) 'beta.4 was removed by the new installer'
    Assert ($after.hst.Count -eq 1) 'the new HST Office is installed under its own UpgradeCode'
    $arp = Get-ArpEntries 'HST Office'
    Assert ($arp.Count -eq 1 -and $arp[0].DisplayVersion -eq $after.hst[0].Version) "one HST Office entry in Programs and Features ($($arp.DisplayVersion -join ', '))"
    Assert ($after.hst[0].Location.TrimEnd('\') -eq $before.libreoffice_code[0].Location.TrimEnd('\')) 'installed in the beta.4 folder'
    Assert-Starts $after.hst[0].Location 'HST Office' 'hst-office'
}
Write-Host "Scenario $Scenario passed"
