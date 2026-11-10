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
#                       HST Office alone writes none of LibreOffice's names, and a fresh install forces no reinstall.
#   uninstall-beta4-then-install: OtherMsi is the HST Office beta.4 MSI (LibreOffice's UpgradeCode). It is
#                       installed, then uninstalled with msiexec /x (the documented path for beta 1-4 users);
#                       leftovers are listed and fail the run only when they would break the new install. Then
#                       the new MSI installs: every file present, own UpgradeCode, keys, taskbar ids, it starts.
#   upgrade-from-beta4: the new MSI installed over beta.4 (users of beta 1-4, silent installs and the updater). Beta.4's
#                       executables carry a higher version (26.8.1.1) than the new ones (1.0.0.x); the new MSI detects
#                       the old beta (HSTLEGACYPRODUCTS) and forces its files in (REINSTALLMODE=amus) with the system
#                       C++ runtime left out (VC_REDIST=0). Beta.4 is removed, one HST Office entry is left, every file
#                       is present, the install log shows no C++ runtime component installed and no component
#                       disallowed, and it starts. Uninstalling it afterwards leaves no product and no program file.
#   upgrade-from-beta5: OtherMsi is beta.5 (HST Office's own UpgradeCode, 1.0.0.500). The new MSI replaces it
#                       without forcing a reinstall: one product and one Programs and Features entry, the new
#                       version, every file, its own keys, ProgIDs and automation names, and it starts.
#                       Two profiles used by beta.5 on this English Windows: one without a language choice shows the
#                       Vietnamese core UI after the upgrade; one where English was chosen keeps English and can
#                       switch to Vietnamese.
# App shortcuts (upgrade-from-beta4, upgrade-from-beta5): HST Writer, HST Sheets and HST Slides once each on the
# desktop and in the Start menu after the upgrade (check-app-shortcuts.ps1); none left after the uninstall of beta4's.
# UI language (every scenario that installs HST Office): the vi and en-US language packs are installed whatever
# the Windows display language (gm_Langpack_r_vi, also over a beta that left it out). hst-first also starts a
# fresh profile: Vietnamese core UI with no choice stored; English chosen wins after a restart; back to Vietnamese.
param(
    [Parameter(Mandatory=$true)][ValidateSet('libreoffice-first', 'hst-first', 'uninstall-beta4-then-install', 'upgrade-from-beta4', 'upgrade-from-beta5')][string]$Scenario,
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

function Get-MsiRows($Db, [string]$Sql, [int]$Columns) {
    $view = Invoke-Com $Db 'OpenView' @($Sql)
    Invoke-Com $view 'Execute' @() | Out-Null
    $rows = New-Object System.Collections.Generic.List[object]
    while ($true) {
        $rec = Invoke-Com $view 'Fetch' @()
        if (-not $rec) { break }
        # A plain [int] index: a pipeline $_ reaches InvokeMember as a PSObject and fails with DISP_E_TYPEMISMATCH.
        $row = New-Object string[] $Columns
        for ([int]$i = 1; $i -le $Columns; $i++) { $row[$i - 1] = "$(Get-ComProperty $rec 'StringData' @($i))" }
        $rows.Add($row)
    }
    Invoke-Com $view 'Close' @() | Out-Null
    return , $rows
}

function Assert-AllFiles([string]$Msi, [string]$ProductCode, [string]$Name) {
    # Every file the product should have under its install folder must be on disk; list all missing ones, then fail.
    # Expected: components Windows Installer registered for the product, plus unconditional components of a feature
    # installed locally (an upgrade can skip those, so they need not be registered). Folders come from the MSI's
    # Directory table; GAC assemblies and components outside the install folder (fonts, system files) are skipped.
    $db = Invoke-Com $installer 'OpenDatabase' @($Msi, 0)
    $root = "$(Get-ComProperty $installer 'ProductInfo' @($ProductCode, 'InstallLocation'))"
    if (-not $root.EndsWith('\')) { $root += '\' }
    $dirs = @{}
    foreach ($d in (Get-MsiRows $db 'SELECT `Directory`, `Directory_Parent`, `DefaultDir` FROM `Directory`' 3)) { $dirs[$d[0]] = $d }
    $resolved = @{ 'INSTALLLOCATION' = $root }
    function Resolve-Dir([string]$Id) {
        if ($resolved.ContainsKey($Id)) { return $resolved[$Id] }
        $row = $dirs[$Id]
        if (-not $row -or -not $row[1] -or $row[1] -eq $Id) { $resolved[$Id] = $null; return $null }
        $parent = Resolve-Dir $row[1]
        $target = ($row[2].Split(':')[0]).Split('|')[-1]
        $resolved[$Id] = if ($null -eq $parent) { $null } elseif ($target -eq '.') { $parent } else { $parent + $target + '\' }
        return $resolved[$Id]
    }
    $gac = @{}
    foreach ($a in (Get-MsiRows $db 'SELECT `Component_`, `File_Application` FROM `MsiAssembly`' 2)) { if (-not $a[1]) { $gac[$a[0]] = $true } }
    $local = @{}
    foreach ($f in (Get-MsiRows $db 'SELECT `Feature_`, `Component_` FROM `FeatureComponents`' 2)) {
        if ((Get-ComProperty $installer 'FeatureState' @($ProductCode, $f[0])) -eq 3) { $local[$f[1]] = $true }
    }
    $components = @{}
    foreach ($c in (Get-MsiRows $db 'SELECT `Component`, `ComponentId`, `Directory_`, `Condition` FROM `Component`' 4)) { $components[$c[0]] = $c }
    $missing = New-Object System.Collections.Generic.List[string]; $checked = 0; $skipped = 0; $unregistered = 0; $state = @{}
    foreach ($f in (Get-MsiRows $db 'SELECT `Component_`, `FileName` FROM `File`' 2)) {
        $c = $components[$f[0]]
        $dir = Resolve-Dir $c[2]
        if ($gac.ContainsKey($c[0]) -or -not $dir) { $skipped++; continue }
        if (-not $state.ContainsKey($c[0])) { $state[$c[0]] = "$(Get-ComProperty $installer 'ComponentPath' @($ProductCode, $c[1]))" -ne '' }
        $registered = $state[$c[0]]
        if (-not $registered -and ($c[3] -or -not $local.ContainsKey($c[0]))) { $skipped++; continue }
        if (-not $registered) { $unregistered++ }
        $checked++
        $path = $dir + $f[1].Split('|')[-1]
        if (-not (Test-Path -LiteralPath $path)) { $missing.Add($path) }
    }
    $list = Join-Path $Out "$Name-missing-files.txt"
    Set-Content -LiteralPath $list -Value ($missing -join "`r`n") -Encoding UTF8
    if ($missing.Count) {
        Write-Host "MISSING ($($missing.Count) of $checked files; list in $list):"
        $missing | ForEach-Object { Write-Host "  $_" }
    }
    Assert ($missing.Count -eq 0) "$Name has all $checked files under $root ($unregistered of them in unregistered components; $skipped files outside the folder, in the GAC or not selected)"
}

function Assert-InstallLog([string]$Msi, [string]$Name, [bool]$Legacy) {
    # The verbose install log of $Name. Over a beta 1-4 ($Legacy): the old beta was detected, REINSTALLMODE became
    # amus, no component of the C++ runtime merge modules was installed (it must never replace System32's) and no
    # component was disallowed because a higher-versioned key file is on disk. A fresh install changes neither.
    $log = Get-Content -LiteralPath (Join-Path $Out "$Name-install.log")
    $db = Invoke-Com $installer 'OpenDatabase' @($Msi, 0)
    $runtime = @{}
    foreach ($m in (Get-MsiRows $db 'SELECT `Component`, `ModuleID` FROM `ModuleComponents`' 2)) {
        if ($m[1] -like 'Microsoft_VC*') { $runtime[$m[0]] = $true }
    }
    $installed = @($log | ForEach-Object { if ($_ -match 'Component: (\S+); +Installed: \S+; +Request: \S+; +Action: Local') { $Matches[1] } } |
        Where-Object { $runtime.ContainsKey($_) })
    $disallowed = @($log | Where-Object { $_ -match 'Disallowing installation of component' })
    $forced = @($log | Where-Object { $_ -match "REINSTALLMODE property.*'amus'" })
    $detected = @($log | Where-Object { $_ -match 'HSTLEGACYPRODUCTS property' })
    Set-Content -LiteralPath (Join-Path $Out "$Name-log-findings.txt") -Encoding UTF8 -Value (
        @("runtime components installed: $($installed.Count)") + $installed + @("disallowed: $($disallowed.Count)") + $disallowed +
        @("reinstall mode: $($forced.Count)") + $forced + @("legacy detected: $($detected.Count)") + $detected)
    Write-Host "$Name log: $($runtime.Count) C++ runtime components in the MSI, $($installed.Count) installed, $($disallowed.Count) disallowed"
    $disallowed | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    if ($Legacy) {
        Assert ($detected.Count -gt 0) "$Name detected the old beta (HSTLEGACYPRODUCTS set)"
        Assert ($forced.Count -gt 0) "$Name forced its files in (REINSTALLMODE=amus)"
        Assert ($runtime.Count -gt 0 -and $installed.Count -eq 0) "$Name installed none of the $($runtime.Count) C++ runtime components ($($installed -join ', '))"
        Assert ($disallowed.Count -eq 0) "$Name disallowed no component ($($disallowed.Count) Disallowing lines)"
    } else {
        Assert ($detected.Count -eq 0 -and $forced.Count -eq 0) "$Name (fresh install) detected no old beta and forced no reinstall"
    }
}

function Get-ChosenAtInstall {
    # The "Dùng HST Office để mở tài liệu văn phòng" hint the first start reads (per-machine install), or $null.
    $key = Get-Item -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\HASON TECH\HST Office\DefaultApps' -ErrorAction SilentlyContinue
    if ($key) { $key.GetValue('ChosenAtInstall') } else { $null }
}

function Show-Leftovers([string]$Location, [string]$Label) {
    # Files left in the install folder and HST registry keys left after an uninstall; returns the files.
    $files = @(if ($Location -and (Test-Path -LiteralPath $Location)) { Get-ChildItem -LiteralPath $Location -Recurse -File -Force | ForEach-Object FullName })
    $keys = @('HKEY_LOCAL_MACHINE\SOFTWARE\HASON TECH\HST Office', 'HKEY_LOCAL_MACHINE\SOFTWARE\LibreOffice\Layers\HST Office',
              'HKEY_LOCAL_MACHINE\SOFTWARE\LibreOffice\HST Office') | Where-Object { Test-Path -LiteralPath "Registry::$_" }
    $leftovers = @($files) + @($keys | ForEach-Object { "registry: $_" })
    Set-Content -LiteralPath (Join-Path $Out "$Label-leftovers.txt") -Value ($leftovers -join "`r`n") -Encoding UTF8
    Write-Host "Leftovers after $($Label): $($leftovers.Count)"
    $leftovers | ForEach-Object { Write-Host "  $_" }
    return , $files
}

function Assert-BetaRemoved($State, [string]$Location, [string]$Label) {
    # After msiexec /x: list every leftover; fail only on those that would break a new install (a product still
    # registered, a Programs and Features entry, or executables left in the program folder).
    $files = Show-Leftovers $Location $Label
    Assert ($State.libreoffice_code.Count -eq 0 -and $State.hst.Count -eq 0) "no HST Office product is registered ($Label)"
    Assert ((Get-ArpEntries 'HST Office').Count -eq 0) 'no HST Office entry is left in Programs and Features'
    $binaries = @($files | Where-Object { $_ -match '\.(exe|dll|com|bin|pyd)$' })
    Assert ($binaries.Count -eq 0) "no program files left in $Location ($($binaries.Count): $($binaries -join ', '))"
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

function Assert-UiLanguagePacks([string]$Location, [string]$Name) {
    # Files of gm_Langpack_r_vi / gm_Langpack_r_en_US: the registrations and the vi translations of the core UI.
    foreach ($rel in 'share\registry\Langpack-vi.xcd', 'share\registry\Langpack-en-US.xcd', 'program\resource\vi\LC_MESSAGES\vcl.mo') {
        Assert (Test-Path -LiteralPath (Join-Path $Location $rel)) "$Name installed the UI language file $rel (English Windows)"
    }
}

function Invoke-UiLanguage([string]$Location, [string]$Label, [string]$ProfileDir, [string[]]$Arguments) {
    # One headless start of the installed office on $ProfileDir, with the office's own Python (uno).
    $python = Join-Path $Location 'program\python.exe'
    $script = Join-Path $PSScriptRoot '..\..\tests\runtime\check-windows-ui-language.py'
    $argv = @('-X', 'utf8', "`"$script`"", '--install', "`"$($Location.TrimEnd('\'))`"", '--profile', "`"$ProfileDir`"",
              '--label', $Label, '--out', "`"$(Join-Path $Out 'ui-language')`"") + $Arguments
    $p = Start-Process $python -PassThru -NoNewWindow -ArgumentList $argv `
        -RedirectStandardOutput (Join-Path $Out "ui-language-$Label.log") -RedirectStandardError (Join-Path $Out "ui-language-$Label.err")
    if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "FAIL: UI language check $Label did not finish within 10 minutes" }
    Get-Content -LiteralPath (Join-Path $Out "ui-language-$Label.log") | ForEach-Object { Write-Host "  $_" }
    Assert ($p.ExitCode -eq 0) "UI language check $Label (exit $($p.ExitCode), $Out\ui-language-$Label.err)"
}

if ($Scenario -in 'libreoffice-first', 'hst-first') {
    $first, $second = if ($Scenario -eq 'libreoffice-first') { 'libreoffice', 'hst-office' } else { 'hst-office', 'libreoffice' }
    $msi = @{ 'libreoffice' = $OtherMsi; 'hst-office' = $HstMsi }
    Install-Msi $msi[$first] $first
    $alone = Show-State "after-$first"
    if ($first -eq 'hst-office') {
        Assert-InstallLog $HstMsi 'hst-office' $false
        Assert ($null -eq (Get-ChosenAtInstall)) 'a silent install without HSTDEFAULTAPPS=1 leaves DefaultApps\ChosenAtInstall absent (box unticked)'
        Assert (-not $alone.registry.lo_odt_open -and -not $alone.registry.lo_install_path) 'HST Office alone writes no LibreOffice ProgID or install path'
        Assert-Owns $alone.registry 'hst' $alone.hst[0].Location
        Assert-NoLibreOfficeNames $alone.coexist
        Assert-HstCoexistKeys $alone.coexist $alone.hst[0].Location
        Assert-AllFiles $HstMsi $alone.hst[0].ProductCode 'hst-office'
        $loc = $alone.hst[0].Location
        Assert-UiLanguagePacks $loc 'hst-office'
        $fresh = Join-Path $Out 'profile-ui-language'
        Invoke-UiLanguage $loc 'fresh-default' $fresh @('--expect-stored', 'none', '--expect-ui', 'vi', '--need-vi', '--set', 'en-US')
        Invoke-UiLanguage $loc 'fresh-english' $fresh @('--expect-stored', 'en-US', '--expect-ui', 'en-US', '--set', 'vi')
        Invoke-UiLanguage $loc 'fresh-back-to-vi' $fresh @('--expect-stored', 'vi', '--expect-ui', 'vi')
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
} elseif ($Scenario -eq 'uninstall-beta4-then-install') {
    Install-Msi $OtherMsi 'hst-office-beta4'
    $before = Show-State 'after-beta4'
    Assert ($before.libreoffice_code.Count -eq 1 -and $before.libreoffice_code[0].Version -eq '1.0.0.1' -and $before.libreoffice_code[0].Name -like 'HST Office*') 'beta.4 is installed under LibreOffice''s UpgradeCode as 1.0.0.1'
    $beta = $before.libreoffice_code[0]
    Uninstall-Product $beta.ProductCode 'hst-office-beta4'
    $clean = Show-State 'after-beta4-uninstall'
    Assert-BetaRemoved $clean $beta.Location 'beta4-uninstall'
    Install-Msi $HstMsi 'hst-office'
    $after = Show-State 'after-hst-office'
    Assert ($after.hst.Count -eq 1 -and $after.libreoffice_code.Count -eq 0) 'the new HST Office is installed under its own UpgradeCode'
    $arp = Get-ArpEntries 'HST Office'
    Assert ($arp.Count -eq 1 -and $arp[0].DisplayVersion -eq $after.hst[0].Version) "one HST Office entry in Programs and Features ($($arp.DisplayVersion -join ', '))"
    $loc = $after.hst[0].Location
    Assert-NoLibreOfficeNames $after.coexist @('lo_software_key', 'lo_classes_software_key')
    Assert-HstCoexistKeys $after.coexist $loc
    Assert-Owns $after.registry 'hst' $loc
    Assert-AllFiles $HstMsi $after.hst[0].ProductCode 'hst-office-after-beta4-uninstall'
    Assert-UiLanguagePacks $loc 'hst-office-after-beta4-uninstall'
    & (Join-Path $PSScriptRoot 'check-app-user-model-ids.ps1') -Install $loc
    Assert-Starts $loc 'HST Office' 'hst-office'
} elseif ($Scenario -eq 'upgrade-from-beta5') {
    Install-Msi $OtherMsi 'hst-office-beta5'
    $before = Show-State 'after-beta5'
    Assert ($before.hst.Count -eq 1 -and $before.hst[0].Version -eq '1.0.0.500' -and $before.libreoffice_code.Count -eq 0) 'beta.5 is installed under HST Office''s UpgradeCode as 1.0.0.500'
    # Profiles of beta.5 users on this English Windows: one never chose a language, one chose English.
    $plain, $english = (Join-Path $Out 'profile-beta5-no-choice'), (Join-Path $Out 'profile-beta5-english')
    Invoke-UiLanguage $before.hst[0].Location 'beta5-no-choice' $plain @()
    Invoke-UiLanguage $before.hst[0].Location 'beta5-english' $english @('--set', 'en-US')
    Install-Msi $HstMsi 'hst-office'
    Assert-InstallLog $HstMsi 'hst-office' $false
    $after = Show-State 'after-hst-office'
    Assert ($after.hst.Count -eq 1 -and $after.hst[0].ProductCode -ne $before.hst[0].ProductCode) "beta.5 was replaced: one HST Office product, the new one ($($after.hst.Version -join ', '))"
    $arp = Get-ArpEntries 'HST Office'
    Assert ($arp.Count -eq 1 -and $arp[0].DisplayVersion -eq $after.hst[0].Version) "one HST Office entry in Programs and Features ($($arp.DisplayVersion -join ', '))"
    $loc = $after.hst[0].Location
    Assert ($loc.TrimEnd('\') -eq $before.hst[0].Location.TrimEnd('\')) 'installed in the beta.5 folder'
    Assert-NoLibreOfficeNames $after.coexist
    Assert-HstCoexistKeys $after.coexist $loc
    Assert-Owns $after.registry 'hst' $loc
    Assert-AllFiles $HstMsi $after.hst[0].ProductCode 'hst-office-after-beta5'
    Assert-UiLanguagePacks $loc 'hst-office-after-beta5'
    # One HST Writer, HST Sheets and HST Slides each on the desktop and in the Start menu after the upgrade.
    & (Join-Path $PSScriptRoot 'check-app-shortcuts.ps1') -Expect installed -Install $loc
    Invoke-UiLanguage $loc 'upgraded-no-choice' $plain @('--expect-stored', 'none', '--expect-ui', 'vi', '--need-vi')
    Invoke-UiLanguage $loc 'upgraded-english' $english @('--expect-stored', 'en-US', '--expect-ui', 'en-US', '--need-vi', '--set', 'vi')
    Invoke-UiLanguage $loc 'upgraded-switched-to-vi' $english @('--expect-stored', 'vi', '--expect-ui', 'vi')
    Assert-Starts $loc 'HST Office' 'hst-office'
} else {
    Install-Msi $OtherMsi 'hst-office-beta4'
    $before = Show-State 'after-beta4'
    Assert ($before.libreoffice_code.Count -eq 1 -and $before.libreoffice_code[0].Version -eq '1.0.0.1') 'beta.4 is installed under LibreOffice''s UpgradeCode as 1.0.0.1'
    Install-Msi $HstMsi 'hst-office'
    Assert-InstallLog $HstMsi 'hst-office' $true
    $after = Show-State 'after-hst-office'
    Assert ($after.libreoffice_code.Count -eq 0) 'beta.4 was removed by the new installer'
    Assert ($after.hst.Count -eq 1) 'the new HST Office is installed under its own UpgradeCode'
    $arp = Get-ArpEntries 'HST Office'
    Assert ($arp.Count -eq 1 -and $arp[0].DisplayVersion -eq $after.hst[0].Version) "one HST Office entry in Programs and Features ($($arp.DisplayVersion -join ', '))"
    $loc = $after.hst[0].Location
    Assert ($loc.TrimEnd('\') -eq $before.libreoffice_code[0].Location.TrimEnd('\')) 'installed in the beta.4 folder'
    Assert-NoLibreOfficeNames $after.coexist @('lo_software_key', 'lo_classes_software_key')
    Assert-HstCoexistKeys $after.coexist $loc
    Assert-Owns $after.registry 'hst' $loc
    Assert-AllFiles $HstMsi $after.hst[0].ProductCode 'hst-office-after-upgrade'
    Assert-UiLanguagePacks $loc 'hst-office-after-upgrade'
    & (Join-Path $PSScriptRoot 'check-app-shortcuts.ps1') -Expect installed -Install $loc
    Assert-Starts $loc 'HST Office' 'hst-office'
    # Uninstalling the upgraded install removes it completely, as for a fresh install.
    Uninstall-Product $after.hst[0].ProductCode 'hst-office-upgraded'
    $gone = Show-State 'after-upgraded-uninstall'
    Assert-BetaRemoved $gone $loc 'upgraded-uninstall'
    & (Join-Path $PSScriptRoot 'check-app-shortcuts.ps1') -Expect removed
}
Write-Host "Scenario $Scenario passed"
