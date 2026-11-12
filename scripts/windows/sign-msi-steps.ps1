# SPDX-License-Identifier: AGPL-3.0-only
# Steps of scripts/windows/sign-msi.ps1 (dot-sourced; needs the types from msi-authenticode-native.cs).
$PeSignedOk = 'Valid'
$NoCompressionAttribute = 0x2000   # msidbFileAttributesNoncompressed: the file is not in a cabinet

function Write-Log([string]$Message) {
    Write-Host $Message
    Add-Content -LiteralPath $script:LogPath -Value $Message -Encoding UTF8
}

function Invoke-Query($Db, [string]$Sql, [object[]]$Arguments = @()) {
    , @($Db.Query($Sql, $Arguments))
}

function Test-IsPe([string]$Path) {
    # MZ header whose e_lfanew points at a "PE\0\0" signature.
    $stream = [IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt 64) { return $false }
        $reader = New-Object IO.BinaryReader $stream
        if ($reader.ReadUInt16() -ne 0x5A4D) { return $false }
        $stream.Position = 0x3C
        $offset = $reader.ReadUInt32()
        if ($offset + 4 -gt $stream.Length) { return $false }
        $stream.Position = $offset
        return $reader.ReadUInt32() -eq 0x00004550
    } finally { $stream.Dispose() }
}

function Test-EmbeddedSignature($Signature) {
    # Valid and embedded in the file: a catalog match on this PC proves nothing on another one.
    $Signature.Status -eq $PeSignedOk -and "$($Signature.SignatureType)" -eq 'Authenticode'
}

function Test-TimestampedSignature($Signature) {
    (Test-EmbeddedSignature $Signature) -and $null -ne $Signature.TimeStamperCertificate
}

function Get-CertificateLabel($Certificate) {
    if (-not $Certificate) { return '(none)' }
    $Certificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
}

function Get-SigningCertificate([string]$Thumbprint) {
    $now = Get-Date
    $certs = @(Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.HasPrivateKey -and $_.NotAfter -gt $now })
    if ($Thumbprint) {
        $wanted = ($Thumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
        $certs = @($certs | Where-Object { $_.Thumbprint -eq $wanted })
    }
    if ($certs.Count -eq 0) {
        throw ("no valid code-signing certificate with a private key in Cert:\CurrentUser\My of $env:USERNAME" +
               $(if ($Thumbprint) { " matching thumbprint $Thumbprint" } else { '' }) +
               '. Connect the token and run this as the Windows user whose desktop session sees it.')
    }
    if ($certs.Count -gt 1) {
        $list = ($certs | ForEach-Object { "$(Get-CertificateLabel $_) $($_.Thumbprint.Substring(0, 8))... until $($_.NotAfter.ToString('yyyy-MM-dd'))" }) -join '; '
        throw "several code-signing certificates, choose one with -Thumbprint: $list"
    }
    $cert = $certs[0]
    Write-Log ("certificate: {0}, issuer {1}, valid until {2:yyyy-MM-dd}, thumbprint {3}..." -f (Get-CertificateLabel $cert),
               $cert.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $true), $cert.NotAfter,
               $cert.Thumbprint.Substring(0, 8))
    return $cert
}

function Initialize-Signer($Certificate, [string]$TimestampUrl, [string]$Name, [string]$Info) {
    $script:SignCert = $Certificate
    $script:SignTimestampUrl = $TimestampUrl
    $script:SignName = $Name
    $script:SignInfo = $Info
    $script:SignedCount = 0
    [HstAuthenticode]::OpenKey($Certificate)
}

function Invoke-Sign([string]$Path) {
    # A failed signature (PIN cancelled, token removed) stops the run; a timestamp server hiccup is retried.
    [HstAuthenticode]::Sign($Path, $script:SignCert, $script:SignName, $script:SignInfo)
    for ($attempt = 1; ; $attempt++) {
        try { [HstAuthenticode]::Timestamp($Path, $script:SignTimestampUrl); break }
        catch {
            if ($attempt -ge 5) { throw "timestamp of $Path failed 5 times: $($_.Exception.Message)" }
            Start-Sleep -Seconds (5 * $attempt)
        }
    }
    $script:SignedCount++
    if ($script:SignedCount % 100 -eq 0) { Write-Log "  ... $($script:SignedCount) files signed" }
}

function New-Cabinet([string]$Directory, [object[]]$Keys, [string]$CabPath, [string]$Compression) {
    # Files keep the File table order (Sequence) and are named by their File key, as Windows Installer expects.
    $out = Split-Path $CabPath
    $ddf = "$CabPath.ddf"
    $lines = @('.OPTION EXPLICIT', ".Set CabinetNameTemplate=$(Split-Path $CabPath -Leaf)", ".Set DiskDirectoryTemplate=$out",
               '.Set MaxDiskSize=0', '.Set CabinetFileCountThreshold=0', '.Set FolderFileCountThreshold=0',
               '.Set FolderSizeThreshold=0', '.Set MaxCabinetSize=0', '.Set Cabinet=on', '.Set Compress=on',
               ".Set CompressionType=$Compression", ".Set RptFileName=$CabPath.rpt", ".Set InfFileName=$CabPath.inf")
    if ($Compression -eq 'LZX') { $lines += '.Set CompressionMemory=21' }
    $lines += $Keys | ForEach-Object { "`"$(Join-Path $Directory $_)`" `"$_`"" }
    Set-Content -LiteralPath $ddf -Value $lines -Encoding ASCII
    & makecab.exe /F $ddf | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "makecab failed ($LASTEXITCODE) for $CabPath" }
    if (@(Get-ChildItem -LiteralPath $out -Filter *.cab).Count -ne 1) { throw "makecab did not write exactly one cabinet for $CabPath" }
}

function Invoke-CabinetSigning($Db, [string]$Work, [string]$Compression) {
    $files = Invoke-Query $Db 'SELECT `File`, `Sequence`, `Attributes` FROM `File`'
    $hashed = @{}
    if ($Db.HasTable('MsiFileHash')) { foreach ($row in (Invoke-Query $Db 'SELECT `File_` FROM `MsiFileHash`')) { $hashed[$row[0]] = $true } }
    $changed = 0
    $previous = 0
    foreach ($media in (Invoke-Query $Db 'SELECT `DiskId`, `LastSequence`, `Cabinet` FROM `Media` ORDER BY `LastSequence`')) {
        $last = [int]$media[1]
        $inCab = @($files | Where-Object { [int]$_[1] -gt $previous -and [int]$_[1] -le $last } | Sort-Object { [int]$_[1] })
        $previous = $last
        if ($inCab.Count -eq 0) { continue }
        if (-not $media[2].StartsWith('#')) { throw "Media $($media[0]) uses the external cabinet '$($media[2])'; only embedded cabinets are supported" }
        $stream = $media[2].Substring(1)
        $dir = Join-Path $Work "cab-$($media[0])"
        New-Item -ItemType Directory -Force $dir | Out-Null
        $cab = Join-Path $Work $stream
        $bytes = $Db.ExportStream('_Streams', $stream, $cab)
        & expand.exe $cab "-F:*" $dir | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "expand failed ($LASTEXITCODE) for cabinet $stream" }
        Remove-Item -LiteralPath $cab
        $keys = @($inCab | Where-Object { Test-Path -LiteralPath (Join-Path $dir $_[0]) } | ForEach-Object { $_[0] })
        $missing = @($inCab | Where-Object { -not (Test-Path -LiteralPath (Join-Path $dir $_[0])) -and -not ([int]$_[2] -band $NoCompressionAttribute) })
        if ($missing.Count) { throw "cabinet $stream lacks $($missing.Count) files of its range, e.g. $($missing[0][0])" }
        $extracted = @(Get-ChildItem -LiteralPath $dir -File).Count
        if ($extracted -ne $keys.Count) { throw "cabinet $stream holds $extracted files, the File table expects $($keys.Count)" }
        $pe = 0; $toSign = @()
        foreach ($key in $keys) {
            $path = Join-Path $dir $key
            if (-not (Test-IsPe $path)) { continue }
            $pe++
            if (-not (Test-EmbeddedSignature (Get-AuthenticodeSignature -LiteralPath $path))) { $toSign += $key }
        }
        Write-Log ("cabinet {0} ({1:n1} MB): {2} files, {3} PE, {4} to sign, {5} already signed" -f $stream, ($bytes / 1MB),
                   $keys.Count, $pe, $toSign.Count, ($pe - $toSign.Count))
        if ($toSign.Count) {
            foreach ($key in $toSign) { Invoke-Sign (Join-Path $dir $key) }
            $outCab = Join-Path (Join-Path $Work "newcab-$($media[0])") $stream
            New-Item -ItemType Directory -Force (Split-Path $outCab) | Out-Null
            New-Cabinet $dir $keys $outCab $Compression
            $Db.ImportStream('_Streams', $stream, $outCab)
            foreach ($key in $toSign) {
                $path = Join-Path $dir $key
                $Db.Execute('UPDATE `File` SET `FileSize` = ? WHERE `File` = ?', [object[]]@([int](Get-Item -LiteralPath $path).Length, $key))
                if ($hashed.ContainsKey($key)) {
                    $hash = [HstMsiDb]::FileHash($path)
                    $Db.Execute('UPDATE `MsiFileHash` SET `HashPart1` = ?, `HashPart2` = ?, `HashPart3` = ?, `HashPart4` = ? WHERE `File_` = ?',
                                [object[]]@($hash[0], $hash[1], $hash[2], $hash[3], $key))
                }
            }
            Write-Log ("cabinet {0} repacked: {1:n1} MB" -f $stream, ((Get-Item -LiteralPath $outCab).Length / 1MB))
            Remove-Item -LiteralPath (Split-Path $outCab) -Recurse -Force
            $changed += $toSign.Count
        }
        Remove-Item -LiteralPath $dir -Recurse -Force
    }
    return $changed
}

function Get-BinaryPes($Db, [string]$Directory) {
    # Writes every Binary-table row to Directory and returns the names of the PE files among them.
    New-Item -ItemType Directory -Force $Directory | Out-Null
    $names = @()
    if (-not $Db.HasTable('Binary')) { return , $names }
    foreach ($row in (Invoke-Query $Db 'SELECT `Name` FROM `Binary`')) {
        $path = Join-Path $Directory $row[0]
        $Db.ExportStream('Binary', $row[0], $path) | Out-Null
        if (Test-IsPe $path) { $names += $row[0] }
    }
    return , $names
}

function Invoke-BinaryTableSigning($Db, [string]$Work) {
    $dir = Join-Path $Work 'binary'
    $changed = 0
    $names = Get-BinaryPes $Db $dir
    foreach ($name in $names) {
        $path = Join-Path $dir $name
        if (Test-EmbeddedSignature (Get-AuthenticodeSignature -LiteralPath $path)) { continue }
        Invoke-Sign $path
        $Db.ImportStream('Binary', $name, $path)
        $changed++
    }
    Write-Log "Binary table: $($names.Count) PE, $changed signed now"
    return $changed
}

function Test-PeSet([string]$Label, [object[]]$Paths) {
    # Logs signer counts and every failure; returns the number of failures.
    $failures = 0; $signers = @{}; $untimed = 0
    foreach ($path in $Paths) {
        $sig = Get-AuthenticodeSignature -LiteralPath $path
        if (-not (Test-EmbeddedSignature $sig)) {
            $failures++
            if ($failures -le 30) { Write-Log "  FAIL $Label $(Split-Path $path -Leaf): $($sig.Status) $($sig.StatusMessage)" }
            continue
        }
        $who = Get-CertificateLabel $sig.SignerCertificate
        $signers[$who] = 1 + $(if ($signers.ContainsKey($who)) { $signers[$who] } else { 0 })
        if (-not $sig.TimeStamperCertificate) { $untimed++ }
    }
    $by = ($signers.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', '
    Write-Log "$Label`: $($Paths.Count) PE, $($Paths.Count - $failures) validly signed ($by), $untimed without timestamp, $failures failures"
    return $failures
}

function Test-SignedMsi([string]$Path, [string]$Directory) {
    $failures = 0
    $sig = Get-AuthenticodeSignature -LiteralPath $Path
    if (Test-TimestampedSignature $sig) {
        Write-Log "MSI: valid, signed by $(Get-CertificateLabel $sig.SignerCertificate), timestamp by $(Get-CertificateLabel $sig.TimeStamperCertificate)"
    } else { Write-Log "FAIL MSI: $($sig.Status) $($sig.StatusMessage), timestamp: $([bool]$sig.TimeStamperCertificate)"; $failures++ }
    $db = New-Object HstMsiDb $Path, $false
    try { $names = Get-BinaryPes $db (Join-Path $Directory 'binary') } finally { $db.Dispose() }
    $failures += Test-PeSet 'Binary table' @($names | ForEach-Object { Join-Path (Join-Path $Directory 'binary') $_ })
    $image = Join-Path $Directory 'admin-image'
    $log = Join-Path $Directory 'admin-install.log'
    $run = Start-Process msiexec.exe -ArgumentList "/a `"$Path`" /qn TARGETDIR=`"$image`" /l*v `"$log`"" -Wait -PassThru
    if ($run.ExitCode -ne 0) {
        Write-Log "FAIL administrative extraction: msiexec exit $($run.ExitCode), log $log"
        return $failures + 1
    }
    $pes = @(Get-ChildItem -LiteralPath $image -Recurse -File | Where-Object { $_.Extension -ne '.msi' -and (Test-IsPe $_.FullName) } |
             ForEach-Object { $_.FullName })
    Write-Log "administrative extraction: ok, $(@(Get-ChildItem -LiteralPath $image -Recurse -File).Count) files"
    $failures += Test-PeSet 'installed files' $pes
    return $failures
}
