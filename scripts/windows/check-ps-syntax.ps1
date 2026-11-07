# Parse every PowerShell smoke script and fail on any syntax error, before anything is installed.
$ErrorActionPreference = 'Stop'
$bad = 0
foreach ($f in Get-ChildItem (Join-Path $PSScriptRoot '*.ps1')) {
  $errors = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$errors)
  foreach ($e in $errors) { Write-Host "$($f.Name):$($e.Extent.StartLineNumber): $($e.Message)"; $bad++ }
}
if ($bad) { throw "$bad PowerShell parse errors" }
