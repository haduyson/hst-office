# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# The new-version pop-up on a Windows test PC, without touching the installed HST Office or the user's update cache.
#   -Phase prepare -Msi <msi> -Oxt <test package .oxt> [-Dir D:\hst-test\popup]  (SSH session) administrative image
#            (msiexec /a) whose bundled extension is the test package (it honours HST_UPDATE_TEST_URL)
#   -Phase drive  [-DriveArgs '--policy']    (console user's session) update-popup-drive-windows.py with the image's
#            Python (both .py pushed into <Dir>); the signed manifests latest-<version>.json(.sig) are in <Dir>\win-srv, report in <Dir>\report*.json
#   -Phase policy-on | policy-off            (SSH session, elevated) HKLM policy AutoCheck=false, Final; removed again
#   -Phase clean                             (SSH session) remove the image and the run folders
param(
    [Parameter(Mandatory = $true)][ValidateSet('prepare', 'drive', 'policy-on', 'policy-off', 'clean')][string]$Phase,
    [string]$Msi, [string]$Oxt, [string]$Dir = 'D:\hst-test\popup', [string]$DriveArgs = '', [string]$User = 'kiemtra'
)
$ErrorActionPreference = 'Stop'
$image = "$Dir\image"
$policy = 'HKLM:\SOFTWARE\Policies\HASON TECH\HST Office\org.openoffice.Office.HSTUpdate\AutoCheck'
function Get-Program { (Get-ChildItem -Path $image -Recurse -Filter soffice.exe | Select-Object -First 1).DirectoryName }
switch ($Phase) {
    'prepare' {
        Remove-Item -Recurse -Force $image -ErrorAction SilentlyContinue
        $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList '/a', "`"$Msi`"", '/qn', "TARGETDIR=`"$image`"", '/l*v', "`"$Dir\admin.log`""
        "admin image: exit $($p.ExitCode)"
        $program = Get-Program
        $ext = Join-Path (Split-Path $program) 'share\extensions\hst-vietnamese-tools'
        Remove-Item -Recurse -Force $ext
        Copy-Item -LiteralPath $Oxt -Destination "$Dir\test-extension.zip" -Force  # Expand-Archive wants .zip
        Expand-Archive -LiteralPath "$Dir\test-extension.zip" -DestinationPath $ext -Force
        & icacls.exe $Dir /grant "${User}:(OI)(CI)F" /q | Out-Null
        "program: $program; test extension: $(Test-Path "$ext\description.xml")"
    }
    'drive' {
        $program = Get-Program
        $name = if ($DriveArgs -match 'policy') { 'report-policy' } else { 'report' }
        $arguments = @("$Dir\update-popup-drive-windows.py", '--program', $program, '--work', "$Dir\work", '--srv', "$Dir\win-srv",
                       '--out', "$Dir\$name.json") + ($DriveArgs -split ' ' | Where-Object { $_ })
        & "$program\python.exe" @arguments *> "$Dir\$name.log"
        "driver exit $LASTEXITCODE"
    }
    'policy-on' {
        New-Item -Path $policy -Force | Out-Null
        Set-ItemProperty -Path $policy -Name Value -Value 'false'
        Set-ItemProperty -Path $policy -Name Type -Value 'xs:boolean'
        Set-ItemProperty -Path $policy -Name Final -Value 1 -Type DWord
        "policy set: $((Get-ItemProperty $policy).Value)"
    }
    'policy-off' {
        Remove-Item -Path (Split-Path $policy) -Recurse -Force -ErrorAction SilentlyContinue
        "policy removed: $(-not (Test-Path (Split-Path $policy)))"
    }
    'clean' {
        Get-CimInstance Win32_Process -Filter "Name like 'soffice%'" | Where-Object { $_.CommandLine -like "*$Dir*" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Remove-Item -Recurse -Force $image, "$Dir\work" -ErrorAction SilentlyContinue
        "cleaned: $(-not (Test-Path $image))"
    }
}
