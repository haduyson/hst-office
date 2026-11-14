# SPDX-License-Identifier: AGPL-3.0-only
# The toolbar_two_rows_probe snapshot on Windows, through MSAA (oleacc), as a screen reader reads the office: its
# UNO window peers no longer offer XAccessible and its windows show no UI Automation tree. Prints one JSON object:
#   {"bars": [{"box": [x, y, w, h], "items": [[x, y, w, h], ...]}], "banners": [[x, y, w, h], ...]}
# in screen px, for the top windows of the soffice.bin processes started from -Install (never another office).
param([Parameter(Mandatory = $true)][string]$Install, [string]$TraceFile = '')
$ErrorActionPreference = 'Stop'
Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Accessibility;
public static class HstMsaa {
    [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr h, uint id, ref Guid iid,
        [MarshalAs(UnmanagedType.Interface)] out object acc);
    [DllImport("oleacc.dll")] static extern int AccessibleChildren(IAccessible parent, int start, int count,
        [Out] object[] children, out int got);
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    const int ROLE_TOOLBAR = 0x16, ROLE_SEPARATOR = 0x15, ROLE_WINDOW = 0x9, ROLE_CLIENT = 0xa, INVISIBLE = 0x8000, OFFSCREEN = 0x10000;
    public static List<int[]> Banners = new List<int[]>();
    public static List<KeyValuePair<int[], List<int[]>>> Bars = new List<KeyValuePair<int[], List<int[]>>>();

    static int[] Box(IAccessible a) {
        int x, y, w, h;
        try { a.accLocation(out x, out y, out w, out h, 0); } catch { return null; }
        return w > 0 && h > 0 ? new int[] { x, y, w, h } : null;
    }
    static bool Shown(IAccessible a) {
        try { return ((int)a.get_accState(0) & (INVISIBLE | OFFSCREEN)) == 0; } catch { return false; }
    }
    public static bool Debug = false;
    public static List<string> Trace = new List<string>();
    static int State(IAccessible a) { try { return (int)a.get_accState(0); } catch { return -1; } }
    static int Role(IAccessible a) { try { return Convert.ToInt32(a.get_accRole(0)); } catch { return 0; } }
    static List<IAccessible> Kids(IAccessible a) {
        var list = new List<IAccessible>();
        int n; try { n = a.accChildCount; } catch { return list; }
        if (n <= 0) return list;
        var kids = new object[Math.Min(n, 2000)]; int got;
        if (AccessibleChildren(a, 0, kids.Length, kids, out got) != 0) return list;
        for (int i = 0; i < got; i++) { var k = kids[i] as IAccessible; if (k != null) list.Add(k); }
        return list;
    }
    static void Walk(IAccessible a, int depth) {
        if (depth > 24 || !Shown(a)) return;
        int role = Role(a);
        string name = ""; try { name = a.get_accName(0) ?? ""; } catch { }
        // the banner: named "<solution> - <tagline>" with an em dash (window and client nodes carry the title, also with a dash)
        if (role != ROLE_WINDOW && role != ROLE_CLIENT && name.Contains(" \u2014 ")) {
            var b = Box(a); if (b != null) Banners.Add(b);
        }
        if (Debug) Trace.Add(depth + " role " + role + " state " + State(a) + " box " + string.Join(",", Box(a) ?? new int[0]) + " " + name);
        if (role == ROLE_TOOLBAR) {
            var box = Box(a); if (box == null) return;
            var items = new List<int[]>();
            foreach (var k in Kids(a)) {
                if (!Shown(k) || Role(k) == ROLE_SEPARATOR) continue;
                var b = Box(k); if (b != null) items.Add(b);
            }
            Bars.Add(new KeyValuePair<int[], List<int[]>>(box, items));
            return;
        }
        foreach (var k in Kids(a)) Walk(k, depth + 1);
    }
    public static void Run(int[] pids) {
        var guid = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71"); // IID_IAccessible
        EnumWindows((h, l) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (IsWindowVisible(h) && Array.IndexOf(pids, (int)pid) >= 0) {
                object acc;
                if (AccessibleObjectFromWindow(h, 0xFFFFFFFC, ref guid, out acc) == 0 && acc is IAccessible)
                    Walk((IAccessible)acc, 0); // OBJID_CLIENT
            }
            return true;
        }, IntPtr.Zero);
    }
}
'@
$pids = [int[]]@(Get-Process soffice.bin -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Install*" } |
    ForEach-Object { $_.Id })
[HstMsaa]::Debug = [bool]$TraceFile
[HstMsaa]::Run($pids)
if ($TraceFile) { [HstMsaa]::Trace | Set-Content -Encoding UTF8 $TraceFile }  # every node read, for diagnosis
$bars = New-Object System.Collections.ArrayList
foreach ($bar in [HstMsaa]::Bars) {
    $items = New-Object System.Collections.ArrayList
    foreach ($item in $bar.Value) { [void]$items.Add($item) }
    [void]$bars.Add([ordered]@{ box = $bar.Key; items = $items })
}
$banners = New-Object System.Collections.ArrayList
foreach ($banner in [HstMsaa]::Banners) { [void]$banners.Add($banner) }
[ordered]@{ bars = $bars; banners = $banners; pids = $pids } | ConvertTo-Json -Depth 6 -Compress
