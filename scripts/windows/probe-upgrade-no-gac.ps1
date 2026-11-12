# SPDX-License-Identifier: AGPL-3.0-only
# Upgrade probe: a new HST Office MSI over 1.0.1 leaves no CLI-UNO assembly of its own in the .NET GAC, and VBA still runs.
#   probe-upgrade-no-gac.ps1 -OldMsi <1.0.1 msi> -NewMsi <msi> -Out <dir> [-LibreOfficeMsi <LibreOffice msi>]
# 1.0.0 and 1.0.1 installed cli_ure, cli_basetypes, cli_uretypes, cli_cppuhelper, cli_oootypes and their policy.1.0.*
# assemblies into the GAC (MsiAssembly rows, the same strong names as LibreOffice's). The new MSI has none
# (scripts/check-msi-no-cli.py); its RemoveExistingProducts runs before InstallInitialize, so the old product, its GAC
# references included, is uninstalled first.
# Steps: [LibreOffice first, if given: its cli_* go into the GAC] -> 1.0.1 -> new MSI (upgrade) -> repair (msiexec /fa)
# -> 1.0.1 again (downgrade, must be refused) -> uninstall. After every step from the upgrade on, the cli_* folders and
# file hashes in the GAC are exactly those before HST Office came (none, or LibreOffice's untouched), one HST Office
# product (none after uninstall), no cli_* file in the program folder, no error 1304 in the logs. VBA macros run
# headless in Sheets and Writer after the upgrade (probe-vba-headless.py with the office's own Python); with
# LibreOffice, in LibreOffice too, after the upgrade and after HST Office is uninstalled.
param(
    [Parameter(Mandatory=$true)][string]$OldMsi,
    [Parameter(Mandatory=$true)][string]$NewMsi,
    [Parameter(Mandatory=$true)][string]$Out,
    [string]$LibreOfficeMsi = ''
)
$ErrorActionPreference = 'Stop'
$HstCode = '{A1751BCB-2603-4428-A5DE-419B438ECFBC}'   # docs/BUILD_MATRIX.md, never changes
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$installer = New-Object -ComObject WindowsInstaller.Installer
$vbaProbe = Join-Path $PSScriptRoot 'probe-vba-headless.py'

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "ok: $Message"
}

function Get-ComProperty($Object, [string]$Name, [object[]]$Arguments) {
    , ($Object.GetType().InvokeMember($Name, [Reflection.BindingFlags]::GetProperty, $null, $Object, $Arguments))
}

function Get-HstProducts {
    $list = Get-ComProperty $installer 'RelatedProducts' @($HstCode)
    $count = Get-ComProperty $list 'Count' @()
    for ($i = 0; $i -lt $count; $i++) {
        $code = Get-ComProperty $list 'Item' @($i)
        [pscustomobject]@{
            ProductCode = $code
            Version = Get-ComProperty $installer 'ProductInfo' @($code, 'VersionString')
            Location = Get-ComProperty $installer 'ProductInfo' @($code, 'InstallLocation')
        }
    }
}

function Get-MsiProperty([string]$Msi, [string]$Property) {
    $db = $installer.GetType().InvokeMember('OpenDatabase', [Reflection.BindingFlags]::InvokeMethod, $null, $installer, @($Msi, 0))
    $view = $db.GetType().InvokeMember('OpenView', [Reflection.BindingFlags]::InvokeMethod, $null, $db,
        @("SELECT ``Value`` FROM ``Property`` WHERE ``Property`` = '$Property'"))
    $view.GetType().InvokeMember('Execute', [Reflection.BindingFlags]::InvokeMethod, $null, $view, $null) | Out-Null
    $record = $view.GetType().InvokeMember('Fetch', [Reflection.BindingFlags]::InvokeMethod, $null, $view, $null)
    $value = Get-ComProperty $record 'StringData' @(1)
    $view.GetType().InvokeMember('Close', [Reflection.BindingFlags]::InvokeMethod, $null, $view, $null) | Out-Null
    # Let go of the database so msiexec can open the package afterwards.
    foreach ($o in $record, $view, $db) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($o) }
    return $value
}

function Get-CliGac([string]$Name) {
    # "<path> <sha256>" of every file in the cli_* / policy.*.cli_* assembly folders of the .NET 4 and .NET 2 GACs.
    $roots = foreach ($base in "$env:WINDIR\Microsoft.NET\assembly", "$env:WINDIR\assembly") {
        foreach ($gac in 'GAC_MSIL', 'GAC_32', 'GAC_64', 'GAC') { Join-Path $base $gac }
    }
    $lines = @($roots | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-ChildItem -LiteralPath $_ -Directory } |
        Where-Object { $_.Name -like 'cli_*' -or $_.Name -like 'policy.*.cli_*' } |
        ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Recurse -File } |
        ForEach-Object { "$($_.FullName) $((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)" } | Sort-Object)
    $lines | Set-Content -Encoding utf8 (Join-Path $Out "gac-$Name.txt")
    Write-Host "GAC cli_* files ($Name): $($lines.Count)"
    return , $lines
}

function Invoke-Msiexec([string[]]$Arguments, [string]$Name) {
    $log = Join-Path $Out "$Name.log"
    # Wait for msiexec itself only: -Wait would also wait for applications the Restart Manager restarts (Explorer).
    $p = Start-Process msiexec.exe -PassThru -ArgumentList ($Arguments + '/qn', '/norestart', '/l*v', "`"$log`"")
    $p.WaitForExit()
    $errors1304 = @(Select-String -LiteralPath $log -Pattern 'Error 1304' -SimpleMatch -ErrorAction SilentlyContinue)
    Write-Host "$Name`: msiexec exit $($p.ExitCode), error 1304 lines: $($errors1304.Count)"
    [pscustomobject]@{ ExitCode = $p.ExitCode; Log = $log; Errors1304 = $errors1304.Count }
}

function Assert-Done($Result, [string]$Name) {
    Assert ($Result.ExitCode -eq 0 -or $Result.ExitCode -eq 3010) "$Name (msiexec exit $($Result.ExitCode), log $($Result.Log))"
}

# Known leftover of 1.0.0/1.0.1 (and of LibreOffice x64): scp2 declares cli_cppuhelper processorArchitecture="x86",
# but the x64 build's assembly is AMD64 and Fusion puts it in GAC_64. The old product's own uninstall (run by
# RemoveExistingProducts, or msiexec /x) asks Fusion to remove the x86 name, which is not there, so this one file stays.
# The new MSI cannot change the old product's uninstall; nothing loads the file. Reported, not failed; anything else fails.
$KnownOrphan = '\Microsoft.NET\assembly\GAC_64\cli_cppuhelper\v4.0_1.0.23.0__ce2cb7e279207b9e\cli_cppuhelper.dll '

function Assert-GacAsBefore([string]$Name) {
    $now = Get-CliGac $Name
    $orphans = @($now | Where-Object { $before -notcontains $_ -and $_ -like "*$KnownOrphan*" })
    if ($orphans.Count) { Write-Host "KNOWN: $Name`: left by the old product's uninstall (x86 name for an AMD64 assembly): $($orphans -join '; ')" }
    $extra = @($now | Where-Object { $before -notcontains $_ -and $orphans -notcontains $_ })
    $gone = @($before | Where-Object { $now -notcontains $_ })
    Assert ($extra.Count -eq 0 -and $gone.Count -eq 0) "$Name`: the GAC cli_* files are those before HST Office came (extra: $($extra -join '; ') missing: $($gone -join '; '))"
}

function Invoke-VbaProbe([string]$Program, [string]$Name) {
    # Bounded: a blocked office must fail this step, not the job's time limit (the probe dumps its stacks after 10 min).
    $dir = Join-Path $Out "vba-$Name"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $stdout, $stderr = (Join-Path $dir 'probe.out'), (Join-Path $dir 'probe.err')
    $p = Start-Process (Join-Path $Program 'python.exe') -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -ArgumentList "`"$vbaProbe`"", '--soffice', "`"$(Join-Path $Program 'soffice.exe')`"", '--out', "`"$dir`""
    $null = $p.Handle  # keeps ExitCode readable after WaitForExit
    $done = $p.WaitForExit(900000)
    if (-not $done) {
        $p.Kill()
        Get-Process soffice, soffice.bin -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Program*" } | Stop-Process -Force
    }
    Get-Content -LiteralPath $stdout, $stderr -ErrorAction SilentlyContinue | Write-Host
    Assert ($done -and $p.ExitCode -eq 0) "$Name`: VBA macros run headless in Sheets and Writer (probe exit $(if ($done) { $p.ExitCode } else { 'timeout' }))"
}

$newCode = Get-MsiProperty $NewMsi 'ProductCode'
$newVersion = [version](Get-MsiProperty $NewMsi 'ProductVersion')
$oldVersion = [version](Get-MsiProperty $OldMsi 'ProductVersion')
Write-Host "old $oldVersion, new $newVersion $newCode"
$loProgram = Join-Path $env:ProgramFiles 'LibreOffice\program'
if ($LibreOfficeMsi) {
    Assert-Done (Invoke-Msiexec @('/i', "`"$LibreOfficeMsi`"") 'libreoffice-install') 'LibreOffice installs'
}
$before = Get-CliGac 'before'
if ($LibreOfficeMsi) { Assert ($before.Count -gt 0) "LibreOffice put its cli_* assemblies into the GAC ($($before.Count) files)" }

$old = Invoke-Msiexec @('/i', "`"$OldMsi`"") 'old-install'
Assert-Done $old 'HST Office 1.0.1 installs'
$oldGac = Get-CliGac 'old'
Assert ($oldGac.Count -gt 0) "the GAC has cli_* assemblies with 1.0.1 installed ($($oldGac.Count) files; $(@($oldGac | Where-Object { $before -notcontains $_ }).Count) new or changed by 1.0.1)"

$new = Invoke-Msiexec @('/i', "`"$NewMsi`"") 'new-install'
Assert-Done $new 'the new MSI installs over 1.0.1'
Assert ($new.Errors1304 -eq 0) 'the upgrade log has no error 1304'
Assert-GacAsBefore 'upgrade'
$products = @(Get-HstProducts)
$products | Format-Table -AutoSize | Out-String | Write-Host
Assert ($products.Count -eq 1) "one HST Office product registered after the upgrade ($($products.Count))"
$product = $products[0]
Assert ($product.ProductCode -eq $newCode) "the registered product is the new one ($($product.ProductCode) $($product.Version))"
$root = if ($product.Location) { $product.Location.TrimEnd('\') } else { Join-Path $env:ProgramFiles 'HSTOffice' }
$program = Join-Path $root 'program'
Assert (Test-Path -LiteralPath (Join-Path $program 'soffice.exe')) "soffice.exe under $program"
$cliFiles = @(Get-ChildItem -LiteralPath $root -Recurse -File -Include 'cli_*.dll', 'cli_*.config', 'policy.*.cli_*.dll' -ErrorAction SilentlyContinue)
Assert ($cliFiles.Count -eq 0) "no CLI-UNO file in the install folder ($($cliFiles.FullName -join ', '))"
Invoke-VbaProbe $program 'hst-after-upgrade'

$repair = Invoke-Msiexec @('/fa', $product.ProductCode) 'repair'
Assert-Done $repair 'repair (msiexec /fa) of the new product'
Assert ($repair.Errors1304 -eq 0) 'the repair log has no error 1304'
Assert-GacAsBefore 'repair'

# Windows Installer compares three version fields; a build of the same release (1.0.1 before VERSION moves on) would
# simply replace 1.0.1 again, so the downgrade check needs a higher version.
if ([version]"$($newVersion.Major).$($newVersion.Minor).$($newVersion.Build)" -gt [version]"$($oldVersion.Major).$($oldVersion.Minor).$($oldVersion.Build)") {
    $down = Invoke-Msiexec @('/i', "`"$OldMsi`"") 'downgrade'
    Assert ($down.ExitCode -ne 0 -and $down.ExitCode -ne 3010) "installing 1.0.1 over the new version is refused (msiexec exit $($down.ExitCode))"
    $after = @(Get-HstProducts)
    Assert ($after.Count -eq 1 -and $after[0].ProductCode -eq $newCode) "the new version stays installed after the refused downgrade ($($after.Version -join ', '))"
    Assert-GacAsBefore 'downgrade'
} else {
    Write-Host "NOT TESTED: downgrade ($newVersion is not above $oldVersion in the three fields Windows Installer compares)"
}
if ($LibreOfficeMsi) { Invoke-VbaProbe $loProgram 'libreoffice-with-hst' }

Assert-Done (Invoke-Msiexec @('/x', $product.ProductCode) 'uninstall') 'uninstall of the new product'
Assert (@(Get-HstProducts).Count -eq 0) 'no HST Office product left after uninstall'
Assert-GacAsBefore 'uninstall'
if ($LibreOfficeMsi) { Invoke-VbaProbe $loProgram 'libreoffice-after-hst-uninstall' }
Write-Host 'Upgrade over 1.0.1 passed: no CLI-UNO assembly of HST Office in the GAC, VBA runs, repair, downgrade block, uninstall'
