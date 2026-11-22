# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Test PDF for the HST PDF preview checks (dot-sourced by check-windows-pdf-preview*.ps1).
# A4 pages; page i (0-based) has a black 100 x 100 pt square at x = 50 + 100 i, 100 pt below the top edge.
function New-TestPdf([string]$path, [int]$pages) {
    $objects = @{ 1 = '<< /Type /Catalog /Pages 2 0 R >>' }
    $kids = @()
    for ($i = 0; $i -lt $pages; $i++) {
        $page = 3 + 2 * $i; $content = 4 + 2 * $i; $kids += "$page 0 R"
        $stream = "0 0 0 rg $(50 + 100 * $i) 642 100 100 re f"
        $objects[$page] = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents $content 0 R >>"
        $objects[$content] = "<< /Length $($stream.Length) >>`nstream`n$stream`nendstream"
    }
    $objects[2] = "<< /Type /Pages /Kids [$($kids -join ' ')] /Count $pages >>"
    $sb = New-Object System.Text.StringBuilder; [void]$sb.Append("%PDF-1.4`n"); $offsets = @{}
    foreach ($k in ($objects.Keys | Sort-Object)) { $offsets[$k] = $sb.Length; [void]$sb.Append("$k 0 obj`n$($objects[$k])`nendobj`n") }
    $xref = $sb.Length; $size = ($objects.Keys | Measure-Object -Maximum).Maximum + 1
    [void]$sb.Append("xref`n0 $size`n0000000000 65535 f `n")
    for ($k = 1; $k -lt $size; $k++) { [void]$sb.Append(("{0:D10} 00000 n `n" -f $offsets[$k])) }
    [void]$sb.Append("trailer`n<< /Size $size /Root 1 0 R >>`nstartxref`n$xref`n%%EOF`n")
    [IO.File]::WriteAllBytes($path, [Text.Encoding]::ASCII.GetBytes($sb.ToString()))
}
