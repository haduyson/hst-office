# SPDX-License-Identifier: AGPL-3.0-only
# Windows side of scripts/perf/large-file-open-local.sh: unpack the MSI as an administrative image (nothing is
# installed) and run large-file-open.py with the image's own Python. Everything stays under the test root.
#   large-file-open-windows.ps1 <root> <label> <msi file name> [harness options...]
# No param() block: harness options such as --label would otherwise bind to a script parameter.
$ErrorActionPreference = 'Stop'
if ($args.Count -lt 3) { throw 'usage: large-file-open-windows.ps1 <root> <label> <msi file name> [options]' }
$Root = $args[0]; $Label = $args[1]; $Msi = $args[2]
$Rest = @($args | Select-Object -Skip 3)
$img = Join-Path $Root "img\$Label"; $out = Join-Path $Root "out\$Label"
$pkg = Join-Path $Root "pkg\$Label\$Msi"
$hash = (Get-FileHash $pkg -Algorithm SHA256).Hash
if (-not (Test-Path "$img\.package.sha256") -or (Get-Content "$img\.package.sha256") -ne $hash) {
    if (Test-Path $img) { Remove-Item -Recurse -Force $img }
    $p = Start-Process msiexec.exe -ArgumentList @('/a', "`"$pkg`"", '/qn', "TARGETDIR=`"$img`"") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "msiexec /a exit $($p.ExitCode)" }
    Set-Content "$img\.package.sha256" $hash
}
$soffice = Get-ChildItem $img -Recurse -Filter soffice.exe | Where-Object { $_.DirectoryName -like '*\program' } |
    Select-Object -First 1
$python = Join-Path $soffice.DirectoryName 'python.exe'
New-Item -ItemType Directory -Force $out | Out-Null
"$((Get-CimInstance Win32_Processor).Name), $([Environment]::ProcessorCount) logical processors" |
    Set-Content (Join-Path $out 'machine.txt')
Get-Process soffice* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Root*" } | Stop-Process -Force
$env:PYTHONUTF8 = '1'
& $python (Join-Path $Root 'scripts\large-file-open.py') --soffice $soffice.FullName --python $python `
    --files (Join-Path $Root 'fixtures') --out $out --label $Label @Rest
Get-Process soffice* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Root*" } | Stop-Process -Force
