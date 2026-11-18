# SPDX-License-Identifier: AGPL-3.0-only
<#
.SYNOPSIS
  HST PDF preview handler and thumbnail provider on an installed HST Office (Windows).

.DESCRIPTION
  -Mode Snapshot -State FILE   save the PDF-related shell registrations (before installing HST Office).
  -Mode Installed [-Out DIR]   after installing: the registrations are present and leave other programs'
                               handlers alone; a 3-page PDF renders as a thumbnail (directly and through the
                               shell's thumbnail extraction) and in the preview handler, which scrolls through
                               all pages (scroll bar range, Page Down, mouse wheel, End). PNGs go to DIR.
  -Mode Removed -State FILE    after uninstalling: nothing of HST's is left and every value saved by Snapshot
                               is back as it was.
  Runs in a 64-bit PowerShell; needs no interactive session (the preview is drawn with WM_PRINTCLIENT).
  Exit code 0 when every check passes.
#>
param(
    [ValidateSet('Snapshot', 'Installed', 'Removed')][string]$Mode = 'Installed',
    [string]$State,
    [string]$Out = (Join-Path $env:TEMP 'hst-pdf-preview-check')
)
$ErrorActionPreference = 'Stop'
$PreviewIid = '{8895b1c6-b41f-4c1c-a562-0d564250836f}'
$ThumbIid = '{e357fccd-a995-4576-b01f-234630154e96}'
$PreviewClsid = '{6058E664-567B-4207-82EE-F250B8F88276}'
$ThumbClsid = '{61440647-9253-4376-A0B3-66622FA3B055}'
$script:failures = 0
function Check([bool]$ok, [string]$what) {
    if ($ok) { "PASS $what" } else { "FAIL $what"; $script:failures++ }
}
function DefaultValue([string]$path) {
    $key = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
    if ($key) { $key.GetValue('') } else { $null }
}
# Values that decide which PDF preview/thumbnail handler the shell uses, and HST's own.
function Registrations {
    $r = [ordered]@{}
    foreach ($place in @('.pdf', 'SystemFileAssociations\.pdf', 'HSTOffice.Pdf')) {
        foreach ($iid in @($PreviewIid, $ThumbIid)) {
            $r["HKLM:\SOFTWARE\Classes\$place\ShellEx\$iid"] = DefaultValue "HKLM:\SOFTWARE\Classes\$place\ShellEx\$iid"
        }
    }
    foreach ($clsid in @($PreviewClsid, $ThumbClsid)) {
        $r["CLSID $clsid"] = DefaultValue "HKLM:\SOFTWARE\Classes\CLSID\$clsid\InprocServer32"
    }
    $r['PreviewHandlers'] = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\PreviewHandlers' -ErrorAction SilentlyContinue).$PreviewClsid
    $r
}

if ($Mode -eq 'Snapshot') {
    if (-not $State) { throw '-State FILE is required' }
    Registrations | ConvertTo-Json | Set-Content -LiteralPath $State -Encoding UTF8
    Registrations | Format-Table -AutoSize | Out-String -Width 220
    exit 0
}

if ($Mode -eq 'Removed') {
    if (-not $State) { throw '-State FILE is required' }
    $before = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
    $now = Registrations
    foreach ($name in $now.Keys) {
        $was = $before.$name
        Check ("$($now[$name])" -eq "$was") "after uninstall $name is back to '$was' (now '$($now[$name])')"
    }
    foreach ($clsid in @($PreviewClsid, $ThumbClsid)) {
        Check (-not (Test-Path "HKLM:\SOFTWARE\Classes\CLSID\$clsid")) "CLSID $clsid removed"
    }
    Check (-not (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved' -ErrorAction SilentlyContinue).$PreviewClsid) 'Approved entry removed'
    "$script:failures failures"
    exit [int]($script:failures -ne 0)
}

# ---- Installed ----
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

namespace HstPdfPreviewCheck {
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
[StructLayout(LayoutKind.Sequential)] public struct SIZE { public int cx, cy; }
[StructLayout(LayoutKind.Sequential)] public struct SCROLLINFO { public uint cbSize, fMask; public int nMin, nMax; public uint nPage; public int nPos, nTrackPos; }

[ComImport, Guid("b824b49d-22ac-4161-ac8a-9916e8fa3f7f"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IInitializeWithStream { void Initialize(IStream stream, uint mode); }
[ComImport, Guid("e357fccd-a995-4576-b01f-234630154e96"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IThumbnailProvider { void GetThumbnail(uint cx, out IntPtr hbmp, out int alpha); }
[ComImport, Guid("8895b1c6-b41f-4c1c-a562-0d564250836f"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPreviewHandler {
    void SetWindow(IntPtr hwnd, ref RECT rect); void SetRect(ref RECT rect); void DoPreview(); void Unload();
    void SetFocus(); void QueryFocus(out IntPtr hwnd); [PreserveSig] int TranslateAccelerator(IntPtr msg); }
[ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IShellItemImageFactory { [PreserveSig] int GetImage(SIZE size, int flags, out IntPtr hbmp); }

public static class Native {
    [DllImport("ole32.dll", PreserveSig = false)]
    public static extern void CoCreateInstance(ref Guid clsid, IntPtr outer, uint context, ref Guid iid,
        [MarshalAs(UnmanagedType.IUnknown)] out object obj);
    [DllImport("shlwapi.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    public static extern void SHCreateStreamOnFileEx(string file, uint mode, uint attributes, bool create,
        IStream template, out IStream stream);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    public static extern void SHCreateItemFromParsingName(string path, IntPtr bc, ref Guid iid,
        [MarshalAs(UnmanagedType.IUnknown)] out object item);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateWindowExW(uint exStyle, string cls, string name, uint style, int x, int y,
        int w, int h, IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);
    [DllImport("user32.dll")] public static extern bool DestroyWindow(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindowExW(IntPtr parent, IntPtr after, string cls, string name);
    [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool GetScrollInfo(IntPtr hwnd, int bar, ref SCROLLINFO info);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hwnd, out RECT rect);
    [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);

    public static object Create(string clsid, Guid iid) {
        Guid c = new Guid(clsid); object o; CoCreateInstance(ref c, IntPtr.Zero, 1 /* INPROC_SERVER */, ref iid, out o); return o;
    }
    public static IStream Open(string path) { IStream s; SHCreateStreamOnFileEx(path, 0x20 /* READ|SHARE_DENY_WRITE */, 0, false, null, out s); return s; }

    public static Bitmap Thumbnail(string clsid, string path, uint size) {
        object o = Create(clsid, typeof(IInitializeWithStream).GUID);
        IStream s = Open(path);
        try {
            ((IInitializeWithStream)o).Initialize(s, 0);
            IntPtr h; int alpha; ((IThumbnailProvider)o).GetThumbnail(size, out h, out alpha);
            try { return Image.FromHbitmap(h); } finally { DeleteObject(h); }
        } finally { Marshal.ReleaseComObject(o); Marshal.ReleaseComObject(s); }
    }
    public static Bitmap ShellThumbnail(string path, int size) {
        Guid iid = typeof(IShellItemImageFactory).GUID; object item;
        SHCreateItemFromParsingName(path, IntPtr.Zero, ref iid, out item);
        IntPtr h; SIZE s; s.cx = size; s.cy = size;
        int hr = ((IShellItemImageFactory)item).GetImage(s, 0x8 /* SIIGBF_THUMBNAILONLY */, out h);
        if (hr != 0) throw new COMException("IShellItemImageFactory::GetImage", hr);
        try { return Image.FromHbitmap(h); } finally { DeleteObject(h); }
    }
    public static Bitmap Capture(IntPtr hwnd) {
        RECT r; GetClientRect(hwnd, out r);
        Bitmap b = new Bitmap(r.Right, r.Bottom);
        using (Graphics g = Graphics.FromImage(b)) {
            IntPtr dc = g.GetHdc();
            SendMessageW(hwnd, 0x0318 /* WM_PRINTCLIENT */, dc, (IntPtr)0x4 /* PRF_CLIENT */);
            g.ReleaseHdc(dc);
        }
        return b;
    }
    public static SCROLLINFO Scroll(IntPtr hwnd) {
        SCROLLINFO i = new SCROLLINFO(); i.cbSize = (uint)Marshal.SizeOf(i); i.fMask = 0x17; /* RANGE|PAGE|POS */
        GetScrollInfo(hwnd, 1 /* SB_VERT */, ref i); return i;
    }
    // One preview handler instance shown in parent (PowerShell cannot cast the RCW to these interfaces).
    public sealed class Preview {
        object handler; IStream stream;
        public Preview(string clsid, string path, IntPtr parent, int width, int height) {
            handler = Create(clsid, typeof(IPreviewHandler).GUID);
            stream = Open(path);
            ((IInitializeWithStream)handler).Initialize(stream, 0);
            RECT r = new RECT(); r.Right = width; r.Bottom = height;
            ((IPreviewHandler)handler).SetWindow(parent, ref r);
            ((IPreviewHandler)handler).DoPreview();
        }
        // Unloads, then drops this side's stream reference: the file is free only if the handler let go too.
        public void Unload() {
            ((IPreviewHandler)handler).Unload();
            Marshal.ReleaseComObject(stream); Marshal.ReleaseComObject(handler);
        }
    }
    // Share of dark pixels in a box given as fractions of the bitmap.
    public static double Dark(Bitmap b, double x0, double y0, double x1, double y1) {
        int n = 0, dark = 0;
        for (int y = (int)(y0 * b.Height); y < (int)(y1 * b.Height); y++)
            for (int x = (int)(x0 * b.Width); x < (int)(x1 * b.Width); x++) {
                Color c = b.GetPixel(x, y); n++; if (c.R + c.G + c.B < 150) dark++; }
        return n == 0 ? 0 : (double)dark / n;
    }
}
}
'@

New-Item -ItemType Directory -Force -Path $Out | Out-Null
. (Join-Path $PSScriptRoot 'pdf-preview-fixture.ps1')
$pdf = Join-Path $Out ("three-pages-{0}.pdf" -f [DateTime]::Now.ToString('HHmmssfff'))  # fresh name: no cached thumbnail
New-TestPdf $pdf 3
$broken = Join-Path $Out 'broken.pdf'
[IO.File]::WriteAllText($broken, 'not a PDF')

# Registrations
$reg = Registrations
$dll = $reg["CLSID $PreviewClsid"]
Check ($dll -and $dll -like '*\program\shlxthdl\hstpdfpreview.dll' -and (Test-Path -LiteralPath $dll)) "preview CLSID InprocServer32 = $dll"
Check ($dll -and $reg["CLSID $ThumbClsid"] -eq $dll) 'thumbnail CLSID uses the same DLL'
Check ($dll -and (Test-Path -LiteralPath (Join-Path (Split-Path (Split-Path $dll)) 'pdfiumlo.dll'))) 'pdfiumlo.dll is in the program directory'
Check ((DefaultValue "HKLM:\SOFTWARE\Classes\CLSID\$PreviewClsid" ) -ne $null -and (Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$PreviewClsid").AppID -eq '{6d2b5079-2f0b-48dd-ab7f-97cec514d30b}') 'preview handler runs in prevhost.exe (AppID)'
Check ($reg['PreviewHandlers'] -ne $null) 'listed under PreviewHandlers'
Check ($reg["HKLM:\SOFTWARE\Classes\HSTOffice.Pdf\ShellEx\$PreviewIid"] -eq $PreviewClsid) 'HSTOffice.Pdf preview handler'
Check ($reg["HKLM:\SOFTWARE\Classes\HSTOffice.Pdf\ShellEx\$ThumbIid"] -eq $ThumbClsid) 'HSTOffice.Pdf thumbnail provider'
foreach ($iid in @($PreviewIid, $ThumbIid)) {
    $ext = $reg["HKLM:\SOFTWARE\Classes\.pdf\ShellEx\$iid"]
    Check ($ext -ne $PreviewClsid -and $ext -ne $ThumbClsid) ".pdf\ShellEx\$iid is not HST's (it is '$ext')"
}
if ($State -and (Test-Path -LiteralPath $State)) {
    # Slots another program had before the install keep their value; empty ones may be HST's.
    $before = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
    foreach ($name in $reg.Keys | Where-Object { $_ -like 'HKLM:*' -and $_ -notlike '*HSTOffice.Pdf*' }) {
        $was = $before.$name
        if ($was) { Check ($reg[$name] -eq $was) "$name kept '$was'" }
    }
}

# Thumbnail provider, in-process
try {
    $thumb = [HstPdfPreviewCheck.Native]::Thumbnail($ThumbClsid, $pdf, 256)
    $thumb.Save((Join-Path $Out 'thumbnail-direct.png'))
    Check ($thumb.Height -eq 256 -and [Math]::Abs($thumb.Width - 181) -le 1) "thumbnail fits 256 px ($($thumb.Width)x$($thumb.Height))"
    # page 1's square: x 50..150 of 595 pt, y 100..200 of 842 pt
    Check ([HstPdfPreviewCheck.Native]::Dark($thumb, 0.10, 0.14, 0.23, 0.22) -gt 0.9) 'thumbnail shows page 1 square'
    Check ([HstPdfPreviewCheck.Native]::Dark($thumb, 0.30, 0.30, 0.95, 0.95) -lt 0.01) 'thumbnail is white elsewhere'
} catch { Check $false "thumbnail provider: $_" }
try {
    [void][HstPdfPreviewCheck.Native]::Thumbnail($ThumbClsid, $broken, 256)
    Check $false 'broken PDF gives no thumbnail'
} catch {
    $hr = $_.Exception.InnerException.HResult
    Check ($hr -eq -2147467259) ('broken PDF gives no thumbnail (E_FAIL, got 0x{0:X8})' -f $hr)
}

# Thumbnail through the shell (registration lookup and the isolated surrogate); only when the shell picks
# HST's provider: another program's provider may own the slot on this machine.
$assoc = $reg["HKLM:\SOFTWARE\Classes\.pdf\ShellEx\$ThumbIid"]
if (-not $assoc -or $assoc -eq $ThumbClsid) {
    try {
        $shell = [HstPdfPreviewCheck.Native]::ShellThumbnail($pdf, 256)
        $shell.Save((Join-Path $Out 'thumbnail-shell.png'))
        Check ([HstPdfPreviewCheck.Native]::Dark($shell, 0.10, 0.14, 0.23, 0.22) -gt 0.9) "shell thumbnail shows page 1 square ($($shell.Width)x$($shell.Height))"
    } catch { Check $false "shell thumbnail: $_" }
} else { "SKIP shell thumbnail: .pdf uses another provider ($assoc)" }

# Preview handler, in-process, in a plain parent window
$parent = [HstPdfPreviewCheck.Native]::CreateWindowExW(0, 'Static', 'hst-pdf-preview-check', 2147483648, 0, 0, 500, 700, [IntPtr]::Zero, [IntPtr]::Zero, [IntPtr]::Zero, [IntPtr]::Zero)
try {
    $previewPdf = $pdf -replace '\.pdf$', '-preview.pdf'  # its own file: only the handler can hold it open
    Copy-Item -LiteralPath $pdf -Destination $previewPdf
    $session = New-Object HstPdfPreviewCheck.Native+Preview($PreviewClsid, $previewPdf, $parent, 500, 700)
    $child = [HstPdfPreviewCheck.Native]::FindWindowExW($parent, [IntPtr]::Zero, 'HSTOfficePdfPreview', $null)
    Check ($child -ne [IntPtr]::Zero) 'preview window created'
    $info = [HstPdfPreviewCheck.Native]::Scroll($child)
    Check (($info.nMax + 1) -gt 2.5 * $info.nPage) "scroll range covers 3 pages (range $($info.nMax + 1), page $($info.nPage))"
    $top = [HstPdfPreviewCheck.Native]::Capture($child); $top.Save((Join-Path $Out 'preview-top.png'))
    $pageTop = 12 / $top.Height; $pageHeight = (($top.Width - 24) * 842 / 595) / $top.Height
    $squareTop = $pageTop + $pageHeight * 0.13; $squareBottom = $pageTop + $pageHeight * 0.225
    Check ([HstPdfPreviewCheck.Native]::Dark($top, 0.12, $squareTop, 0.24, $squareBottom) -gt 0.9) 'preview top shows page 1 square'
    [void][HstPdfPreviewCheck.Native]::SendMessageW($child, 0x115, [IntPtr]3, [IntPtr]::Zero)   # WM_VSCROLL SB_PAGEDOWN
    $afterPage = [HstPdfPreviewCheck.Native]::Scroll($child).nPos
    Check ($afterPage -gt 0) "Page Down scrolls ($afterPage px)"
    [void][HstPdfPreviewCheck.Native]::SendMessageW($child, 0x20A, [IntPtr]((-120) -shl 16), [IntPtr]::Zero)  # WM_MOUSEWHEEL down
    $afterWheel = [HstPdfPreviewCheck.Native]::Scroll($child).nPos
    Check ($afterWheel -gt $afterPage) "mouse wheel scrolls ($afterWheel px)"
    [void][HstPdfPreviewCheck.Native]::SendMessageW($child, 0x115, [IntPtr]7, [IntPtr]::Zero)   # SB_BOTTOM
    $end = [HstPdfPreviewCheck.Native]::Capture($child); $end.Save((Join-Path $Out 'preview-end.png'))
    # page 3's square spans x 250..350 of 595 pt (0.42..0.59 of the page width); page 1's x 0.08..0.25
    Check ([HstPdfPreviewCheck.Native]::Dark($end, 0.46, 0.0, 0.56, 1.0) -gt 0.03) 'preview end shows page 3 square'
    Check ([HstPdfPreviewCheck.Native]::Dark($end, 0.12, 0.0, 0.22, 1.0) -lt 0.005) 'preview end does not show page 1'
    $session.Unload()
    Check ([HstPdfPreviewCheck.Native]::FindWindowExW($parent, [IntPtr]::Zero, 'HSTOfficePdfPreview', $null) -eq [IntPtr]::Zero) 'Unload destroys the preview window'
    $locked = $false
    try { [IO.File]::Open($previewPdf, 'Open', 'ReadWrite', 'None').Close() } catch { $locked = $true }
    Check (-not $locked) 'Unload releases the file'

    $session = New-Object HstPdfPreviewCheck.Native+Preview($PreviewClsid, $broken, $parent, 500, 700)
    $child = [HstPdfPreviewCheck.Native]::FindWindowExW($parent, [IntPtr]::Zero, 'HSTOfficePdfPreview', $null)
    $msg = [HstPdfPreviewCheck.Native]::Capture($child); $msg.Save((Join-Path $Out 'preview-broken.png'))
    Check ([HstPdfPreviewCheck.Native]::Dark($msg, 0.0, 0.0, 1.0, 0.2) -gt 0.0005) 'broken PDF shows a message'
    $session.Unload()
} catch { Check $false "preview handler: $_" }
finally { [void][HstPdfPreviewCheck.Native]::DestroyWindow($parent) }

"$script:failures failures; images in $Out"
exit [int]($script:failures -ne 0)
