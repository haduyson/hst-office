# SPDX-License-Identifier: AGPL-3.0-only
# Accessibility helper of check-windows-ribbon-launchers.py. It reads and presses HST Office's ribbon and dialog
# tabs through MSAA (oleacc, the tree that VCL's IAccessible2 bridge serves). It works on the windows of ONE office
# process (-OfficePid) or ONE window (-Hwnd), and never sends a key or a mouse event. UI Automation sees no
# VCL tree in a disconnected session, but MSAA does. Output is UTF-8, one result line.
#   -Action select-tab -Name <ribbon tab>   select the shown ribbon tab of that name
#   -Action press      -Name <button name>  default action of the shown button of that name (the smallest one when
#                                           several share it: a group launcher ↘ is the small one)
#   -Action selected   -Hwnd <dialog>       print the name of the dialog's selected tab (HST's dialogs list their tabs
#                                           vertically: the dialog's first list; other dialogs have page tabs)
#   -Action other-tab  -Hwnd <dialog> -Name <tab>   select the first tab of the dialog not named <tab>
#   -Action state      -Name <button name>  print the MSAA states of the shown buttons of that name (0x8 pressed)
#   -Action dump                            print the shown tab and button names
param(
    [Parameter(Mandatory = $true)][ValidateSet('select-tab', 'press', 'selected', 'other-tab', 'dump', 'tabs', 'state')][string]$Action,
    [int]$OfficePid = 0,
    [long]$Hwnd = 0,
    [string]$Name = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using Accessibility;
public static class HstMsaa {
  [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr h, uint id, ref Guid iid,
      [MarshalAs(UnmanagedType.Interface)] out object o);
  [DllImport("oleacc.dll")] static extern int AccessibleChildren(IAccessible a, int start, int n, [Out] object[] kids, out int got);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  public class Node { public int Role; public string Name; public int State; public int Area; public IAccessible Acc; public object Id; }
  public static List<IntPtr> Windows(uint pid) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
  public static List<Node> Walk(IntPtr h) {
    var r = new List<Node>(); Guid g = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71"); object o;
    if (AccessibleObjectFromWindow(h, 0xFFFFFFFC, ref g, out o) == 0 && o is IAccessible) Rec((IAccessible)o, 0, r);
    return r;
  }
  static Node Make(IAccessible a, object id) {
    var n = new Node { Acc = a, Id = id };
    try { n.Name = a.get_accName(id); } catch {}
    try { n.Role = Convert.ToInt32(a.get_accRole(id)); } catch {}
    try { n.State = Convert.ToInt32(a.get_accState(id)); } catch {}
    try { int x, y, w, hh; a.accLocation(out x, out y, out w, out hh, id); n.Area = w * hh; } catch {}
    return n;
  }
  static void Rec(IAccessible a, int depth, List<Node> r) {
    if (depth > 40) return;
    int n = 0; try { n = a.accChildCount; } catch { return; }
    if (n <= 0 || n > 600) return;
    var kids = new object[n]; int got = 0;
    try { AccessibleChildren(a, 0, n, kids, out got); } catch { got = 0; }
    if (got == 0) {  // a tab list of a dialog hands its tabs out one by one only
      for (int i = 1; i <= n; i++) { object k = null; try { k = a.get_accChild(i); } catch {} kids[i - 1] = k ?? (object)i; }
      got = n;
    }
    for (int i = 0; i < got; i++) {
      var c = kids[i] as IAccessible;
      if (c != null) { r.Add(Make(c, 0)); Rec(c, depth + 1, r); } else r.Add(Make(a, kids[i]));
    }
  }
}
'@
$PAGETAB, $BUTTON, $LIST, $LISTITEM, $SELECTED, $INVISIBLE, $OFFSCREEN = 37, 43, 33, 34, 0x2, 0x8000, 0x10000

function DialogTabs {
    # HST's tab dialogs show their tabs as a vertical list (the dialog's first list); others as page tabs
    $nodes = @(Nodes)
    $first = [Array]::FindIndex($nodes, [Predicate[object]] { param($n) $n.Role -eq $LIST })
    $items = @()
    if ($first -ge 0) {
        for ($i = $first + 1; $i -lt $nodes.Count -and $nodes[$i].Role -eq $LISTITEM; $i++) { $items += $nodes[$i] }
    }
    if ($items.Count) { return $items }
    return @($nodes | Where-Object { $_.Role -eq $PAGETAB })
}

function Nodes {
    $roots = if ($Hwnd) { @([IntPtr]$Hwnd) } else { [HstMsaa]::Windows([uint32]$OfficePid) }
    foreach ($h in $roots) {
        foreach ($n in [HstMsaa]::Walk($h)) { if (-not ($n.State -band ($INVISIBLE -bor $OFFSCREEN))) { $n } }
    }
}

function Shown($role, $wanted) { @(Nodes | Where-Object { $_.Role -eq $role -and ($wanted -eq $null -or $_.Name -eq $wanted) }) }

function Press($n) {
    if ($n.Role -in $LISTITEM, $PAGETAB) { $n.Acc.accSelect(3, $n.Id); return 'select' }  # TAKEFOCUS|TAKESELECTION
    try { $n.Acc.accDoDefaultAction($n.Id); return 'default' } catch { $n.Acc.accSelect(3, $n.Id); return 'select' }
}

switch ($Action) {
    'select-tab' {
        $tab = Shown $PAGETAB $Name | Select-Object -First 1
        if (-not $tab) { 'NOTFOUND'; exit 2 }
        'OK ' + (Press $tab)
    }
    'press' {
        $found = Shown $BUTTON $Name
        if (-not $found) { 'NOTFOUND'; exit 2 }
        $n = $found | Sort-Object { $_.Area } | Select-Object -First 1
        $about = ($found | ForEach-Object { '[0x{0:x},{1}]' -f $_.State, $_.Area }) -join ''
        'OK ' + $found.Count + $about + ' ' + (Press $n)
    }
    'selected' {
        $tab = DialogTabs | Where-Object { $_.State -band $SELECTED } | Select-Object -First 1
        if (-not $tab) { 'NOTFOUND'; exit 2 }
        'TAB ' + $tab.Name
    }
    'other-tab' {
        $tab = DialogTabs | Where-Object { $_.Name -ne $Name } | Select-Object -First 1
        if (-not $tab) { 'NOTFOUND'; exit 2 }
        'OK ' + $tab.Name + ' ' + (Press $tab)
    }
    'state' {
        'STATE ' + ((Shown $BUTTON $Name | ForEach-Object { '0x{0:x}' -f $_.State }) -join ' ')
    }
    'tabs' {
        $roots = if ($Hwnd) { @([IntPtr]$Hwnd) } else { [HstMsaa]::Windows([uint32]$OfficePid) }
        foreach ($h in $roots) {
            'WINDOW ' + $h + ' ' + (([HstMsaa]::Walk($h) | Select-Object -First 150 |
                ForEach-Object { '{0}:{1}[0x{2:x}]' -f $_.Role, $_.Name, $_.State }) -join ' | ')
        }
    }
    'dump' {
        'TABS ' + ((Shown $PAGETAB $null | ForEach-Object { '{0}[0x{1:x}]' -f $_.Name, $_.State }) -join ' | ')
        'SMALL BUTTONS ' + ((Shown $BUTTON $null | Where-Object { $_.Area -lt 900 } | ForEach-Object { '{0}[{1},0x{2:x}]' -f $_.Name, $_.Area, $_.State }) -join ' | ')
    }
}
