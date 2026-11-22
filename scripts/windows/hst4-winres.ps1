# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
<#
Version resources of a Windows build slot, dot-sourced by hst4-build.ps1.

Reset-StaleWinRes: gbuild's WinResTarget dependency files (workdir\Dep\WinResTarget\*.d, written by makedepend)
come out EMPTY on the Windows slots, so make never rebuilds a .res when a header its .rc includes changes. The
version resource of every HST exe/dll is include\default.rc, which includes hst_version.h (generated from /VERSION
by trial-build.sh --configure) and version.hrc -> config_host\config_version.h: after a version bump an
incremental slot kept linking the old .res (the 1.0.2 MSI shipped FileVersion 1.0.1 on 167 files). Before make,
the headers every .rc of the tree includes (followed transitively through the tree's include directories; SDK
headers are part of the toolchain) are hashed; when the hash differs from the last build's, every .res is deleted
so make rebuilds them and relinks their exe/dll. A clean tree has no stamp and no .res, so nothing is deleted.

Test-FileVersions: every exe/dll the new MSI ships (its File table) whose version resource in instdir names the
product "HST Office" must carry the FileVersion (VERSION.build) and ProductVersion (release id) that
scripts/write-hst-version.py derives from the checkout's /VERSION and data/hst/release.json; otherwise the build
fails before the MSI is collected. Files the MSI does not ship are not checked: an incremental instdir keeps
leftovers of modules no longer built (cli_uno.dll after CLI-UNO was turned off, still 1.0.1).
#>

function Get-WinResInputs([string]$Tree) {
    # .rc files of the source tree (not workdir/instdir/external tarball trees, not ODK samples or tests).
    # EnumerateFiles per module directory: Get-ChildItem -Recurse over the whole tree (workdir included) is far slower.
    $skip = '\\(odk\\examples|[^\\]*test[^\\]*)\\'
    $rcs = foreach ($dir in Get-ChildItem -LiteralPath $Tree -Directory | Where-Object { $_.Name -notin 'workdir', 'instdir', 'external', 'translations', 'helpcontent2', 'dictionaries' }) {
        foreach ($f in [IO.Directory]::EnumerateFiles($dir.FullName, '*.rc', [IO.SearchOption]::AllDirectories)) {
            if ($f.Substring($Tree.Length) -notmatch $skip) { $f }
        }
    }
    $found = [ordered]@{}
    $queue = New-Object System.Collections.Queue
    foreach ($rc in $rcs) { $queue.Enqueue($rc) }
    while ($queue.Count) {
        $file = $queue.Dequeue()
        $module = ($file.Substring($Tree.Length + 1) -split '\\')[0]
        $dirs = @((Split-Path -Parent $file), (Join-Path $Tree 'include'), (Join-Path $Tree 'config_host'),
            (Join-Path $Tree "$module\inc"))
        foreach ($m in [regex]::Matches([IO.File]::ReadAllText($file), '(?m)^\s*#\s*include\s*[<"]([^>"]+)[>"]')) {
            $name = $m.Groups[1].Value -replace '/', '\'
            foreach ($d in $dirs) {
                $p = Join-Path $d $name
                if (Test-Path -LiteralPath $p -PathType Leaf) {
                    $full = (Resolve-Path -LiteralPath $p).Path
                    if (-not $found.Contains($full)) { $found[$full] = $true; $queue.Enqueue($full) }
                    break
                }
            }
        }
    }
    @($found.Keys | Sort-Object)
}

function Reset-StaleWinRes([string]$Tree) {
    $stamp = Join-Path $Tree 'workdir\hst-winres-inputs.txt'
    $inputs = Get-WinResInputs $Tree
    $lines = foreach ($f in $inputs) { "$((Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash)  $($f.Substring($Tree.Length + 1))" }
    $text = ($lines -join "`n") + "`n"
    $old = if (Test-Path -LiteralPath $stamp) { [IO.File]::ReadAllText($stamp) } else { $null }
    $res = @(Get-ChildItem -LiteralPath (Join-Path $Tree 'workdir\WinResTarget') -Recurse -File -Filter '*.res' -ErrorAction SilentlyContinue)
    if ($old -eq $text) {
        Write-Log "version resources: $($inputs.Count) .rc headers unchanged, $($res.Count) .res kept"
        return
    }
    if ($res.Count) {
        $changed = if ($null -eq $old) { 'no record of the last build' } else {
            $was = @($old -split "`n"); (@($lines | Where-Object { $was -notcontains $_ }) | ForEach-Object { ($_ -split '  ', 2)[1] }) -join ', ' }
        $res | Remove-Item -Force
        Write-Log "version resources: .rc headers changed ($changed): deleted $($res.Count) .res, make rebuilds them and relinks"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $stamp) | Out-Null
    [IO.File]::WriteAllText($stamp, $text)
}

function Get-MsiFileNames([string]$Msi) {
    # Long file names of the MSI's File table ("SHORT~1.DLL|long.dll"), through the Windows Installer COM object.
    $call = { param($o, $name, $kind, $argv) $o.GetType().InvokeMember($name, $kind, $null, $o, $argv) }
    $wi = New-Object -ComObject WindowsInstaller.Installer
    $db = & $call $wi 'OpenDatabase' 'InvokeMethod' @($Msi, 0)
    $view = & $call $db 'OpenView' 'InvokeMethod' @('SELECT `FileName` FROM `File`')
    [void](& $call $view 'Execute' 'InvokeMethod' $null)
    $names = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    while ($rec = & $call $view 'Fetch' 'InvokeMethod' $null) {
        [void]$names.Add(((& $call $rec 'StringData' 'GetProperty' @(1)) -split '\|')[-1])
    }
    [void](& $call $view 'Close' 'InvokeMethod' $null)
    foreach ($o in $view, $db, $wi) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($o) }   # unlock the MSI
    , $names
}

function Test-FileVersions([string]$Tree, [string]$Checkout, [string]$Py, [string]$MsiDir, [datetime]$Since,
    [int]$Minimum = 100) {
    $msi = @(Get-ChildItem -LiteralPath $MsiDir -Filter '*.msi' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $Since } | Sort-Object LastWriteTime)
    if (-not $msi.Count) { throw "no MSI written by this build under $MsiDir" }
    $shipped = Get-MsiFileNames $msi[-1].FullName
    $writer = Join-Path $Checkout 'scripts\write-hst-version.py'
    $ask = { param($flag) $v = (& $Py -I $writer $flag | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $v) { throw "write-hst-version.py $flag failed" }; $v }
    $release = & $ask '--release'
    $version = & $ask '--print'
    $build = & $ask '--build'
    $wantFile = "$version.$build"
    $files = @(Get-ChildItem -LiteralPath (Join-Path $Tree 'instdir') -Recurse -File -Include '*.exe', '*.dll' |
        Where-Object { $shipped.Contains($_.Name) -and $_.VersionInfo.ProductName -eq 'HST Office' })
    $bad = @($files | Where-Object { $_.VersionInfo.FileVersion -ne $wantFile -or $_.VersionInfo.ProductVersion -ne $release })
    if ($files.Count -lt $Minimum) {
        throw "only $($files.Count) exe/dll carry the HST Office version resource (expected at least $Minimum)"
    }
    if ($bad.Count) {
        $list = ($bad | Select-Object -First 10 | ForEach-Object {
            "$($_.Name) $($_.VersionInfo.FileVersion)/$($_.VersionInfo.ProductVersion)" }) -join ', '
        throw "$($bad.Count) of $($files.Count) HST exe/dll do not carry FileVersion $wantFile / ProductVersion ${release}: $list"
    }
    Write-Log "file versions: $($files.Count) HST exe/dll of $($msi[-1].Name) carry FileVersion $wantFile, ProductVersion $release"
}
