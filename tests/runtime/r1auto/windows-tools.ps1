# SPDX-License-Identifier: AGPL-3.0-only
$ErrorActionPreference = 'Stop'
choco install poppler --yes --no-progress
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$pdfTool = Get-ChildItem C:\ProgramData\chocolatey\lib -Recurse -Filter pdftoppm.exe | Select-Object -First 1
if (!$pdfTool) { throw 'Thiếu công cụ đọc PDF' }
$pdfTool.DirectoryName | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8
