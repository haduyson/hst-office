# SPDX-License-Identifier: AGPL-3.0-only
# Opens VBA UserForm sample files with what this Windows machine has, and says what was really tested.
#
#   powershell -File scripts\windows\probe-excel-userform.ps1 -Samples tests\fixtures\vba-forms
#
# Always: the structural check (tests/runtime/vba_form_structure.py). When Microsoft Excel or Word is
# installed: open each file through COM with macros disabled, list its VB components (needs "Trust
# access to the VBA project object model") and report the form's controls. Exit 1 when a file fails a
# check that ran. Exit 0 with "NOT TESTED" lines when Office is missing: GitHub's Windows runners have
# no Office, so a green run there does NOT prove that real Office opens the file; a human must test.
param([Parameter(Mandatory = $true)][string]$Samples)
$ErrorActionPreference = 'Stop'
$failed = 0
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$validator = Join-Path $root 'tests\runtime\vba_form_structure.py'

function Open-InOffice($progId, $file, $open) {
    try { $app = New-Object -ComObject $progId } catch { Write-Output "NOT TESTED ${file}: $progId is not installed"; return $true }
    try {
        $app.Visible = $false
        $app.DisplayAlerts = 0
        $app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable: never run the sample's code
        $doc = & $open $app $file
        try {
            $names = foreach ($component in $doc.VBProject.VBComponents) { "$($component.Name):$($component.Type)" }
            Write-Output "PASS $file opens in $progId; components: $($names -join ', ')"
            $form = $doc.VBProject.VBComponents | Where-Object { $_.Type -eq 3 } | Select-Object -First 1
            if (-not $form) { Write-Output "FAIL ${file}: $progId sees no UserForm"; return $false }
            $controls = foreach ($control in $form.Designer.Controls) { "$($control.Name)=$($control.GetType().Name)" }
            Write-Output "PASS $file form $($form.Name) controls: $($controls -join ', ')"
        } catch {
            Write-Output "NOT TESTED ${file}: VBA project not readable, enable Trust access to the VBA project object model ($_)"
        }
        $doc.Close($false) | Out-Null
        return $true
    } catch {
        Write-Output "FAIL ${file}: $progId could not open it: $_"
        return $false
    } finally {
        $app.Quit() | Out-Null
    }
}

foreach ($file in Get-ChildItem -Path $Samples -File -Include *.xlsm, *.xls, *.docm, *.doc -Recurse) {
    & python $validator $file.FullName
    if ($LASTEXITCODE -ne 0) { $failed++ }
    if ($file.Extension -in '.xlsm', '.xls') {
        if (-not (Open-InOffice 'Excel.Application' $file.FullName { param($a, $f) $a.Workbooks.Open($f) })) { $failed++ }
    } else {
        if (-not (Open-InOffice 'Word.Application' $file.FullName { param($a, $f) $a.Documents.Open($f) })) { $failed++ }
    }
}
if ($failed) { Write-Output "$failed file(s) failed"; exit 1 }
Write-Output 'Done. Lines marked NOT TESTED still need a human test in real Microsoft Office.'
