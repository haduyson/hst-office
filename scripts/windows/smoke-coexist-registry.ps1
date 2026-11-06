# SPDX-License-Identifier: AGPL-3.0-only
# Dot-sourced by smoke-install-paths.ps1 (uses its Get-RegDefault and Assert). The registry names LibreOffice
# registers that HST Office used to share: App Paths of the common program names, the vnd.libreoffice.command
# URI scheme, the Explorer extension class IDs, the legacy StarOffice ProgIDs and keys under Software\LibreOffice. HST Office must write none of
# them, and installing or removing either suite must leave the other's entries as they were.

$LoClsids = [ordered]@{   # LibreOffice's class ids (upstream shell/inc/shlxthdl.hxx, propertyhdl.hxx, ooofilt.hxx)
    infotip = '{087B3AE3-E237-4467-B8DB-5A38AB959AC9}'; column = '{C52AF81D-F7A0-4AAB-8E87-F80A60CCD396}'
    propsheet = '{63542C48-9552-494A-84F7-73AA6A7C99C1}'; thumbnail = '{3B092F0C-7696-40E3-A80F-68D74DA84210}'
    property = '{AE424E85-F6DF-4910-A6A9-438797986431}'; filter = '{7BC0E710-5703-45BE-A29D-5D46D8B39262}'
}
$HstClsids = [ordered]@{  # hst-windows-own-shell-extension-clsids.patch
    infotip = '{2A30C089-4A9F-4456-9E48-AEB9FF0012A3}'; column = '{0643B6EE-B40D-4AA5-AC91-6849F83692BD}'
    propsheet = '{9A9E8777-D20C-40AD-826C-085F05B40FA6}'; thumbnail = '{BC84498F-C467-4BD6-9876-D44924DA54D0}'
    property = '{A5B95EEC-7757-43B4-A663-634CF2E9A67A}'; filter = '{A0914CEA-1A1D-4B82-A200-FE2818319A03}'
}
$AppNames = 'soffice', 'swriter', 'scalc', 'simpress', 'sdraw', 'smath', 'sbase', 'unopkg'
$ExtractImage = '{BB2E617C-0920-11D1-9A0B-00C04FC2D6C1}'

function Get-CoexistRegistry {
    # lo_*: names only LibreOffice may register; hst_*: HST Office's own replacements; the rest is recorded only.
    $r = [ordered]@{}
    foreach ($n in $AppNames) { $r["lo_app_path_$n"] = Get-RegDefault "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$n.exe" }
    $r.lo_uri_open = Get-RegDefault 'HKEY_CLASSES_ROOT\vnd.libreoffice.command\shell\open\command'
    $r.lo_sxw_open = Get-RegDefault 'HKEY_CLASSES_ROOT\soffice.StarWriterDocument.6\shell\open\command'
    $r.lo_oxt_open = Get-RegDefault 'HKEY_CLASSES_ROOT\office.Extension.1\shell\open\command'
    foreach ($k in $LoClsids.Keys) { $r["lo_clsid_$k"] = Get-RegDefault "HKEY_CLASSES_ROOT\CLSID\$($LoClsids[$k])\InprocServer32" }
    $ure = Get-Item -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\LibreOffice\Layers\URE\1' -ErrorAction SilentlyContinue
    $r.lo_layer_ure = if ($ure) { $ure.GetValue('UREINSTALLLOCATION') } else { $null }
    $r.lo_software_key = if (Test-Path -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\LibreOffice') { 'present' } else { $null }
    $r.lo_classes_software_key = if (Test-Path -LiteralPath 'Registry::HKEY_CLASSES_ROOT\Software\LibreOffice') { 'present' } else { $null }
    $r.hst_sxw_open = Get-RegDefault 'HKEY_CLASSES_ROOT\HSTOffice.StarWriterDocument.6\shell\open\command'
    $r.hst_office_uri_open = Get-RegDefault 'HKEY_CLASSES_ROOT\HSTOffice.OfficeURI\shell\open\command'
    $r.hst_oxt_open = Get-RegDefault 'HKEY_CLASSES_ROOT\HSTOffice.Extension.1\shell\open\command'
    $r.hst_odt_thumbnail = Get-RegDefault "HKEY_CLASSES_ROOT\HSTOffice.WriterDocument.1\shellex\$ExtractImage"
    foreach ($k in $HstClsids.Keys) { $r["hst_clsid_$k"] = Get-RegDefault "HKEY_CLASSES_ROOT\CLSID\$($HstClsids[$k])\InprocServer32" }
    $r.odt_thumbnail = Get-RegDefault "HKEY_CLASSES_ROOT\.odt\shellex\$ExtractImage"
    $r.odt_property_handler = Get-RegDefault 'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\PropertySystem\PropertyHandlers\.odt'
    $r
}

function Assert-HstCoexistKeys([System.Collections.IDictionary]$Reg, [string]$Location) {
    # HST Office's own legacy ProgID, Office URI ProgID and every Explorer extension class point into its program folder.
    $program = (Join-Path $Location 'program').TrimEnd('\')
    foreach ($k in @('hst_sxw_open', 'hst_office_uri_open', 'hst_oxt_open') + @($HstClsids.Keys | ForEach-Object { "hst_clsid_$_" })) {
        Assert ($Reg[$k] -and $Reg[$k].IndexOf($program, [StringComparison]::OrdinalIgnoreCase) -ge 0) "$k is in $program ($($Reg[$k]))"
    }
    Assert ($Reg.hst_odt_thumbnail -eq $HstClsids.thumbnail) "HSTOffice.WriterDocument.1 has HST Office's thumbnail handler ($($Reg.hst_odt_thumbnail))"
}

function Assert-NoLibreOfficeNames([System.Collections.IDictionary]$Reg, [string[]]$Except = @()) {
    # With HST Office alone, none of LibreOffice's names exists (Except: entries not checked).
    $written = @($Reg.Keys | Where-Object { $_ -like 'lo_*' -and $Except -notcontains $_ -and $Reg[$_] })
    Assert ($written.Count -eq 0) "HST Office alone writes no App Paths, vnd.libreoffice.command, LibreOffice class id, soffice.Star ProgID or Software\LibreOffice key ($($written -join ', '))"
}

function Assert-Kept([System.Collections.IDictionary]$Before, [System.Collections.IDictionary]$After, [string]$Prefix, [string]$Label) {
    # Every entry of one suite is unchanged (same value, or still missing) after the other suite was installed or removed.
    $changed = @($Before.Keys | Where-Object { $_ -like "$Prefix*" -and "$($Before[$_])" -ne "$($After[$_])" } |
        ForEach-Object { "$_ '$($Before[$_])' -> '$($After[$_])'" })
    Assert ($changed.Count -eq 0) "$Label ($($changed -join '; '))"
}

function Assert-LibreOfficeRegistered([System.Collections.IDictionary]$Reg, [string]$Location) {
    # LibreOffice registers App Paths and its URI scheme itself; they must point into LibreOffice's folder.
    foreach ($k in 'lo_app_path_soffice', 'lo_uri_open') {
        Assert ($Reg[$k] -and $Reg[$k].IndexOf($Location.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -ge 0) "$k is LibreOffice's ($($Reg[$k]))"
    }
}
