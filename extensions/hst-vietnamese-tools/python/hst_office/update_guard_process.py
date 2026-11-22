# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Local process queries of the update start-up guard (update_guard), never the network:

- pid_alive: does the update helper still run (Windows: OpenProcess/GetExitCodeProcess through ctypes, never
  os.kill, which would end the process; elsewhere signal 0);
- own_executable: macOS proc_pidpath through ctypes, the path of this office's executable after a bundle swap.
"""
import os
import platform


def pid_alive(pid, system=None):
    """True while process `pid` exists. Windows: never os.kill, which would end the process."""
    if (system or platform.system()) == "Windows":
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def own_executable():
    """macOS: the path the kernel now gives this process's executable (it follows a rename), or None."""
    try:
        import ctypes
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        buffer = ctypes.create_string_buffer(4096)
        size = libc.proc_pidpath(os.getpid(), buffer, ctypes.sizeof(buffer))
        return buffer.raw[:size].decode("utf-8", "replace") if size > 0 else None
    except (OSError, AttributeError):
        return None
