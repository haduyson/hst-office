# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: the shortcuts HST Writer, HST Sheets and HST Slides of hst-msi-app-desktop-shortcuts.patch.
#   -Expect installed    one of each on the desktop and in the Start menu, each opening its own app
#                        (program\swriter.exe, scalc.exe, simpress.exe, no arguments) with its own AppUserModelID
#   -Expect no-desktop   installed with CREATEDESKTOPLINK=0: the Start menu entries only, no desktop shortcut of HST Office
#   -Expect removed      after uninstall: none of them is left on a desktop or in the Start menu
# Every mode: no "HST Base" shortcut anywhere (hst-hide-base-launchers.patch); installed modes: .odb still opens
# with HST Office (HSTOffice.* type whose open command is program\sbase.exe).
# Usage: pwsh -NoProfile -File check-app-shortcuts.ps1 -Expect installed|no-desktop|removed [-Install <dir>]
param(
    [Parameter(Mandatory = $true)][ValidateSet('installed', 'no-desktop', 'removed')][string]$Expect,
    [string]$Install = ''
)
$ErrorActionPreference = 'Stop'
if ($Expect -ne 'removed' -and -not $Install) { throw "-Install is required with -Expect $Expect" }

# Shortcut name -> launcher in <install>\program and the AppUserModelID of that app's windows.
$apps = [ordered]@{
    'HST Writer' = @{ Exe = 'swriter.exe'; Id = 'HASONTECH.HSTOffice.Writer' }
    'HST Sheets' = @{ Exe = 'scalc.exe'; Id = 'HASONTECH.HSTOffice.Calc' }
    'HST Slides' = @{ Exe = 'simpress.exe'; Id = 'HASONTECH.HSTOffice.Impress' }
}
# Per-machine installs use the public desktop and Start menu, per-user ones the user's: look in both.
$places = [ordered]@{
    desktop = @([Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('Desktop'))
    'Start menu' = @([Environment]::GetFolderPath('CommonPrograms'), [Environment]::GetFolderPath('Programs'))
}
$wsh = New-Object -ComObject WScript.Shell
$shell = New-Object -ComObject Shell.Application
$install = $Install.TrimEnd('\')
$bad = 0
function Fail([string]$Message) { Write-Host "FAIL: $Message"; $script:bad++ }

function Find-Links([string[]]$Folders, [string]$Name) {
    # Start menu entries may sit in a sub-folder; the desktop is flat.
    @(foreach ($folder in ($Folders | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)) {
        Get-ChildItem -LiteralPath $folder -Recurse -Filter "$Name.lnk" -ErrorAction SilentlyContinue
    })
}

foreach ($place in $places.Keys) {
    $wanted = $Expect -eq 'installed' -or ($Expect -eq 'no-desktop' -and $place -eq 'Start menu')
    foreach ($name in $apps.Keys) {
        $links = Find-Links $places[$place] $name
        if (-not $wanted) {
            if ($links.Count -gt 0) { Fail "$place has '$name' ($($links.FullName -join ', '))" } else { Write-Host "ok: no '$name' on the $place" }
            continue
        }
        if ($links.Count -ne 1) { Fail "$place has $($links.Count) shortcuts named '$name' ($($links.FullName -join ', ')), expected one"; continue }
        $link = $links[0]
        $lnk = $wsh.CreateShortcut($link.FullName)
        $target = Join-Path $install "program\$($apps[$name].Exe)"
        $id = $shell.NameSpace($link.DirectoryName).ParseName($link.Name).ExtendedProperty('System.AppUserModel.ID')
        Write-Host ("{0} '{1}': {2} {3} [{4}] icon {5}" -f $place, $name, $lnk.TargetPath, $lnk.Arguments, $id, $lnk.IconLocation)
        if ($lnk.TargetPath -ne $target) { Fail "$place '$name' opens $($lnk.TargetPath), expected $target" }
        if ($lnk.Arguments) { Fail "$place '$name' passes arguments '$($lnk.Arguments)'" }
        if (-not (Test-Path -LiteralPath $lnk.TargetPath)) { Fail "$place '$name' points to a missing file" }
        if ($id -ne $apps[$name].Id) { Fail "$place '$name' has AppUserModelID '$id', expected $($apps[$name].Id)" }
    }
}
if ($Expect -eq 'no-desktop') {
    # The box covers every desktop shortcut of the product, the Start Center's "HST Office" one included.
    $others = @(foreach ($folder in $places['desktop']) {
        Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -ErrorAction SilentlyContinue |
            Where-Object { $wsh.CreateShortcut($_.FullName).TargetPath -like "$install\*" }
    })
    if ($others.Count -gt 0) { Fail "desktop shortcuts into $install with CREATEDESKTOPLINK=0: $($others.Name -join ', ')" }
}
# HST Base is offered nowhere (hst-hide-base-launchers.patch), in every mode: install, upgrade and uninstall.
$base = Find-Links (@($places['desktop']) + @($places['Start menu'])) 'HST Base'
if ($base.Count -gt 0) { Fail "HST Base shortcut found: $($base.FullName -join ', ')" } else { Write-Host 'ok: no HST Base shortcut' }
if ($Expect -ne 'removed') {
    # ...but Base stays installed and .odb files still open with HST Office.
    $progId = (Get-ItemProperty -LiteralPath 'Registry::HKEY_CLASSES_ROOT\.odb' -ErrorAction SilentlyContinue).'(default)'
    $command = (Get-ItemProperty -LiteralPath "Registry::HKEY_CLASSES_ROOT\$progId\shell\open\command" -ErrorAction SilentlyContinue).'(default)'
    $sbase = Join-Path $install 'program\sbase.exe'
    Write-Host ".odb: $progId -> $command"
    if ($progId -notlike 'HSTOffice.*') { Fail ".odb is not an HST Office type ('$progId')" }
    elseif (-not $command -or $command -notlike "*$sbase*") { Fail ".odb does not open with $sbase ('$command')" }
    elseif (-not (Test-Path -LiteralPath $sbase)) { Fail "$sbase is missing" }
    else { Write-Host 'ok: .odb opens with HST Office' }
}
if ($bad -gt 0) { throw "$bad app shortcut check(s) failed (expected: $Expect)" }
Write-Host "app shortcuts: $Expect - ok"
