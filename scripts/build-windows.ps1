# SPDX-License-Identifier: AGPL-3.0-only
# Runner setup helpers for the Windows trial build (windows-2022). Build steps live in scripts/windows/trial-build.sh.
#   pwsh -File scripts/build-windows.ps1 -Task Probe|FreeDisk|Cygwin|Tools [-Work C:\hst]
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Probe', 'FreeDisk', 'Cygwin', 'Tools')][string]$Task,
    [string]$Work = 'C:\hst'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$CygwinMirror = 'https://mirrors.kernel.org/sourceware/cygwin/'
$CygwinRoot = 'C:\cygwin64'
# Package set for the LibreOffice Windows build (wiki Development/BuildingOnWindows).
$CygwinPackages = 'autoconf,automake,bison,flex,gawk,gettext,gettext-devel,git,gperf,libtool,m4,make,patch,perl,pkg-config,python3,rsync,unzip,zip,curl,wget,cabextract,diffutils,findutils,grep,sed,tar,xz,ccache'
$MakeUrl = 'https://dev-www.libreoffice.org/bin/cygwin/make-4.2.1-msvc.exe'

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

function Invoke-Cygwin {
    New-Item -ItemType Directory -Force -Path $Work, "$Work\logs", "$Work\bin" | Out-Null
    $setup = "$Work\setup-x86_64.exe"
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.cygwin.com/setup-x86_64.exe' -OutFile $setup
    $sig = Get-AuthenticodeSignature $setup
    Write-Summary ("- Cygwin setup sha256 $((Get-FileHash $setup).Hash), signature $($sig.Status) $($sig.SignerCertificate.Subject)")
    if ($sig.Status -ne 'Valid') { throw "Cygwin setup signature invalid: $($sig.Status)" }
    $setupArgs = @('--quiet-mode', '--no-shortcuts', '--no-startmenu', '--no-desktop', '--only-site', '--site', $CygwinMirror,
        '--local-package-dir', "$Work\cygpkgs", '--root', $CygwinRoot, '--packages', $CygwinPackages)
    $p = Start-Process -FilePath $setup -ArgumentList $setupArgs -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "Cygwin setup failed: $($p.ExitCode)" }
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
    choco install nasm --no-progress -y
    if ($LASTEXITCODE -ne 0) { throw 'nasm install failed' }
    if (-not (Test-Path 'C:\Program Files\NASM\nasm.exe')) { throw 'nasm.exe not found in C:\Program Files\NASM' }
}

switch ($Task) {
    'Probe' { Invoke-Probe }
    'FreeDisk' { Invoke-FreeDisk }
    'Cygwin' { Invoke-Cygwin }
    'Tools' { Invoke-Tools }
}
