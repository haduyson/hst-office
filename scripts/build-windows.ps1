# SPDX-License-Identifier: AGPL-3.0-only
# Runner setup helpers for the Windows trial build (windows-2022). Build steps live in scripts/windows/trial-build.sh.
#   pwsh -File scripts/build-windows.ps1 -Task Probe|FreeDisk|Cygwin|Tools [-Work D:\hst] [-CygwinRoot C:\cygwin64]
# -CygwinRoot lets a local build PC (scripts/windows/hst4-setup.ps1) install the same package set elsewhere.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Probe', 'FreeDisk', 'Cygwin', 'Tools')][string]$Task,
    [string]$Work = 'D:\hst',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$CygwinRoot = 'C:\cygwin64'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$CygwinMirror = 'https://mirrors.kernel.org/sourceware/cygwin/'
# Package set for the LibreOffice Windows build (wiki Development/BuildingOnWindows).
$CygwinPackages = 'autoconf,automake,bison,flex,gawk,gettext,gettext-devel,git,gperf,libtool,m4,make,patch,perl,pkg-config,python3,rsync,unzip,zip,libxml2,libxslt,perl-Archive-Zip,perl-Font-TTF,perl-IO-String,curl,wget,cabextract,diffutils,findutils,grep,sed,tar,xz'
$FlexVersion = '2.6.4-2'
$FlexSha512 = '283E462FC23117D865B5D6963E69693FB624FD355CB5113BB2DCA9C0A9262E95ABF025A5B6ACC2AAE5CA8B7C07210A060402FE35B84346DBDEE51FC23B65DDD2'
$MakeUrl ='https://dev-www.libreoffice.org/bin/cygwin/make-4.2.1-msvc.exe'

function Install-ChocoPackage([string]$Name) {
    # The community feed has transient outages; retry before failing the job.
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        choco install $Name --no-progress -y
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "choco install $Name failed (attempt $attempt), retrying"
        Start-Sleep -Seconds (30 * $attempt)
    }
    throw "$Name install failed"
}

function Write-Summary([string]$Text) {
    Write-Output $Text
    if ($env:GITHUB_STEP_SUMMARY) { Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $Text }
}

function Invoke-Probe {
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $os = Get-CimInstance Win32_OperatingSystem
    $lines = @('### Runner probe', "- image: $env:ImageOS $env:ImageVersion; OS: $($os.Caption) $($os.Version)",
        "- CPU: $($cpu.Name); logical processors: $($cs.NumberOfLogicalProcessors)",
        ('- RAM total/free GiB: {0:N1} / {1:N1}' -f ($cs.TotalPhysicalMemory / 1GB), ($os.FreePhysicalMemory / 1MB)))
    foreach ($d in Get-PSDrive -PSProvider FileSystem | Where-Object { $null -ne $_.Used }) {
        $lines += ('- drive {0}: free {1:N1} GiB, used {2:N1} GiB' -f $d.Name, ($d.Free / 1GB), ($d.Used / 1GB))
    }
    $vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -all -prerelease -format json | ConvertFrom-Json
    foreach ($v in $vs) { $lines += "- Visual Studio: $($v.displayName) $($v.installationVersion) at $($v.installationPath)" }
    $sdk = (Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\Include" -Directory -ErrorAction SilentlyContinue).Name -join ', '
    $lines += "- Windows SDKs: $sdk"
    Write-Summary ($lines -join "`n")
}

function Invoke-FreeDisk {
    # Not needed by the LibreOffice build: Android SDK/NDK, Julia, Haskell, Strawberry Perl (shadows Cygwin perl).
    $before = (Get-PSDrive C).Free / 1GB
    foreach ($p in 'C:\Android', 'C:\Program Files\Android', 'C:\Program Files (x86)\Android', 'C:\Julia', 'C:\Strawberry', 'C:\ghcup', 'C:\Rust', 'C:\Users\runneradmin\.rustup', 'C:\hostedtoolcache\windows\Java_Temurin-Hotspot_jdk') {
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Write-Summary ('### Free disk' + "`n" + ('- C: free before/after: {0:N1} / {1:N1} GiB; removed Android SDK, Julia, Strawberry Perl, ghcup, Rust, Temurin cache' -f $before, ((Get-PSDrive C).Free / 1GB)))
}

function Install-PinnedFlex {
    # flex 2.6.5 (Cygwin, 2026-11-11) generates a scanner where connectivity's sqlflex.cxx fails with C3861
    # 'yy_fatal_error'. Overlay the previous release, checked against the mirror's setup.ini sha512.
    $tarball = "$Work\cygpkgs\flex-$FlexVersion.tar.xz"
    Invoke-WebRequest -UseBasicParsing -Uri "${CygwinMirror}x86_64/release/flex/flex-$FlexVersion.tar.xz" -OutFile $tarball
    if ((Get-FileHash -Algorithm SHA512 $tarball).Hash -ne $FlexSha512) { throw "flex $FlexVersion sha512 mismatch" }
    # No double quotes inside the -c argument: Windows PowerShell 5.1 mangles them (work paths have no spaces).
    & "$CygwinRoot\bin\bash.exe" --login -c "tar -xJf `$(cygpath -u '$tarball') -C / && flex --version"
    if ($LASTEXITCODE -ne 0) { throw "flex $FlexVersion overlay failed" }
    Write-Summary "- flex pinned to $FlexVersion"
}

function Invoke-Cygwin {
    New-Item -ItemType Directory -Force -Path $Work, "$Work\logs", "$Work\bin" | Out-Null
    $setup = "$Work\setup-x86_64.exe"
    # cygwin.com sometimes fails DNS on hosted runners; retry before failing the job.
    for ($attempt = 1; ; $attempt++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri 'https://www.cygwin.com/setup-x86_64.exe' -OutFile $setup; break }
        catch {
            if ($attempt -ge 4) { throw }
            Write-Host "Cygwin setup download failed (attempt $attempt): $($_.Exception.Message); retrying"
            Start-Sleep -Seconds (30 * $attempt)
        }
    }
    $sig = Get-AuthenticodeSignature $setup
    Write-Summary ("- Cygwin setup sha256 $((Get-FileHash $setup).Hash), signature $($sig.Status) $($sig.SignerCertificate.Subject)")
    if ($sig.Status -ne 'Valid') { throw "Cygwin setup signature invalid: $($sig.Status)" }
    $setupArgs = @('--quiet-mode', '--no-shortcuts', '--no-startmenu', '--no-desktop', '--only-site', '--site', $CygwinMirror,
        '--local-package-dir', "$Work\cygpkgs", '--root', $CygwinRoot, '--packages', $CygwinPackages)
    $p = Start-Process -FilePath $setup -ArgumentList $setupArgs -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "Cygwin setup failed: $($p.ExitCode)" }
    Install-PinnedFlex
    & "$CygwinRoot\bin\cygcheck.exe" -c | Set-Content -LiteralPath "$Work\logs\cygwin-packages.txt"
    if ($LASTEXITCODE -ne 0) { throw 'cygcheck failed' }
}

function Invoke-Tools {
    New-Item -ItemType Directory -Force -Path "$Work\bin" | Out-Null
    # Native GNU make (avoids Cygwin fork cost); configure detects it first in PATH. Fall back to Cygwin make on failure.
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $MakeUrl -OutFile "$Work\bin\make.exe"
        Write-Summary "- native make sha256 $((Get-FileHash "$Work\bin\make.exe").Hash)"
    } catch { Write-Summary "- native make download failed ($($_.Exception.Message)); using Cygwin make" }
    # configure demands a Windows-path pkgconf named pkgconf-2.4.3.exe (harfbuzz/meson); pkgconfiglite emits Windows paths.
    Install-ChocoPackage 'pkgconfiglite'
    $pkg = Get-ChildItem 'C:\ProgramData\chocolatey\lib\pkgconfiglite' -Recurse -Filter pkg-config.exe | Select-Object -First 1
    if (-not $pkg) { throw 'pkg-config.exe not found in pkgconfiglite package' }
    Copy-Item -LiteralPath $pkg.FullName -Destination "$Work\bin\pkgconf-2.4.3.exe"
    Write-Summary "- pkgconf shim from $($pkg.FullName)"
    Install-ChocoPackage 'nasm'
    if (-not (Test-Path 'C:\Program Files\NASM\nasm.exe')) { throw 'nasm.exe not found in C:\Program Files\NASM' }
}

switch ($Task) {
    'Probe' { Invoke-Probe }
    'FreeDisk' { Invoke-FreeDisk }
    'Cygwin' { Invoke-Cygwin }
    'Tools' { Invoke-Tools }
}
