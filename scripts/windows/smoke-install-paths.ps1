# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: HST Office installs next to LibreOffice, and replaces the betas installed under LibreOffice's code.
#   smoke-install-paths.ps1 -Scenario <name> -HstMsi <msi> -OtherMsi <msi> -Out <dir>
#   libreoffice-first:  OtherMsi is the official LibreOffice MSI, installed first, then HST Office. Both stay
#                       registered with one Programs and Features entry each, keep their own ProgIDs, open
#                       commands and UNO install path, and both start. HST Office is then uninstalled:
#                       LibreOffice keeps its ProgIDs, .docx and install path, and still starts.
#                       LibreOffice's App Paths, vnd.libreoffice.command scheme, Explorer extension class ids
#                       and legacy ProgIDs are unchanged by HST Office's install and uninstall
#                       (smoke-coexist-registry.ps1).
#   hst-first:          the same with HST Office first; LibreOffice is uninstalled and HST Office keeps its own;
#                       HST Office alone writes none of LibreOffice's names.
#   upgrade-from-beta4: OtherMsi is the HST Office beta.4 MSI (LibreOffice's UpgradeCode). After the new
#                       MSI, beta.4 is gone, one HST Office entry is left, and it starts from the same folder.
param(
    [Parameter(Mandatory=$true)][ValidateSet('libreoffice-first', 'hst-first', 'upgrade-from-beta4')][string]$Scenario,
    [Parameter(Mandatory=$true)][string]$HstMsi,
    [Parameter(Mandatory=$true)][string]$OtherMsi,
    [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$HstCode = '{A1751BCB-2603-4428-A5DE-419B438ECFBC}'   # docs/BUILD_MATRIX.md, never changes
$LibreOfficeCode = '{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$installer = New-Object -ComObject WindowsInstaller.Installer
. (Join-Path $PSScriptRoot 'smoke-coexist-registry.ps1')

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
    # Wait for msiexec itself only: -Wait would also wait for applications the Restart Manager restarts (Explorer).
    $p = Start-Process msiexec.exe -PassThru -ArgumentList '/i', "`"$Msi`"", '/qn', '/norestart', '/l*v', "`"$log`""
    if (-not $p.WaitForExit(1200000)) { throw "FAIL: $Name did not finish installing within 20 minutes (log $log)" }
    Assert ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) "$Name installs (msiexec exit $($p.ExitCode), log $log)"
}

function Get-RegDefault([string]$Key) {
    # Default value of a registry key, or $null when the key or value is missing.
    $item = Get-Item -LiteralPath "Registry::$Key" -ErrorAction SilentlyContinue
    if ($item) { $item.GetValue('') } else { $null }
}

function Get-Associations {
    # What each suite registered: ProgID open commands, the .odt/.docx defaults and the UNO install paths.
    [ordered]@{
        lo_odt_open = Get-RegDefault 'HKEY_CLASSES_ROOT\LibreOffice.WriterDocument.1\shell\open\command'
        lo_docx_open = Get-RegDefault 'HKEY_CLASSES_ROOT\LibreOffice.Docx\shell\open\command'
        hst_odt_open = Get-RegDefault 'HKEY_CLASSES_ROOT\HSTOffice.WriterDocument.1\shell\open\command'
        hst_docx_open = Get-RegDefault 'HKEY_CLASSES_ROOT\HSTOffice.Docx\shell\open\command'
        odt_default = Get-RegDefault 'HKEY_CLASSES_ROOT\.odt'
        docx_default = Get-RegDefault 'HKEY_CLASSES_ROOT\.docx'
        lo_install_path = Get-RegDefault 'HKEY_LOCAL_MACHINE\SOFTWARE\LibreOffice\UNO\InstallPath'
        hst_install_path = Get-RegDefault 'HKEY_LOCAL_MACHINE\SOFTWARE\HASON TECH\HST Office\UNO\InstallPath'
    }
}

function Assert-Owns([System.Collections.IDictionary]$Reg, [string]$Suite, [string]$Location) {
    # The suite's ProgIDs open its own program and its UNO install path is its own program folder.
    $program = (Join-Path $Location 'program').TrimEnd('\')
    foreach ($k in "$($Suite)_odt_open", "$($Suite)_docx_open") {
        Assert ($Reg[$k] -and $Reg[$k].IndexOf($program, [StringComparison]::OrdinalIgnoreCase) -ge 0) "$k opens $program ($($Reg[$k]))"
    }
    Assert ($Reg["$($Suite)_install_path"] -and $Reg["$($Suite)_install_path"].TrimEnd('\') -ieq $program) "$($Suite)_install_path is $program ($($Reg["$($Suite)_install_path"]))"
}

function Uninstall-Product([string]$ProductCode, [string]$Name) {
    $log = Join-Path $Out "$Name-uninstall.log"
    $p = Start-Process msiexec.exe -PassThru -ArgumentList '/x', $ProductCode, '/qn', '/norestart', '/l*v', "`"$log`""
    if (-not $p.WaitForExit(1200000)) { throw "FAIL: $Name did not finish uninstalling within 20 minutes (log $log)" }
    Assert ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) "$Name uninstalls (msiexec exit $($p.ExitCode), log $log)"
}

function Show-State([string]$Label) {
    $state = [pscustomobject]@{
        label = $Label
        hst = @(Get-Related $HstCode)
        libreoffice_code = @(Get-Related $LibreOfficeCode)
        arp = @((@(Get-ArpEntries 'HST Office') + @(Get-ArpEntries 'LibreOffice')) | Select-Object DisplayName, DisplayVersion, PSChildName)
        registry = Get-Associations
        coexist = Get-CoexistRegistry
    }
    $json = $state | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath (Join-Path $Out "state-$Label.json") -Value $json -Encoding UTF8
    Write-Host $json
    return $state
}

function Invoke-Com($Object, [string]$Name, [object[]]$Arguments) {
    , ($Object.GetType().InvokeMember($Name, [Reflection.BindingFlags]::InvokeMethod, $null, $Object, $Arguments))
}

function Assert-AllFiles([string]$Msi, [string]$ProductCode, [string]$Name) {
    # Every file of every component the product registered must be on disk; list all missing ones, then fail.
    $db = Invoke-Com $installer 'OpenDatabase' @($Msi, 0)
    $view = Invoke-Com $db 'OpenView' @('SELECT `File`.`FileName`, `Component`.`ComponentId` FROM `File`, `Component` WHERE `File`.`Component_` = `Component`.`Component`')
    Invoke-Com $view 'Execute' @() | Out-Null
    $dirs = @{}; $missing = New-Object System.Collections.Generic.List[string]; $checked = 0; $unregistered = 0
    while ($true) {
        $rec = Invoke-Com $view 'Fetch' @()
        if (-not $rec) { break }
        $file = (Get-ComProperty $rec 'StringData' @(1)).Split('|')[-1]
        $id = Get-ComProperty $rec 'StringData' @(2)
        if (-not $dirs.ContainsKey($id)) {
            $kp = "$(Get-ComProperty $installer 'ComponentPath' @($ProductCode, $id))"
            # A file key path gives its folder; a folder key path ends with '\'; registry key paths and unregistered components give none.
            $dirs[$id] = if ($kp -match '^[A-Za-z]:\\.*\\$') { $kp } elseif ($kp -match '^[A-Za-z]:\\') { (Split-Path -Parent $kp) + '\' } else { '' }
        }
        if (-not $dirs[$id]) { $unregistered++; continue }
        $checked++
        $path = $dirs[$id] + $file
        if (-not (Test-Path -LiteralPath $path)) { $missing.Add($path) }
    }
    Invoke-Com $view 'Close' @() | Out-Null
    $list = Join-Path $Out "$Name-missing-files.txt"
    Set-Content -LiteralPath $list -Value ($missing -join "`r`n") -Encoding UTF8
    if ($missing.Count) {
        Write-Host "MISSING ($($missing.Count) of $checked files of registered components; list in $list):"
        $missing | ForEach-Object { Write-Host "  $_" }
    }
    Assert ($missing.Count -eq 0) "$Name has all $checked files of its registered components ($unregistered files in components not installed here)"
}

function Assert-Starts([string]$Location, [string]$Expect, [string]$Name) {
    # soffice.com waits for the office and prints to the console; a headless conversion proves it starts and works.
    $exe = Join-Path $Location 'program\soffice.com'
    Assert (Test-Path -LiteralPath $exe) "$Name has $exe"
    $work = Join-Path $Out $Name
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    $profileUrl = 'file:///' + ((Join-Path $work 'profile') -replace '\\', '/')
    $v = Start-Process $exe -PassThru -NoNewWindow -ArgumentList '--version' -RedirectStandardOutput (Join-Path $work 'version.txt') -RedirectStandardError (Join-Path $work 'version.err')
    if (-not $v.WaitForExit(120000)) { $v.Kill(); throw "FAIL: $Name --version did not return within 2 minutes" }
    $version = Get-Content -LiteralPath (Join-Path $work 'version.txt') -Raw
    $version = "$version".Trim()
    Write-Host "$Name --version: $version"
    Assert ($version -match $Expect) "$Name reports '$Expect' from its own program folder"
    $doc = Join-Path $work 'start.txt'
    Set-Content -LiteralPath $doc -Value "$Name started" -Encoding UTF8
    $p = Start-Process $exe -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $work 'convert.log') -RedirectStandardError (Join-Path $work 'convert.err') `
        -ArgumentList '--headless', '--norestore', "`"-env:UserInstallation=$profileUrl`"", '--convert-to', 'pdf', '--outdir', "`"$work`"", "`"$doc`""
    if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "FAIL: $Name did not finish a conversion within 10 minutes" }
    Assert (Test-Path -LiteralPath (Join-Path $work 'start.pdf')) "$Name starts and converts a document (exit $($p.ExitCode))"
}

if ($Scenario -ne 'upgrade-from-beta4') {
    $first, $second = if ($Scenario -eq 'libreoffice-first') { 'libreoffice', 'hst-office' } else { 'hst-office', 'libreoffice' }
    $msi = @{ 'libreoffice' = $OtherMsi; 'hst-office' = $HstMsi }
    Install-Msi $msi[$first] $first
    $alone = Show-State "after-$first"
    if ($first -eq 'hst-office') {
        Assert (-not $alone.registry.lo_odt_open -and -not $alone.registry.lo_install_path) 'HST Office alone writes no LibreOffice ProgID or install path'
        Assert-Owns $alone.registry 'hst' $alone.hst[0].Location
        Assert-NoLibreOfficeNames $alone.coexist
        Assert-HstCoexistKeys $alone.coexist $alone.hst[0].Location
        Assert-AllFiles $HstMsi $alone.hst[0].ProductCode 'hst-office'
    }
    Install-Msi $msi[$second] $second
    $both = Show-State 'after-both'
    Assert ($both.libreoffice_code.Count -eq 1 -and $both.libreoffice_code[0].Name -like 'LibreOffice*') 'LibreOffice is installed under its UpgradeCode'
    Assert ($both.hst.Count -eq 1) 'HST Office is installed under its own UpgradeCode'
    Assert ((Get-ArpEntries 'LibreOffice').Count -eq 1) 'one LibreOffice entry in Programs and Features'
    Assert ((Get-ArpEntries 'HST Office').Count -eq 1) 'one HST Office entry in Programs and Features'
    $lo, $hst = $both.libreoffice_code[0].Location, $both.hst[0].Location
    Assert ($hst -and $hst -ne $lo) 'separate install folders'
    Assert-Owns $both.registry 'lo' $lo
    Assert-Owns $both.registry 'hst' $hst
    Assert-LibreOfficeRegistered $both.coexist $lo
    Assert-HstCoexistKeys $both.coexist $hst
    if ($first -eq 'libreoffice') { Assert-Kept $alone.coexist $both.coexist 'lo_' "installing HST Office leaves LibreOffice's App Paths, URI scheme, class ids and legacy ProgIDs" }
    else { Assert-Kept $alone.coexist $both.coexist 'hst_' "installing LibreOffice leaves HST Office's legacy ProgIDs, Office URI ProgID and class ids" }
    # .docx: the second suite never takes a format the first already owns.
    Write-Host ".docx default after $($first): $($alone.registry.docx_default)"
    Assert ($both.registry.docx_default -eq $alone.registry.docx_default) ".docx keeps its owner after the second install ($($both.registry.docx_default))"
    Assert-AllFiles $HstMsi $both.hst[0].ProductCode 'hst-office-with-libreoffice'
    Assert-Starts $lo 'LibreOffice 26\.8' 'libreoffice'
    Assert-Starts $hst 'HST Office' 'hst-office'
    # Uninstall the second suite: the first keeps everything it registered.
    $code = if ($second -eq 'hst-office') { $both.hst[0].ProductCode } else { $both.libreoffice_code[0].ProductCode }
    Uninstall-Product $code $second
    $left = Show-State "after-uninstall-$second"
    if ($first -eq 'libreoffice') {
        Assert ($left.hst.Count -eq 0 -and $left.libreoffice_code.Count -eq 1) 'only LibreOffice is left'
        Assert-Owns $left.registry 'lo' $lo
        Assert-Kept $alone.coexist $left.coexist 'lo_' "uninstalling HST Office leaves LibreOffice's App Paths, URI scheme, class ids and legacy ProgIDs"
        Assert-Kept $alone.coexist $left.coexist 'hst_' 'uninstalling HST Office removes its own class ids and ProgIDs'
        Assert ($left.registry.docx_default -eq $alone.registry.docx_default) ".docx keeps LibreOffice's setting ($($left.registry.docx_default))"
        Assert-Starts $lo 'LibreOffice 26\.8' 'libreoffice-after-uninstall'
    } else {
        Assert ($left.libreoffice_code.Count -eq 0 -and $left.hst.Count -eq 1) 'only HST Office is left'
        Assert-Owns $left.registry 'hst' $hst
        Assert-AllFiles $HstMsi $left.hst[0].ProductCode 'hst-office-after-uninstall'
        Assert-Kept $alone.coexist $left.coexist 'hst_' "uninstalling LibreOffice leaves HST Office's legacy ProgIDs, Office URI ProgID and class ids"
        Assert ($left.registry.docx_default -eq $alone.registry.docx_default) ".docx keeps HST Office's setting ($($left.registry.docx_default))"
        Assert-Starts $hst 'HST Office' 'hst-office-after-uninstall'
    }
    # .odt: each suite registers ODF unconditionally, so the last installer owns it and an uninstall clears it (recorded only).
    Write-Host ".odt default: alone=$($alone.registry.odt_default) both=$($both.registry.odt_default) after uninstall=$($left.registry.odt_default)"
} else {
    Install-Msi $OtherMsi 'hst-office-beta4'
    $before = Show-State 'after-beta4'
    Assert ($before.libreoffice_code.Count -eq 1 -and $before.libreoffice_code[0].Version -eq '1.0.0.1' -and $before.libreoffice_code[0].Name -like 'HST Office*') 'beta.4 is installed under LibreOffice''s UpgradeCode as 1.0.0.1'
    Install-Msi $HstMsi 'hst-office'
    $after = Show-State 'after-hst-office'
    Assert ($after.libreoffice_code.Count -eq 0) 'beta.4 was removed by the new installer'
    Assert ($after.hst.Count -eq 1) 'the new HST Office is installed under its own UpgradeCode'
    $arp = Get-ArpEntries 'HST Office'
    Assert ($arp.Count -eq 1 -and $arp[0].DisplayVersion -eq $after.hst[0].Version) "one HST Office entry in Programs and Features ($($arp.DisplayVersion -join ', '))"
    Assert ($after.hst[0].Location.TrimEnd('\') -eq $before.libreoffice_code[0].Location.TrimEnd('\')) 'installed in the beta.4 folder'
    # beta.4 wrote under Software\LibreOffice; its removal deletes the values, an empty key may stay behind.
    Assert-NoLibreOfficeNames $after.coexist @('lo_software_key', 'lo_classes_software_key')
    Assert-HstCoexistKeys $after.coexist $after.hst[0].Location
    Assert-AllFiles $HstMsi $after.hst[0].ProductCode 'hst-office-after-upgrade'
    Assert-Starts $after.hst[0].Location 'HST Office' 'hst-office'
}
Write-Host "Scenario $Scenario passed"
