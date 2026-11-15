# SPDX-License-Identifier: AGPL-3.0-only
# Lists the accessibility nodes of one HST Office process through MSAA (oleacc), for windows-ribbon-mockup.py.
# One line per node, depth-first: index, parent index (-1 for a root), depth, role, state, x, y, w, h, name (tab-separated).
# Reads only; sends no key and no mouse event. The tree is the one windows-msaa-ribbon.ps1 reads.
#   powershell -File windows-ribbon-nodes.ps1 -OfficePid 1234
param(
    [Parameter(Mandatory = $true)][int]$OfficePid
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text; using Accessibility;
public static class HstNodes {
  [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr h, uint id, ref Guid iid,
      [MarshalAs(UnmanagedType.Interface)] out object o);
  [DllImport("oleacc.dll")] static extern int AccessibleChildren(IAccessible a, int start, int n, [Out] object[] kids, out int got);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  public static List<IntPtr> Windows(uint pid) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
  static void Write(StringBuilder sb, ref int index, int parent, int depth, IAccessible a, object id) {
    int role = 0, state = 0, x = 0, y = 0, w = 0, h = 0; string name = "";
    try { name = a.get_accName(id) ?? ""; } catch {}
    try { role = Convert.ToInt32(a.get_accRole(id)); } catch {}
    try { state = Convert.ToInt32(a.get_accState(id)); } catch {}
    try { a.accLocation(out x, out y, out w, out h, id); } catch {}
    sb.Append(index).Append('\t').Append(parent).Append('\t').Append(depth).Append('\t').Append(role).Append('\t')
      .Append(state).Append('\t').Append(x).Append('\t').Append(y).Append('\t').Append(w).Append('\t').Append(h).Append('\t')
      .Append(name.Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' ')).Append('\n');
    index++;
  }
  static void Children(StringBuilder sb, ref int index, int parent, int depth, IAccessible a) {
    if (depth > 40) return;
    int n = 0; try { n = a.accChildCount; } catch { return; }
    if (n <= 0 || n > 600) return;
    var kids = new object[n]; int got = 0;
    try { AccessibleChildren(a, 0, n, kids, out got); } catch { got = 0; }
    for (int i = 0; i < got; i++) {
      int me = index;
      var c = kids[i] as IAccessible;
      if (c != null) {
        Write(sb, ref index, parent, depth, c, 0);
        Children(sb, ref index, me, depth + 1, c);
      } else {
        Write(sb, ref index, parent, depth, a, kids[i]);
      }
    }
  }
  public static string Dump(uint pid) {
    var sb = new StringBuilder(); int index = 0;
    foreach (var h in Windows(pid)) {
      Guid g = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71"); object o;
      if (AccessibleObjectFromWindow(h, 0xFFFFFFFC, ref g, out o) == 0 && o is IAccessible) {
        int root = index;
        Write(sb, ref index, -1, 0, (IAccessible)o, 0);
        Children(sb, ref index, root, 1, (IAccessible)o);
      }
    }
    return sb.ToString();
  }
}
'@
[Console]::Out.Write([HstNodes]::Dump([uint32]$OfficePid))
