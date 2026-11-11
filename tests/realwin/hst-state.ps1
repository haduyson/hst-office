# HST install/profile state: product registration, the console user's HST profile (hash and two keys only).
$ErrorActionPreference = 'Continue'
$out = [ordered]@{ computer = $env:COMPUTERNAME; time = (Get-Date).ToString('s') }
$out.products = @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | ? DisplayName -like 'HST Office*' | % { "$($_.DisplayName)|$($_.DisplayVersion)|$($_.PSChildName)|$($_.InstallLocation)" })
$user = $null
foreach ($row in (query user 2>$null) | Select-Object -Skip 1) { if ($row.TrimStart('>').Trim() -match '^(\S+)\s+console\s+\d+\s+Active') { $user = $Matches[1] } }
$out.console_user = $user
$sid = (New-Object System.Security.Principal.NTAccount($user)).Translate([System.Security.Principal.SecurityIdentifier]).Value
$home_ = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$sid").ProfileImagePath
$roaming = Join-Path $home_ 'AppData\Roaming'
$out.profiles = @()
foreach ($dir in Get-ChildItem $roaming -Directory -Filter 'HST*' -ErrorAction SilentlyContinue) {
  foreach ($xcu in Get-ChildItem $dir.FullName -Recurse -Filter registrymodifications.xcu -ErrorAction SilentlyContinue) {
    $text = Get-Content $xcu.FullName -Raw -Encoding UTF8
    $ui = [regex]::Match($text, 'Linguistic/General"><prop oor:name="UILocale"[^>]*>(?:<value>([^<]*)</value>|<value/>)').Groups[1].Value
    $sym = [regex]::Match($text, 'Common/Misc"><prop oor:name="SymbolStyle"[^>]*><value>([^<]*)</value>').Groups[1].Value
    $paths = [regex]::Matches($text, '<item oor:path="([^"]*)"><(?:prop|node) oor:name="([^"]*)"') | % { $_.Groups[1].Value + '/' + $_.Groups[2].Value } | Sort-Object -Unique
    $paths | Set-Content -Path ('C:\hst-test\realwin\profile-paths-' + (Get-Date -Format 'HHmmss') + '.txt') -Encoding UTF8
    $last = [regex]::Match($text, 'oor:name="LastCompatibilityCheckID"[^>]*><value>([^<]*)</value>').Groups[1].Value
    $out.profiles += [ordered]@{ path = $xcu.FullName.Replace($home_, '%USERPROFILE%'); sha256 = (Get-FileHash $xcu.FullName).Hash; bytes = $xcu.Length;
      modified = $xcu.LastWriteTime.ToString('s'); items = ([regex]::Matches($text, '<item ')).Count; unique_paths = @($paths).Count; UILocale = $ui; SymbolStyle = $sym; LastCompatibilityCheckID = $last }
  }
}
$out.office_processes = @(Get-Process soffice* -ErrorAction SilentlyContinue | % { "$($_.Id)|$($_.SessionId)|$($_.ProcessName)|$($_.StartTime)" })
$out.c_free_gb = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
$out | ConvertTo-Json -Depth 5
