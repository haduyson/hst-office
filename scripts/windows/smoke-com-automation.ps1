# SPDX-License-Identifier: AGPL-3.0-only
# Windows smoke: HST Office's own automation names, with HST Office installed and no LibreOffice.
#   smoke-com-automation.ps1 -Out <dir>
# LibreOffice's ProgIDs (com.sun.star.ServiceManager, Writer.Application, Calc.Application) do not resolve.
# HSTOffice.ServiceManager creates the Desktop, writes a .docx and an .xlsx and loads them back;
# HSTOffice.Writer.Application opens the .docx and HSTOffice.Sheets.Application the .xlsx (VBA object model).
# Calls go through IDispatch by name ([System.__ComObject].InvokeMember: GetIDsOfNames + Invoke), which needs no type
# information. A PowerShell member access on the object instead ($o.Name(), even $o.GetType()) goes through PowerShell's
# COM binder, which asks IDispatch::GetTypeInfo and throws E_NOTIMPL ("The method or operation is not implemented"):
# the UNO bridge reports one type info but has none for plain UNO objects, and none of the Application objects' functions.
param([Parameter(Mandatory=$true)][string]$Out)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Out | Out-Null

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "ok: $Message"
}

function Invoke-Com($Object, [string]$Name, [object[]]$Arguments = @()) {
    , ([System.__ComObject].InvokeMember($Name, [Reflection.BindingFlags]::InvokeMethod, $null, $Object, $Arguments))
}

# A read as VB/VBScript does it (DISPATCH_METHOD | DISPATCH_PROPERTYGET): Documents and Workbooks are methods of the VBA
# Application (Documents([in] any Index)), which the bridge refuses for a bare DISPATCH_PROPERTYGET (DISP_E_MEMBERNOTFOUND).
function Get-Com($Object, [string]$Name, [object[]]$Arguments = @()) {
    , ([System.__ComObject].InvokeMember($Name, [Reflection.BindingFlags]'InvokeMethod, GetProperty', $null, $Object, $Arguments))
}

function Set-Com($Object, [string]$Name, $Value) {
    [System.__ComObject].InvokeMember($Name, [Reflection.BindingFlags]::SetProperty, $null, $Object, @($Value)) | Out-Null
}

function New-Prop($Manager, [string]$Name, $Value) {
    $p = Invoke-Com $Manager 'Bridge_GetStruct' @('com.sun.star.beans.PropertyValue')
    Set-Com $p 'Name' $Name
    Set-Com $p 'Value' $Value
    return $p
}

function ConvertTo-FileUrl([string]$Path) { 'file:///' + ($Path -replace '\\', '/') }

foreach ($old in 'com.sun.star.ServiceManager', 'Writer.Application', 'Calc.Application') {
    Assert ($null -eq [type]::GetTypeFromProgID($old)) "$old is not registered (LibreOffice's automation name)"
}
foreach ($new in 'HSTOffice.ServiceManager', 'HSTOffice.Writer.Application', 'HSTOffice.Sheets.Application') {
    Assert ($null -ne [type]::GetTypeFromProgID($new)) "$new is registered"
}

$text = 'HST Office COM'
$docx = Join-Path $Out 'com-automation.docx'
$xlsx = Join-Path $Out 'com-automation.xlsx'
Remove-Item -LiteralPath $docx, $xlsx -Force -ErrorAction SilentlyContinue

$sm = New-Object -ComObject HSTOffice.ServiceManager
$desktop = Invoke-Com $sm 'createInstance' @('com.sun.star.frame.Desktop')
Assert ($null -ne $desktop) 'HSTOffice.ServiceManager creates com.sun.star.frame.Desktop'
$hidden = [object[]]@(New-Prop $sm 'Hidden' $true)

$doc = Invoke-Com $desktop 'loadComponentFromURL' @('private:factory/swriter', '_blank', 0, $hidden)
Invoke-Com (Invoke-Com $doc 'getText') 'setString' @($text) | Out-Null
Invoke-Com $doc 'storeToURL' @((ConvertTo-FileUrl $docx), [object[]]@(New-Prop $sm 'FilterName' 'MS Word 2007 XML')) | Out-Null
Invoke-Com $doc 'close' @($true) | Out-Null
$doc = Invoke-Com $desktop 'loadComponentFromURL' @((ConvertTo-FileUrl $docx), '_blank', 0, $hidden)
$read = "$(Invoke-Com (Invoke-Com $doc 'getText') 'getString')"
Invoke-Com $doc 'close' @($true) | Out-Null
Assert ($read.Trim() -eq $text) "HSTOffice.ServiceManager writes and loads back a .docx ('$($read.Trim())')"

$sheet = Invoke-Com $desktop 'loadComponentFromURL' @('private:factory/scalc', '_blank', 0, $hidden)
$cell = Invoke-Com (Invoke-Com (Invoke-Com $sheet 'getSheets') 'getByIndex' @([int]0)) 'getCellByPosition' @([int]0, [int]0)
Invoke-Com $cell 'setString' @($text) | Out-Null
Invoke-Com $sheet 'storeToURL' @((ConvertTo-FileUrl $xlsx), [object[]]@(New-Prop $sm 'FilterName' 'Calc MS Excel 2007 XML')) | Out-Null
Invoke-Com $sheet 'close' @($true) | Out-Null
Assert (Test-Path -LiteralPath $xlsx) 'HSTOffice.ServiceManager writes an .xlsx'

$writer = New-Object -ComObject HSTOffice.Writer.Application
$wdoc = Invoke-Com (Get-Com $writer 'Documents') 'Open' @($docx)
$name = "$(Get-Com $wdoc 'Name')"
Invoke-Com $wdoc 'Close' @() | Out-Null
Assert ($name -eq 'com-automation.docx') "HSTOffice.Writer.Application opens the .docx ($name)"

$sheets = New-Object -ComObject HSTOffice.Sheets.Application
$book = Invoke-Com (Get-Com $sheets 'Workbooks') 'Open' @($xlsx)
$name = "$(Get-Com $book 'Name')"
Invoke-Com $book 'Close' @($false) | Out-Null
Assert ($name -eq 'com-automation.xlsx') "HSTOffice.Sheets.Application opens the .xlsx ($name)"

try { Invoke-Com $desktop 'terminate' | Out-Null } catch { Write-Host "terminate: $($_.Exception.Message)" }
Write-Host 'COM automation passed'
