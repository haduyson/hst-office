# SPDX-License-Identifier: AGPL-3.0-only
# Install (or upgrade to) an HST Office MSI with its default options, as one quiet run of the user's installer:
# no properties are passed, so every default (features, ticked boxes) applies. Refuses while an office runs.
# Writes <Log>.json with the exit code, duration and the registered HST products before and after.
param(
    [Parameter(Mandatory = $true)][string]$Msi,
    [Parameter(Mandatory = $true)][string]$Log
)
$ErrorActionPreference = 'Stop'
function Get-HstProducts {
    @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object DisplayName -like 'HST Office*' |
        ForEach-Object { "$($_.DisplayName)|$($_.DisplayVersion)|$($_.PSChildName)|$($_.InstallLocation)" })
}
$report = [ordered]@{ msi = (Split-Path $Msi -Leaf); sha256 = (Get-FileHash $Msi -Algorithm SHA256).Hash; before = Get-HstProducts }
if (Get-Process soffice.bin, soffice -ErrorAction SilentlyContinue) {
    $report.error = 'an office is running; not installing'
    $report | ConvertTo-Json | Set-Content "$Log.json" -Encoding UTF8
    exit 5
}
$started = Get-Date
$proc = Start-Process msiexec.exe -ArgumentList @('/i', "`"$Msi`"", '/qn', '/norestart', '/l*v', "`"$Log`"") -Wait -PassThru
$report.exit_code = $proc.ExitCode  # 0 ok, 3010 ok but a restart is required, 1603 failure, 1618 another install runs
$report.seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
$report.after = Get-HstProducts
$report.c_free_gb = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
$tail = Get-Content $Log -Encoding Unicode -ErrorAction SilentlyContinue | Select-String -Pattern 'Return value 3|Installation success or error status|MainEngineThread is returning|RemoveExistingProducts|FindRelatedProducts' | Select-Object -Last 12
$report.log_lines = @($tail | ForEach-Object { $_.Line.Trim() })
$report | ConvertTo-Json -Depth 4 | Set-Content "$Log.json" -Encoding UTF8
$report | ConvertTo-Json -Depth 4
exit $proc.ExitCode
