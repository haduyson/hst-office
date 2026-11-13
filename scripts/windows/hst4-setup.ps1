# SPDX-License-Identifier: AGPL-3.0-only
<#
One-time toolchain for a local Windows build PC (HST4) that builds the same MSI as
.github/workflows/desktop-windows.yml. Run elevated (kiemtra over SSH, or detached with hst4-detach.ps1):
  powershell -File scripts\windows\hst4-setup.ps1 [-Step All | -Step Cygwin,Tools,...]  (Defender Prereqs VisualStudio Cygwin Tools Python Report)
Used for every local Windows build PC (HST4, HST5). Prereqs installs Chocolatey (CI's source for NASM and pkgconfiglite)
and Git for Windows when they are missing.
Steps are idempotent. Everything big goes to D: (8.3 names are off there, so no path may contain a space);
the Windows SDK and the VS installer itself always land on C:, which must keep -MinFreeCGiB free.
#>
[CmdletBinding()]
param(
    # Comma-separated so it survives `powershell -File`: All or any of Defender,Prereqs,VisualStudio,Cygwin,Tools,Python,Report.
    [ValidatePattern('^(All|Defender|Prereqs|VisualStudio|Cygwin|Tools|Python|Report)(,(Defender|Prereqs|VisualStudio|Cygwin|Tools|Python|Report))*$')][string]$Step = 'All',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$Root = 'D:\hst-build',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$CygwinRoot = 'D:\cygwin64',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$VsPath = 'D:\VS2022BT',
    [int]$MinFreeCGiB = 3
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # Invoke-WebRequest is many times slower with the progress bar

# The runner image (windows-2022, VS 2022 Enterprise) provides these; configure.log of a CI build shows each one in use:
# MSVC v143 + ATL (Spectre libs are preferred when present), clang-cl for Skia, MSVC merge modules for the MSI,
# CMake/Ninja for externals, Windows SDK 10.0.26100 (midl, MSI tools, UCRT) and .NET Framework 4.8.1 SDK (al.exe, cli_ure).
$VsComponents = @(
    'Microsoft.VisualStudio.Workload.VCTools',
    'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    'Microsoft.VisualStudio.Component.VC.ATL',
    'Microsoft.VisualStudio.Component.VC.Runtimes.x86.x64.Spectre',
    'Microsoft.VisualStudio.Component.VC.ATL.Spectre',
    'Microsoft.VisualStudio.Component.VC.Llvm.Clang',
    'Microsoft.VisualStudio.Component.VC.Redist.MSM',
    'Microsoft.VisualStudio.Component.VC.CMake.Project',
    'Microsoft.VisualStudio.Component.Windows11SDK.26100',
    'Microsoft.Net.Component.4.8.1.SDK',
    'Microsoft.Net.Component.4.8.1.TargetingPack'
)
$PythonVersion = '3.12.10'   # actions/setup-python '3.12' in the workflow
$PillowVersion = '10.4.0'    # pinned in the workflow's "Stage branding" step
$BuildWindows = Join-Path (Split-Path -Parent $PSScriptRoot) 'build-windows.ps1'
$Logs = Join-Path $Root 'logs\setup'
$Vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

function Write-Log([string]$Text) { Write-Output "[$(Get-Date -Format s)] $Text" }

function Assert-FreeC([double]$NeedGiB) {
    $free = (Get-PSDrive C).Free / 1GB
    if ($free - $NeedGiB -lt $MinFreeCGiB) {
        throw ('C: has {0:N1} GiB free; this step needs ~{1} GiB there and {2} GiB must stay free' -f $free, $NeedGiB, $MinFreeCGiB)
    }
}

function Get-SignedDownload([string]$Uri, [string]$OutFile) {
    Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutFile
    $sig = Get-AuthenticodeSignature -LiteralPath $OutFile
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        throw "bad signature on $OutFile`: $($sig.Status) $($sig.SignerCertificate.Subject)"
    }
}

function Invoke-Defender {
    $have = @((Get-MpPreference).ExclusionPath)
    foreach ($p in $Root, $CygwinRoot) {
        if ($have -contains $p) { Write-Log "Defender exclusion present: $p" }
        else { Add-MpPreference -ExclusionPath $p; Write-Log "Defender exclusion added: $p" }
    }
}

function Invoke-Prereqs {
    $choco = "$env:ProgramData\chocolatey\bin\choco.exe"
    if (-not (Test-Path -LiteralPath $choco)) {
        # Official install script; refuse it unless Chocolatey's Authenticode signature is valid.
        $script = Join-Path $Root 'setup\chocolatey-install.ps1'
        New-Item -ItemType Directory -Force -Path (Split-Path $script) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri 'https://community.chocolatey.org/install.ps1' -OutFile $script
        $sig = Get-AuthenticodeSignature -LiteralPath $script
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Chocolatey Software') {
            throw "chocolatey install.ps1 signature: $($sig.Status) $($sig.SignerCertificate.Subject)"
        }
        Assert-FreeC 1
        & $script
        if (-not (Test-Path -LiteralPath $choco)) { throw 'Chocolatey install failed' }
        Write-Log 'Chocolatey installed'
    } else { Write-Log 'Chocolatey present' }
    $env:Path = "$env:Path;$env:ProgramData\chocolatey\bin"
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue) -and -not (Test-Path 'C:\Program Files\Git\cmd\git.exe')) {
        & $choco install git --no-progress -y
        # choco can exit 0 after a failed feed lookup ("installed 0/0"): check the result itself.
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path 'C:\Program Files\Git\cmd\git.exe')) { throw "choco install git failed: $LASTEXITCODE" }
        Write-Log 'Git for Windows installed'
    } else { Write-Log 'Git present' }
}

function Get-VsInstance {
    if (-not (Test-Path -LiteralPath $Vswhere)) { return $null }
    $json = & $Vswhere -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | Out-String
    @($json | ConvertFrom-Json) | Where-Object { $_.installationPath -eq $VsPath } | Select-Object -First 1
}

function Invoke-VisualStudio {
    $bootstrap = Join-Path $Root 'setup\vs_buildtools.exe'
    New-Item -ItemType Directory -Force -Path (Split-Path $bootstrap), $Logs | Out-Null
    Assert-FreeC 6   # Windows SDK, .NET SDK, installer and VC redist cannot move off C:
    Get-SignedDownload 'https://aka.ms/vs/17/release/vs_buildtools.exe' $bootstrap
    $verb = if (Get-VsInstance) { 'modify' } else { $null }
    $vsArgs = @()
    if ($verb) { $vsArgs += $verb }
    $vsArgs += @('--quiet', '--wait', '--norestart', '--nocache', '--installPath', $VsPath)
    if (-not $verb) { $vsArgs += @('--path', "cache=$Root\setup\vs-cache", '--path', "shared=$VsPath-shared") }
    foreach ($c in $VsComponents) { $vsArgs += @('--add', $c) }
    Write-Log "vs_buildtools $($vsArgs -join ' ')"
    $p = Start-Process -FilePath $bootstrap -ArgumentList $vsArgs -Wait -PassThru
    Get-ChildItem $env:TEMP -Filter 'dd_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-6) } | Copy-Item -Destination $Logs -Force
    # 3010 = success, reboot recommended (not done here; the owner decides).
    if ($p.ExitCode -notin 0, 3010) { throw "vs_buildtools failed: exit $($p.ExitCode) (logs in $Logs)" }
    Write-Log "vs_buildtools exit $($p.ExitCode)"
    if (-not (Get-VsInstance)) { throw "VS Build Tools with VC tools not found at $VsPath after install" }
}

function Invoke-BuildWindows([string]$Task) {
    if (-not (Test-Path -LiteralPath $BuildWindows)) { throw "missing $BuildWindows (run from a repository checkout)" }
    & $BuildWindows -Task $Task -Work $Root -CygwinRoot $CygwinRoot
}

function Invoke-Python {
    $dir = Join-Path $Root 'tools\python'
    $exe = Join-Path $dir 'tools\python.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        # NuGet "python" package: a complete CPython with pip that needs no installer, registry or PATH change.
        $pkg = Join-Path $Root "setup\python.$PythonVersion.nupkg"
        New-Item -ItemType Directory -Force -Path (Split-Path $pkg) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri "https://api.nuget.org/v3-flatcontainer/python/$PythonVersion/python.$PythonVersion.nupkg" -OutFile $pkg
        $zip = [IO.Path]::ChangeExtension($pkg, '.zip')
        Move-Item -LiteralPath $pkg -Destination $zip -Force
        Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force
        $sig = Get-AuthenticodeSignature -LiteralPath $exe
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw "python.exe signature: $($sig.Status) $($sig.SignerCertificate.Subject)"
        }
    }
    & $exe -m pip install --disable-pip-version-check --no-warn-script-location "pillow==$PillowVersion"
    if ($LASTEXITCODE -ne 0) { throw 'pip install pillow failed' }
}

function Invoke-Report {
    $vs = Get-VsInstance
    Write-Output "### build toolchain on $env:COMPUTERNAME"
    if ($vs) { Write-Output "- VS: $($vs.displayName) $($vs.installationVersion) at $($vs.installationPath)" }
    else { Write-Output "- VS: not installed at $VsPath" }
    $msvc = Get-ChildItem "$VsPath\VC\Tools\MSVC" -Directory -ErrorAction SilentlyContinue
    Write-Output "- MSVC toolsets: $(($msvc.Name) -join ', '); ATL Spectre libs: $(Test-Path "$VsPath\VC\Tools\MSVC\*\atlmfc\lib\spectre\x64")"
    $clang = "$VsPath\VC\Tools\Llvm\bin\clang-cl.exe"
    if (Test-Path $clang) { Write-Output "- clang-cl: $((& $clang --version | Select-Object -First 1))" }
    Write-Output "- merge modules: $(Test-Path "$VsPath\VC\Redist\MSVC\v143\MergeModules"); CMake: $(Test-Path "$VsPath\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe")"
    $kits = "${env:ProgramFiles(x86)}\Windows Kits\10"
    Write-Output "- Windows SDKs: $((Get-ChildItem "$kits\Include" -Directory -ErrorAction SilentlyContinue).Name -join ', ')"
    $msiTools = foreach ($t in 'msidb.exe', 'msiinfo.exe', 'msitran.exe', 'msimsp.exe', 'uuidgen.exe', 'midl.exe') {
        "$t=$(Test-Path "$kits\bin\*\x*\$t")"   # MSI tools ship as x86 only
    }
    Write-Output "- SDK tools: $($msiTools -join ' ')"
    Write-Output "- .NET Framework SDKs: $((Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\NETFXSDK" -Directory -ErrorAction SilentlyContinue).Name -join ', ')"
    $bash = Join-Path $CygwinRoot 'bin\bash.exe'
    if (Test-Path $bash) {
        Write-Output '- Cygwin:'
        # No double quotes inside -c (Windows PowerShell 5.1 mangles them).
        & $bash --login -c 'uname -r; for t in make perl python3 flex bison gperf patch rsync git; do echo $t: $($t --version 2>&1 | head -1); done'
    }
    foreach ($t in "$Root\bin\make.exe", "$Root\bin\pkgconf-2.4.3.exe", 'C:\Program Files\NASM\nasm.exe', "$Root\tools\python\tools\python.exe") {
        $v = if (Test-Path $t) { (& $t --version 2>&1 | Select-Object -First 1) } else { 'MISSING' }
        Write-Output "- $t : $v"
    }
    Write-Output ('- free: C: {0:N1} GiB, D: {1:N1} GiB' -f ((Get-PSDrive C).Free / 1GB), ((Get-PSDrive D).Free / 1GB))
    Write-Output "- Defender exclusions include build dirs: $(@((Get-MpPreference).ExclusionPath) -contains $Root) / $(@((Get-MpPreference).ExclusionPath) -contains $CygwinRoot)"
}

$steps = $Step -split ','
$all = $steps -contains 'All'
New-Item -ItemType Directory -Force -Path $Root, $Logs | Out-Null
foreach ($s in 'Defender', 'Prereqs', 'VisualStudio', 'Cygwin', 'Tools', 'Python', 'Report') {
    if (-not ($all -or $steps -contains $s)) { continue }
    Write-Log "== $s"
    switch ($s) {
        'Defender' { Invoke-Defender }
        'Prereqs' { Invoke-Prereqs }
        'VisualStudio' { Invoke-VisualStudio }
        'Cygwin' { Assert-FreeC 0; Invoke-BuildWindows 'Cygwin' }
        'Tools' { Assert-FreeC 0.5; Invoke-BuildWindows 'Tools' }
        'Python' { Invoke-Python }
        'Report' { Invoke-Report }
    }
}
Write-Log 'setup done'
