# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: write a copy of an HST Office MSI with table edits, to try an installer rule without a full build.
#   smoke-edit-msi.ps1 -Edit legacy-reinstall -Msi <in.msi> -OutMsi <out.msi>
#   legacy-reinstall: a detect-only Upgrade row on LibreOffice's code (the 1.0.0.x betas 1-4) sets HSTLEGACYPRODUCTS;
#                     when it is set, two property actions right after FindRelatedProducts (execute and UI sequence,
#                     before costing) set REINSTALLMODE=amus, so files the betas stamped with a higher version are
#                     still copied, and VC_REDIST=0, so the system C++ runtime components are not costed at all.
# Only table logic can be tried this way (Upgrade, Property, CustomAction, sequences), not code changes.
param(
    [Parameter(Mandatory=$true)][ValidateSet('legacy-reinstall')][string]$Edit,
    [Parameter(Mandatory=$true)][string]$Msi,
    [Parameter(Mandatory=$true)][string]$OutMsi
)
$ErrorActionPreference = 'Stop'
$LibreOfficeCode = '{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}'
$installer = New-Object -ComObject WindowsInstaller.Installer

function Invoke-Com($Object, [string]$Name, [object[]]$Arguments, [string]$Kind = 'InvokeMethod') {
    , ($Object.GetType().InvokeMember($Name, [Reflection.BindingFlags]::$Kind, $null, $Object, $Arguments))
}

function Invoke-Sql($Db, [string]$Sql) {
    Write-Host "sql: $Sql"
    $view = Invoke-Com $Db 'OpenView' @($Sql)
    Invoke-Com $view 'Execute' @() | Out-Null
    Invoke-Com $view 'Close' @() | Out-Null
}

function Get-Value($Db, [string]$Sql) {
    # First column of the first row, or $null.
    $view = Invoke-Com $Db 'OpenView' @($Sql)
    Invoke-Com $view 'Execute' @() | Out-Null
    $rec = Invoke-Com $view 'Fetch' @()
    $value = if ($rec) { "$(Invoke-Com $rec 'StringData' @([int]1) 'GetProperty')" } else { $null }
    Invoke-Com $view 'Close' @() | Out-Null
    return $value
}

Copy-Item -LiteralPath $Msi -Destination $OutMsi -Force
$db = Invoke-Com $installer 'OpenDatabase' @($OutMsi, 1)   # msiOpenDatabaseModeTransact
$secure = Get-Value $db "SELECT ``Value`` FROM ``Property`` WHERE ``Property``='SecureCustomProperties'"
if (-not $secure) { throw 'the MSI has no SecureCustomProperties' }
if (($secure -split ';') -contains 'HSTLEGACYPRODUCTS') { throw 'the MSI already has HSTLEGACYPRODUCTS' }
Invoke-Sql $db ("INSERT INTO ``Upgrade`` (``UpgradeCode``, ``VersionMin``, ``VersionMax``, ``Attributes``, ``ActionProperty``) " +
    "VALUES ('$LibreOfficeCode', '1.0.0.0', '1.0.1.0', 258, 'HSTLEGACYPRODUCTS')")
Invoke-Sql $db "UPDATE ``Property`` SET ``Value``='$secure;HSTLEGACYPRODUCTS' WHERE ``Property``='SecureCustomProperties'"
$actions = [ordered]@{ HstLegacyReinstallMode = @('REINSTALLMODE', 'amus'); HstLegacyNoVcRedist = @('VC_REDIST', '0') }
foreach ($a in $actions.Keys) {
    Invoke-Sql $db "INSERT INTO ``CustomAction`` (``Action``, ``Type``, ``Source``, ``Target``) VALUES ('$a', 51, '$($actions[$a][0])', '$($actions[$a][1])')"
}
foreach ($table in 'InstallExecuteSequence', 'InstallUISequence') {
    $find = [int](Get-Value $db "SELECT ``Sequence`` FROM ``$table`` WHERE ``Action``='FindRelatedProducts'")
    $cost = [int](Get-Value $db "SELECT ``Sequence`` FROM ``$table`` WHERE ``Action``='CostInitialize'")
    if (-not $find -or -not $cost) { throw "$table lacks FindRelatedProducts or CostInitialize" }
    $next = Get-Value $db "SELECT ``Sequence`` FROM ``$table`` WHERE ``Sequence`` > $find AND ``Sequence`` <= $($find + $actions.Count)"
    if ($next) { throw "$table has no free sequence numbers right after FindRelatedProducts ($find; $next is taken)" }
    if ($find + $actions.Count -ge $cost) { throw "$table runs CostInitialize ($cost) too early" }
    $seq = $find
    foreach ($a in $actions.Keys) {
        $seq++
        Invoke-Sql $db "INSERT INTO ``$table`` (``Action``, ``Condition``, ``Sequence``) VALUES ('$a', 'HSTLEGACYPRODUCTS', $seq)"
    }
}
Invoke-Com $db 'Commit' @() | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($db) | Out-Null
Write-Host "edited ($Edit): $OutMsi"
