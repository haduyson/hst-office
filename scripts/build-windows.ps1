# SPDX-License-Identifier: AGPL-3.0-only
# Inventory prerequisites and print the exact Cygwin configure command. No build is executed.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $RepoRoot 'build-config/windows-x86_64.conf'
$SourcePath = Join-Path $RepoRoot 'upstream/libreoffice'
function Stop-Blocked([string]$Reason) {
    [Console]::Error.WriteLine("BLOCKED: $Reason")
    exit 1
}
function Quote-Shell([string]$Value) {
    return "'" + $Value.Replace("'", "'`"'`"'") + "'"
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { Stop-Blocked "missing $ConfigPath" }
$ConfigureOptions = @(Get-Content -LiteralPath $ConfigPath | Where-Object { $_ -and -not $_.StartsWith('#') })
foreach ($Option in $ConfigureOptions) {
    if (-not $Option.StartsWith('--')) { Stop-Blocked 'invalid configure argument' }
}
$Invocation = './autogen.sh ' + (($ConfigureOptions | ForEach-Object { Quote-Shell $_ }) -join ' ')
Write-Output "UNVERIFIED configure invocation (not executed; working directory: $SourcePath in Cygwin):"
Write-Output $Invocation
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Stop-Blocked 'requires Windows x86_64, Visual Studio 2022, Windows SDK 10.0 and Cygwin; native execution UNVERIFIED'
}
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    Stop-Blocked 'requires a native Windows x86_64 host and 64-bit PowerShell'
}
foreach ($Tool in @('cl.exe', 'link.exe', 'rc.exe', 'mt.exe', 'signtool.exe', 'bash.exe', 'cygpath.exe')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) { Stop-Blocked "missing $Tool; use VS 2022 x64 Native Tools with Cygwin" }
}
if (-not $env:VisualStudioVersion -or [version]$env:VisualStudioVersion -lt [version]'17.0') {
    Stop-Blocked 'Visual Studio 2022 >=17.0 is required'
}
if (-not $env:WindowsSDKVersion -or $env:WindowsSDKVersion -notmatch '^10\.0\.') {
    Stop-Blocked 'Windows SDK 10.0 is required'
}
$CompilerVersion = (Get-Item (Get-Command cl.exe).Source).VersionInfo.FileVersion
Write-Output "Compiler: $CompilerVersion; VS: $env:VisualStudioVersion; SDK: $env:WindowsSDKVersion"
$ShellPlatform = & bash.exe -lc 'uname -s'
if ($LASTEXITCODE -ne 0 -or $ShellPlatform -notmatch '^CYGWIN_NT') { Stop-Blocked 'bash.exe must be Cygwin, not WSL/Git Bash' }
& bash.exe -lc 'set -eu; for tool in autoconf automake make perl python3 pkg-config bison flex gperf zip; do command -v "$tool" >/dev/null; done; uname -a'
if ($LASTEXITCODE -ne 0) { Stop-Blocked 'missing required Cygwin configure/build tools' }
$DriveRoot = [IO.Path]::GetPathRoot($RepoRoot)
$Disk = [IO.DriveInfo]::new($DriveRoot)
if ($Disk.AvailableFreeSpace -lt 100000000000) { Stop-Blocked 'OPS-01: at least 100 GB free disk required' }
$Machine = Get-CimInstance Win32_ComputerSystem
if ($Machine.TotalPhysicalMemory -lt 16GB) { Stop-Blocked 'OPS-01: at least 16 GiB RAM required' }
foreach ($File in @('configure.ac', 'autogen.sh')) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourcePath $File) -PathType Leaf)) { Stop-Blocked 'missing pinned LibreOffice source checkout' }
}
foreach ($Asset in @('intro.png', 'about.svg', 'logo.svg')) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "branding/libreoffice/$Asset") -PathType Leaf)) {
        Stop-Blocked "missing branding asset: $Asset"
    }
}
Write-Output 'Prerequisite inventory complete; configure was not executed.'
Stop-Blocked 'TODO: needs validated HST patch integration, signing credentials, MSI lifecycle tests and platform QA (SIGN-01, QA-01)'
