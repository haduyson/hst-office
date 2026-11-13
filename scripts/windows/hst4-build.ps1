# SPDX-License-Identifier: AGPL-3.0-only
<#
Development/test build of the HST Office MSI on a local Windows PC (HST4), following the same steps as
.github/workflows/desktop-windows.yml. Official releases still come from CI. Toolchain: hst4-setup.ps1.
  powershell -File D:\hst-build\tools\scripts\windows\hst4-build.ps1 -Ref rc/1.0.2-batch1 [-ExpectSha <sha>] [-Jobs 28] [-Priority Normal] [-Clean] [-VerifyTree]
  powershell -File D:\hst-build\tools\scripts\windows\hst4-build.ps1 -Status
Parallel slots / build queue (scripts/build-queue.sh): every slot has its own -Root (D:\hst-build, D:\hst-build-s2, ...)
with its own repo\ lo\ stage\ pristine\ and build.lock; Cygwin, VS and Python stay under -ToolsRoot (D:\hst-build).
-OutName names the output folder (the queue passes its job name). -Modules sc,sw (TEST ONLY) runs
`make <module>.build` instead of the full make and writes a patch overlay zip (instdir files the build rewrote, with
apply-build-overlay.ps1 for an admin-install image) instead of an MSI; the slot needs one full build first.
Long builds: start it with hst4-detach.ps1 (scheduled task) so it survives the SSH session.
Layout under -Root (the same as the runner's D:\hst; all paths are free of spaces):
  repo\  checkout of -Ref       lo\  LibreOffice tree + workdir (kept between runs = incremental build)
  dl\  pinned tarballs (under -ToolsRoot, shared by all slots)  branding\  staged branding  bin\  native make, pkgconf  logs\ metrics\  trial-build.sh output
  pristine\<key>\ cached extract   stage\ last patched tree (see hst4-tree.sh)
  out\<ref>-<sha7>\  renamed MSI + SHA256SUMS + build-info.json   status.json  current state for -Status
Incremental: hst4-tree.sh re-applies the checkout's patch steps (its own trial-build.sh) on a cached extract and
copies only files whose content changed into lo\, so make rebuilds just what the commit changed. -Clean rebuilds
lo\ from scratch (only needed after a tarball change left stale upstream files in lo\).
#>
[CmdletBinding(DefaultParameterSetName = 'Build')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Build')][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$')][string]$Ref,
    [Parameter(ParameterSetName = 'Build')][ValidateRange(1, 256)][int]$Jobs = [Environment]::ProcessorCount,
    [Parameter(ParameterSetName = 'Build')][ValidateSet('Normal', 'BelowNormal', 'Idle')][string]$Priority = 'Normal',
    [Parameter(ParameterSetName = 'Build')][switch]$Clean,
    # Also compare the updated tree with a fresh extract+patch (adds ~10 min); see hst4-tree.sh.
    [Parameter(ParameterSetName = 'Build')][switch]$VerifyTree,
    # Fail unless -Ref resolves to this commit (prefix of at least 7 hex digits), e.g. the sha announced for a batch.
    [Parameter(ParameterSetName = 'Build')][ValidatePattern('^[0-9a-f]{7,40}$')][string]$ExpectSha = '',
    [Parameter(ParameterSetName = 'Build')][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9-]{0,59}$')][string]$OutName = '',
    [Parameter(ParameterSetName = 'Build')][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.+-]*(,[A-Za-z0-9][A-Za-z0-9_.+-]*)*$')][string]$Modules = '',
    [Parameter(Mandatory, ParameterSetName = 'Status')][switch]$Status,
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$Root = 'D:\hst-build',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$ToolsRoot = 'D:\hst-build',
    [ValidatePattern('^[A-Za-z]:\\[^ ]+$')][string]$CygwinRoot = 'D:\cygwin64',
    [string]$RepoUrl = 'https://github.com/haduyson/hst-office.git',
    [int]$MinFreeCGiB = 3,
    [int]$MinFreeDGiB = 45
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repo = Join-Path $Root 'repo'
$Lo = Join-Path $Root 'lo'
$StatusFile = Join-Path $Root 'status.json'
$Bash = Join-Path $CygwinRoot 'bin\bash.exe'
$Python = Join-Path $ToolsRoot 'tools\python\tools\python.exe'
$MsiDir = Join-Path $Lo 'workdir\installation\HSTOffice\msi\install\en-US_vi'   # "Collect installer" step

function Write-Log([string]$Text) { Write-Output "[$(Get-Date -Format s)] $Text" }

function ConvertTo-CygPath([string]$Path) { '/cygdrive/' + $Path.Substring(0, 1).ToLower() + $Path.Substring(2).Replace('\', '/') }

function Invoke-Native([string]$File, [string[]]$Arguments) {
    # Native stderr must not become a terminating error (Windows PowerShell 5.1 + 2>&1); the exit code decides.
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $File @Arguments 2>&1 | ForEach-Object { "$_" } }
    finally { $ErrorActionPreference = $eap }
    if ($LASTEXITCODE -ne 0) { throw "$(Split-Path -Leaf $File) $($Arguments -join ' ') exited $LASTEXITCODE" }
}

function Invoke-Cygwin([string]$Command) {
    # Windows PowerShell mangles embedded double quotes in native arguments; build paths have no spaces anyway.
    if ($Command.Contains('"')) { throw "double quote in Cygwin command: $Command" }
    Invoke-Native $Bash @('--login', '-o', 'igncr', '-c', $Command)
}

function Invoke-Trial([string]$Phase, [string]$Work) {
    # The checkout's own trial-build.sh, so every commit is built with the steps CI uses for it.
    $env:HST_WORK = ConvertTo-CygPath $Work
    Invoke-Cygwin "exec bash -o igncr $(ConvertTo-CygPath $Repo)/scripts/windows/trial-build.sh --$Phase"
}

function Remove-Tree([string]$Path) {
    if (Test-Path -LiteralPath $Path) { cmd.exe /c rd /s /q "$Path" | Out-Null }
    if (Test-Path -LiteralPath $Path) { throw "could not remove $Path" }
}

function Set-Status([string]$State, [string]$Step) {
    $script:Info.state = $State
    $script:Info.step = $Step
    $script:Info.updated = (Get-Date).ToString('s')
    $script:Info | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StatusFile -Encoding utf8
}

function Invoke-Step([string]$Name, [scriptblock]$Body) {
    Set-Status 'running' $Name
    Write-Log "== $Name"
    $t = Get-Date
    & $Body
    $script:Info.seconds[$Name] = [int]((Get-Date) - $t).TotalSeconds
    Write-Log "== $Name done in $($script:Info.seconds[$Name]) s"
}

function Show-Status {
    if (Test-Path -LiteralPath $StatusFile) { Get-Content -LiteralPath $StatusFile -Raw } else { 'no status.json yet' }
    Get-ScheduledTask -TaskName 'hst-build-*' -ErrorAction SilentlyContinue | ForEach-Object { "task $($_.TaskName): $($_.State)" }
    $progress = Join-Path $Root 'metrics\progress.jsonl'
    if (Test-Path -LiteralPath $progress) { "last progress sample: $(Get-Content -LiteralPath $progress -Tail 1)" }
    $log = Join-Path $Root 'logs\build.log'
    if (Test-Path -LiteralPath $log) {
        "build.log: $(@(Select-String -LiteralPath $log -Pattern '^\[build ').Count) [build ...] lines; tail:"
        Get-Content -LiteralPath $log -Tail 5
    }
    ('free: C: {0:N1} GiB, D: {1:N1} GiB' -f ((Get-PSDrive C).Free / 1GB), ((Get-PSDrive D).Free / 1GB))
}

function Assert-Space {
    $c = (Get-PSDrive C).Free / 1GB
    $d = (Get-PSDrive $Root.Substring(0, 1)).Free / 1GB
    if ($c -lt $MinFreeCGiB) { throw ('C: has {0:N1} GiB free, below {1} GiB' -f $c, $MinFreeCGiB) }
    # A full build needs ~30 GiB for workdir/instdir plus the stage copy; an incremental one far less.
    $need = if (Test-Path -LiteralPath (Join-Path $Lo 'workdir')) { 15 } else { $MinFreeDGiB }
    if ($d -lt $need) { throw ('{0} has {1:N1} GiB free, below {2} GiB' -f $Root.Substring(0, 2), $d, $need) }
}

function Sync-Repo {
    $git = (Get-Command git.exe).Source
    if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) {
        Invoke-Native $git @('-c', 'core.autocrlf=false', 'clone', '--no-checkout', $RepoUrl, $Repo)
    }
    Invoke-Native $git @('-C', $Repo, 'config', 'core.autocrlf', 'false')
    Invoke-Native $git @('-C', $Repo, 'fetch', '--force', '--no-tags', 'origin', $Ref)
    $sha = (& $git -C $Repo rev-parse 'FETCH_HEAD^{commit}').Trim()
    if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-f]{40}$') { throw "cannot resolve $Ref" }
    if ($ExpectSha -and -not $sha.StartsWith($ExpectSha)) { throw "$Ref is at $sha, expected $ExpectSha" }
    Invoke-Native $git @('-C', $Repo, 'checkout', '--force', '--detach', $sha)
    Invoke-Native $git @('-C', $Repo, 'clean', '-ffdxq')
    $script:Info.sha = $sha
}

function Sync-Tarballs {
    # Same lock and checksums as "Fetch and verify pinned source tarballs"; download only when one is missing or wrong.
    $dl = Join-Path $ToolsRoot 'dl'
    $lock = Get-Content -LiteralPath (Join-Path $Repo 'upstream\libreoffice-lock.json') -Raw | ConvertFrom-Json
    $stale = @($lock.tarballs | Where-Object {
            $f = Join-Path $dl $_.name
            -not (Test-Path -LiteralPath $f) -or (Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash -ne $_.sha256.ToUpper()
        })
    if ($stale.Count -eq 0) { Write-Log 'tarballs verified'; return }
    Invoke-Native $Python @('-I', (Join-Path $Repo 'scripts\windows\fetch-sources.py'), '--dest', ($dl -replace '\\', '/'))
}

function Sync-Tree {
    # hst4-tree.sh lives next to this script: the checkout may predate it.
    $env:HST_ROOT = ConvertTo-CygPath $Root
    $treeArgs = @(if ($Clean) { '--clean' }) + @(if ($VerifyTree) { '--verify' })
    Invoke-Cygwin "exec bash -o igncr $(ConvertTo-CygPath (Join-Path $PSScriptRoot 'hst4-tree.sh')) $($treeArgs -join ' ')"
}

function Invoke-Build {
    # Command-line variables in MAKEFLAGS override config_host.mk's PARALLELISM (CI's conf says 4) without touching the conf.
    $env:MAKEFLAGS = "PARALLELISM=$Jobs"
    $env:HST_BUILD_DEADLINE = [string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() + 3 * 86400)
    try { Invoke-Trial 'build' $Root }
    finally { Remove-Item Env:\MAKEFLAGS, Env:\HST_BUILD_DEADLINE -ErrorAction SilentlyContinue }
}

function Get-OutDir {
    if ($OutName) { return Join-Path $Root "out\$OutName" }
    $refName = if ($Ref -match '^[0-9a-f]{7,40}$') { 'commit' } else { $Ref -replace '[^A-Za-z0-9._-]', '-' }
    Join-Path $Root "out\$refName-$($script:Info.sha.Substring(0, 7))"
}

function Invoke-Modules {
    # Module names get .build (sc -> sc.build); names with '.' or '_' are make targets as they are.
    $targets = @($Modules -split ',' | ForEach-Object { if ($_ -match '[._]') { $_ } else { "$_.build" } })
    $env:MAKEFLAGS = "PARALLELISM=$Jobs"
    $env:HST_WORK = ConvertTo-CygPath $Root
    try { Invoke-Cygwin "exec bash -o igncr $(ConvertTo-CygPath (Join-Path $PSScriptRoot 'hst4-make-targets.sh')) $($targets -join ' ')" }
    finally { Remove-Item Env:\MAKEFLAGS -ErrorAction SilentlyContinue }
}

function Export-Overlay([datetime]$Since) {
    # TEST ONLY patch overlay: instdir files this module build rewrote (not sdk\), laid out like the install root.
    $inst = Join-Path $Lo 'instdir'
    $name = "HSTOffice-overlay-$($script:Info.sha.Substring(0, 10))-$($Modules -replace ',', '+')"
    $stage = Join-Path $Root "tmp\$name"
    Remove-Tree $stage
    $files = @(Get-ChildItem -LiteralPath $inst -Recurse -File | Where-Object {
            $_.LastWriteTime -ge $Since -and -not $_.FullName.StartsWith((Join-Path $inst 'sdk\'), 'OrdinalIgnoreCase') })
    $rels = foreach ($f in $files) {
        $rel = $f.FullName.Substring($inst.Length + 1)
        $dest = Join-Path $stage "files\$rel"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $dest
        $rel
    }
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    [IO.File]::WriteAllText((Join-Path $stage 'FILES'), ((@($rels) -join "`n") + "`n"))
    $sums = foreach ($rel in $rels) { "$((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $stage "files\$rel")).Hash.ToLower())  $rel" }
    [IO.File]::WriteAllText((Join-Path $stage 'SHA256SUMS'), ((@($sums) -join "`n") + "`n"))
    Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'overlay\apply-build-overlay.ps1') -Destination $stage
    @("HST Office patch overlay - TEST ONLY. Never ship it or install it on user machines.",
        "commit $($script:Info.sha); modules $Modules; built $(Get-Date -Format s) on $env:COMPUTERNAME in $Root",
        'Apply onto an administrative install image of a reference MSI of the same base:',
        '  msiexec /a HSTOffice_<release>_Win_x86-64_en-US_vi.msi /qn TARGETDIR=C:\hst-test\ref',
        '  powershell -File apply-build-overlay.ps1 -Image C:\hst-test\ref',
        "$(@($rels).Count) files: list in FILES, checksums in SHA256SUMS.") | Set-Content -LiteralPath (Join-Path $stage 'README.txt')
    $out = Get-OutDir
    Remove-Tree $out
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $zip = Join-Path $out "$name.zip"
    Compress-Archive -Path $stage -DestinationPath $zip
    Remove-Tree $stage
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLower()
    [IO.File]::WriteAllText((Join-Path $out 'SHA256SUMS'), "$hash  $name.zip`n")
    $script:Info.msi += [ordered]@{ name = "$name.zip"; bytes = (Get-Item $zip).Length; sha256 = $hash; files = @($rels).Count }
    $script:Info.out = $out
}

function Export-Msi([datetime]$Since) {
    # Same renaming and SHA256SUMS as the workflow's "Collect installer" step.
    $release = (& $Python -I (Join-Path $Repo 'scripts\write-hst-version.py') --release).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $release) { throw 'write-hst-version.py --release failed' }
    $msis = @(Get-ChildItem -LiteralPath $MsiDir -Filter '*.msi' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $Since })
    if ($msis.Count -eq 0) { throw "no MSI written by this build under $MsiDir" }
    $out = Get-OutDir
    Remove-Tree $out
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $sums = foreach ($m in $msis) {
        $name = ($m.Name -replace ' ', '') -replace '^HSTOffice_[0-9]+(\.[0-9]+)*_', "HSTOffice_${release}_"
        if ($name -notlike "HSTOffice_${release}_Win_x86-64_*.msi") { throw "unexpected installer name: $name" }
        Copy-Item -LiteralPath $m.FullName -Destination (Join-Path $out $name)
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out $name)).Hash.ToLower()
        $script:Info.msi += [ordered]@{ name = $name; bytes = $m.Length; sha256 = $hash }
        "$hash  $name"
    }
    # LF line endings like sha256sum, so `sha256sum -c SHA256SUMS` works on Linux too.
    [IO.File]::WriteAllText((Join-Path $out 'SHA256SUMS'), (($sums -join "`n") + "`n"))
    $script:Info.release = $release
    $script:Info.out = $out
}

if ($Status) { Show-Status; exit 0 }

New-Item -ItemType Directory -Force -Path $Root, (Join-Path $Root 'tmp') | Out-Null
foreach ($tool in $Bash, $Python, (Join-Path $ToolsRoot 'bin\make.exe')) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "missing $tool; run hst4-setup.ps1 first" }
}
# trial-build.sh puts <work>\bin (native make, pkgconf shim) first in PATH: a new slot root gets a copy.
if (-not (Test-Path -LiteralPath (Join-Path $Root 'bin\make.exe'))) {
    Copy-Item -Recurse -Force -LiteralPath (Join-Path $ToolsRoot 'bin') -Destination $Root
}
$lockFile = [IO.File]::Open((Join-Path $Root 'build.lock'), 'OpenOrCreate', 'ReadWrite', 'None')   # one build at a time
$script:Info = [ordered]@{ ref = $Ref; sha = ''; state = 'starting'; step = ''; jobs = $Jobs; priority = $Priority
    clean = [bool]$Clean; modules = $Modules; outName = $OutName; started = (Get-Date).ToString('s'); updated = ''; seconds = [ordered]@{}; msi = @(); release = ''; out = '' }
try {
    # Child processes (bash, make, cl, link) inherit the priority class; TEMP on D: keeps compiler/packager scratch off C:.
    (Get-Process -Id $PID).PriorityClass = $Priority
    $env:TEMP = $env:TMP = Join-Path $Root 'tmp'
    $env:CHERE_INVOKING = '1'
    # Pinned tarballs are shared by all slots (verified against the lock before use, never modified in place).
    $env:HST_DL = ConvertTo-CygPath (Join-Path $ToolsRoot 'dl')
    $env:HST_REPO = ConvertTo-CygPath $Repo
    Assert-Space
    $t0 = Get-Date
    Invoke-Step 'git' { Sync-Repo }
    Write-Log "building $Ref at $($script:Info.sha) with $Jobs jobs, priority $Priority"
    Invoke-Step 'tarballs' { Sync-Tarballs }
    Invoke-Step 'branding' { Invoke-Native $Python @('-I', (Join-Path $Repo 'scripts\stage-branding.py'), '--out', ((Join-Path $Root 'branding') -replace '\\', '/')) }
    Invoke-Step 'tools' { Invoke-Trial 'tools' $Root }
    Invoke-Step 'tree' { Sync-Tree }
    Invoke-Step 'configure' { Invoke-Trial 'configure' $Root }
    Invoke-Step 'fetch' { Invoke-Trial 'fetch' $Root }
    if ($Modules -and -not (Test-Path -LiteralPath (Join-Path $Lo 'instdir\program\soffice.exe'))) {
        throw "no complete build in $Root yet; -Modules needs one full build in this slot first"
    }
    $buildStart = Get-Date
    if ($Modules) {
        Invoke-Step 'build' { Invoke-Modules }
        Invoke-Step 'collect' { Export-Overlay $buildStart }
    } else {
        Invoke-Step 'build' { Invoke-Build }
        Invoke-Step 'collect' { Export-Msi $buildStart }
    }
    $script:Info.seconds['total'] = [int]((Get-Date) - $t0).TotalSeconds
    Set-Status 'done' ''
    Copy-Item -LiteralPath $StatusFile -Destination (Join-Path $script:Info.out 'build-info.json') -Force
    Write-Log "done: $($script:Info.out)"
} catch {
    $script:Info.error = "$_"
    Set-Status 'failed' $script:Info.step
    throw
} finally {
    $lockFile.Dispose()
}
