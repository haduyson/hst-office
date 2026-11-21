# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: is an office's UI thread answering? For the evidence of a held GUI check: a prompt (answering, a
dialog on screen) is told apart from a hang (the window does not answer WM_NULL), and a hang gets a minidump.

  ui_state()            -> [(hwnd, title, "answers" | "hung")] of the visible office windows
  write_minidump(pid, path) -> True when the full-memory dump of the process is written
  thread_stacks(pid, symbols) -> `~*k` of every thread through cdb.exe (noninvasive), or None without cdb
"""
import ctypes
import glob
import os
import subprocess
from ctypes import wintypes

WM_NULL, SMTO_ABORTIFHUNG = 0x0000, 0x0002
MINIDUMP_WITH_FULL_MEMORY = 0x2
PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
GENERIC_WRITE, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL = 0x40000000, 2, 0x80


def ui_state(timeout_ms=5000):
    """Each visible office window (class SAL*) with whether its thread answers WM_NULL within timeout_ms."""
    from windows_gui_win32 import office_windows
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send = user32.SendMessageTimeoutW
    send.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                     ctypes.POINTER(ctypes.c_size_t))
    send.restype = ctypes.c_size_t
    rows = []
    for hwnd, _cls, title, _rect in office_windows():
        result = ctypes.c_size_t()
        answered = send(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result))
        rows.append((hwnd, title, "answers" if answered else "hung"))
    return rows


def write_minidump(pid, path):
    """A full-memory minidump of process pid at path (for a stack of a hung office)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CreateFileW.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not process:
        return False
    handle = kernel32.CreateFileW(path, GENERIC_WRITE, 0, None, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
    try:
        if handle in (None, wintypes.HANDLE(-1).value):
            return False
        dbghelp.MiniDumpWriteDump.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.HANDLE, wintypes.DWORD,
                                              ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        return bool(dbghelp.MiniDumpWriteDump(process, pid, handle, MINIDUMP_WITH_FULL_MEMORY, None, None, None))
    finally:
        if handle not in (None, wintypes.HANDLE(-1).value):
            kernel32.CloseHandle(handle)
        kernel32.CloseHandle(process)


CDB_GLOBS = (r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe",
             r"C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe",
             r"C:\Program Files\WindowsApps\Microsoft.WinDbg_*\amd64\cdb.exe")


def thread_stacks(pid, symbols=""):
    """Every thread's stack of the process, read without stopping it (cdb -pv); None when no cdb is installed."""
    found = [path for pattern in CDB_GLOBS for path in glob.glob(pattern)]
    if not found:
        return None
    command = [found[0], "-pv", "-p", str(pid), "-c", "~*k 40;qd"]
    if symbols:
        command[1:1] = ["-y", symbols]
    out = subprocess.run(command, capture_output=True, timeout=300, check=False)
    return out.stdout.decode("utf-8", "replace")
