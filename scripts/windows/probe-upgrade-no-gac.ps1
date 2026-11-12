# SPDX-License-Identifier: AGPL-3.0-only
# Upgrade probe: a new HST Office MSI installed over 1.0.1 leaves no CLI-UNO assembly in the .NET GAC, and VBA still runs.
#   probe-upgrade-no-gac.ps1 -OldMsi <1.0.1 msi> -NewMsi <msi> -Out <dir>
# 1.0.0 and 1.0.1 installed cli_ure, cli_basetypes, cli_uretypes, cli_cppuhelper, cli_oootypes and their policy.1.0.*
# assemblies into the GAC (MsiAssembly rows). The new MSI has none (scripts/check-msi-no-cli.py); its
# RemoveExistingProducts runs before InstallInitialize, so the old product, GAC entries included, is uninstalled first.
# Checks: 1.0.1 puts cli_* into the GAC; after the new MSI no cli_* is left in any GAC (beyond what was there before),
# one HST Office product is registered, no cli_* file is in the program folder, the install log has no error 1304,
# and VBA macros run headless in Sheets and Writer (probe-vba-headless.py with the office's own Python).
param(
    [Parameter(Mandatory=$true)][string]$OldMsi,
    [Parameter(Mandatory=$true)][string]$NewMsi,
    [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$HstCode = '{A1751BCB-2603-4428-A5DE-419B438ECFBC}'   # docs/BUILD_MATRIX.md, never changes
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$installer = New-Object -ComObject WindowsInstaller.Installer

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

function Get-CliGac {
    # Assembly folders of the .NET 4 GAC (Microsoft.NET\assembly) and the .NET 2 GAC (assembly), sorted full paths.
    $roots = foreach ($base in "$env:WINDIR\Microsoft.NET\assembly", "$env:WINDIR\assembly") {
        foreach ($gac in 'GAC_MSIL', 'GAC_32', 'GAC_64', 'GAC') { Join-Path $base $gac }
    }
    @($roots | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-ChildItem -LiteralPath $_ -Directory } |
        Where-Object { $_.Name -like 'cli_*' -or $_.Name -like 'policy.*.cli_*' } | ForEach-Object { $_.FullName } | Sort-Object)
}

function Install-Msi([string]$Msi, [string]$Name) {
    $log = Join-Path $Out "$Name-install.log"
    # Wait for msiexec itself only: -Wait would also wait for applications the Restart Manager restarts (Explorer).
    $p = Start-Process msiexec.exe -PassThru -ArgumentList '/i', "`"$Msi`"", '/qn', '/norestart', '/l*v', "`"$log`""
    $p.WaitForExit()
    Assert ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) "$Name installs (msiexec exit $($p.ExitCode), log $log)"
    return $log
}

$before = Get-CliGac
@("before:") + $before | Set-Content -Encoding utf8 (Join-Path $Out 'gac-before.txt')
Write-Host "GAC cli_* folders before: $($before.Count)"

Install-Msi $OldMsi 'old' | Out-Null
$old = Get-CliGac
@("after 1.0.1:") + $old | Set-Content -Encoding utf8 (Join-Path $Out 'gac-old.txt')
$added = @($old | Where-Object { $before -notcontains $_ })
Assert ($added.Count -gt 0) "1.0.1 put $($added.Count) cli_* assembly folders into the GAC ($($added | ForEach-Object { Split-Path $_ -Leaf } | Sort-Object -Unique) )"

$log = Install-Msi $NewMsi 'new'
$after = Get-CliGac
@("after upgrade:") + $after | Set-Content -Encoding utf8 (Join-Path $Out 'gac-after.txt')
$left = @($after | Where-Object { $before -notcontains $_ })
Assert ($left.Count -eq 0) "no cli_* assembly left in the GAC after the upgrade (left: $($left -join ', '))"

$products = @(Get-HstProducts)
$products | Format-Table -AutoSize | Out-String | Write-Host
Assert ($products.Count -eq 1) "one HST Office product registered after the upgrade ($($products.Count))"
Assert ($products[0].Version -ne '1.0.1.10000') "the registered product is the new one ($($products[0].Version))"

$root = if ($products[0].Location) { $products[0].Location.TrimEnd('\') } else { Join-Path $env:ProgramFiles 'HSTOffice' }
$program = Join-Path $root 'program'
Assert (Test-Path -LiteralPath (Join-Path $program 'soffice.exe')) "soffice.exe under $program"
$cliFiles = @(Get-ChildItem -LiteralPath $root -Recurse -File -Include 'cli_*.dll', 'cli_*.config', 'policy.*.cli_*.dll' -ErrorAction SilentlyContinue)
Assert ($cliFiles.Count -eq 0) "no CLI-UNO file in the install folder ($($cliFiles.FullName -join ', '))"
$errors1304 = @(Select-String -LiteralPath $log -Pattern 'Error 1304' -SimpleMatch)
Assert ($errors1304.Count -eq 0) "the upgrade log has no error 1304"

$vbaOut = Join-Path $Out 'vba'
& (Join-Path $program 'python.exe') (Join-Path $PSScriptRoot 'probe-vba-headless.py') --soffice (Join-Path $program 'soffice.exe') --out $vbaOut
Assert ($LASTEXITCODE -eq 0) "VBA macros run headless in Sheets and Writer after the upgrade (probe exit $LASTEXITCODE)"
Write-Host 'Upgrade over 1.0.1 passed: no CLI-UNO assembly in the GAC, VBA runs'
