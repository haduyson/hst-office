# SPDX-License-Identifier: AGPL-3.0-only
# Test-only fault injection for check-close-crash-handler-windows.py: an access violation on the main (oldest)
# thread of ONE soffice.bin that the caller started itself (it passes that pid). The thread is suspended, its return
# address pushed and RIP set to 0, so it faults as soon as it runs again; the office's own crash handler takes over.
# -WaitHwnd: armed first, faults the moment that window (the closing document window) is destroyed, +DelayMs.
param([Parameter(Mandatory = $true)][int]$ProcId, [long]$WaitHwnd = 0, [int]$DelayMs = 0)
$ErrorActionPreference = 'Stop'
if ((Get-Process -Id $ProcId).ProcessName -ne 'soffice.bin') { throw "pid $ProcId is not soffice.bin" }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class HstFault {
  [DllImport("kernel32")] static extern IntPtr OpenThread(int a, bool i, int id);
  [DllImport("kernel32")] static extern IntPtr OpenProcess(int a, bool i, int id);
  [DllImport("kernel32")] static extern int SuspendThread(IntPtr h);
  [DllImport("kernel32")] static extern int ResumeThread(IntPtr h);
  [DllImport("kernel32")] static extern bool GetThreadContext(IntPtr h, IntPtr c);
  [DllImport("kernel32")] static extern bool SetThreadContext(IntPtr h, IntPtr c);
  [DllImport("kernel32")] static extern bool WriteProcessMemory(IntPtr p, IntPtr a, byte[] b, int n, out IntPtr w);
  [DllImport("user32")] static extern bool IsWindow(IntPtr h);
  static IntPtr th, ph;
  public static void Arm(int pid, int tid) { th = OpenThread(0x1FFFFF, false, tid); ph = OpenProcess(0x1FFFFF, false, pid); }
  public static string AfterWindow(long hwnd, int delayMs) {
    var sw = System.Diagnostics.Stopwatch.StartNew();
    while (IsWindow(new IntPtr(hwnd))) { if (sw.ElapsedMilliseconds > 120000) return "window stayed"; System.Threading.Thread.SpinWait(2000); }
    if (delayMs > 0) System.Threading.Thread.Sleep(delayMs);
    return Fault();
  }
  public static string Fault() {
    SuspendThread(th);
    IntPtr raw = Marshal.AllocHGlobal(1232 + 16); IntPtr c = new IntPtr((raw.ToInt64() + 15) & ~15L);
    for (int i = 0; i < 1232; i++) Marshal.WriteByte(c, i, 0);
    Marshal.WriteInt32(c, 0x30, 0x10000B); // CONTEXT_FULL, AMD64 layout
    if (!GetThreadContext(th, c)) { ResumeThread(th); return "GetThreadContext failed"; }
    long rip = Marshal.ReadInt64(c, 0xF8), rsp = Marshal.ReadInt64(c, 0x98) - 8; IntPtr w;
    WriteProcessMemory(ph, new IntPtr(rsp), BitConverter.GetBytes(rip), 8, out w);
    Marshal.WriteInt64(c, 0x98, rsp); Marshal.WriteInt64(c, 0xF8, 0);
    bool ok = SetThreadContext(th, c); ResumeThread(th);
    return "fault injected (rip was 0x" + rip.ToString("x") + ", set=" + ok + ")";
  }
}
"@
$main = $null; $first = [DateTime]::MaxValue
foreach ($t in (Get-Process -Id $ProcId).Threads) { try { if ($t.StartTime -lt $first) { $first = $t.StartTime; $main = $t } } catch {} }
[HstFault]::Arm($ProcId, $main.Id)
"armed thread $($main.Id)"
if ($WaitHwnd -ne 0) { [HstFault]::AfterWindow($WaitHwnd, $DelayMs) } else { [HstFault]::Fault() }
