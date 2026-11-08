# SPDX-License-Identifier: AGPL-3.0-only
$ErrorActionPreference = 'Stop'
choco install poppler --yes --no-progress
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$pdfTool = Get-ChildItem C:\ProgramData\chocolatey\lib -Recurse -Filter pdftoppm.exe | Select-Object -First 1
if (!$pdfTool) { throw 'Thiếu công cụ đọc PDF' }
$pdfTool.DirectoryName | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8
# Git Bash puts /mingw64/bin first, and Git for Windows ships xpdf's pdftotext (no -bbox-layout, exit 99):
# the probes put this poppler first on their own PATH.
"R1_POPPLER_BIN=$($pdfTool.DirectoryName)" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
# The runner agent's console sits mid-screen over every window: minimize it (never stop it).
Add-Type -Name Win -Namespace R1 -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);'
Get-Process | Where-Object { $_.MainWindowTitle -like '*hosted-compute-agent*' } |
  ForEach-Object { [void][R1.Win]::ShowWindow($_.MainWindowHandle, 6); "minimized $($_.ProcessName)" }
