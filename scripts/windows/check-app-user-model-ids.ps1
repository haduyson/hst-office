# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: the Start menu shortcuts and HSTOffice.* ProgIDs of an installed HST Office carry its own
# AppUserModelIDs (hst-windows-app-user-model-ids.patch). Usage: pwsh -NoProfile -File check-app-user-model-ids.ps1 -Install <dir>
param([Parameter(Mandatory = $true)][string]$Install)
$ErrorActionPreference = 'Stop'
# The running windows use HASONTECH.HSTOffice.<Module>; pinned shortcuts and file types must match it
# and never share LibreOffice's TheDocumentFoundation.LibreOffice.<Module> taskbar group.
$shell = New-Object -ComObject Shell.Application
$wsh = New-Object -ComObject WScript.Shell
$install = $Install.TrimEnd('\')
$menus = @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")
$links = @(Get-ChildItem -Path $menus -Recurse -Filter *.lnk -ErrorAction SilentlyContinue |
  Where-Object { $wsh.CreateShortcut($_.FullName).TargetPath -like "$install\*" })
if ($links.Count -eq 0) { throw "no Start menu shortcut points into $install" }
$bad = 0
foreach ($link in $links) {
  $id = $shell.NameSpace($link.DirectoryName).ParseName($link.Name).ExtendedProperty('System.AppUserModel.ID')
  "{0}: {1}" -f $link.Name, $id
  if ($id -notmatch '^HASONTECH\.HSTOffice\.[A-Za-z]+$') { $bad++ }
}
$progids = @(Get-ChildItem -Path Registry::HKEY_CLASSES_ROOT -ErrorAction SilentlyContinue |
  Where-Object { $_.PSChildName -like 'HSTOffice.*' -and $null -ne $_.GetValue('AppUserModelID') })
if ($progids.Count -eq 0) { throw 'no HSTOffice.* ProgID has an AppUserModelID' }
foreach ($key in $progids) {
  $id = $key.GetValue('AppUserModelID')
  "{0}: {1}" -f $key.PSChildName, $id
  if ($id -notmatch '^HASONTECH\.HSTOffice\.[A-Za-z]+$') { $bad++ }
}
if ($bad -gt 0) { throw "$bad shortcut(s) or ProgID(s) carry another AppUserModelID" }
