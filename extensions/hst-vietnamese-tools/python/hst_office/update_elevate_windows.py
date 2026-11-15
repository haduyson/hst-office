# SPDX-License-Identifier: AGPL-3.0-only
"""Windows only: start the updater elevated, with the office window as the owner of the administrator question.

Windows shows an elevation request as a real prompt only when it comes from the foreground window. The updater used to
ask from its own hidden process after the office had closed: such a background request is only a blinking taskbar
button. ctypes only (no process or network modules); update_launch builds the command line."""
import os

ERROR_CANCELLED = 1223  # the user answered No to the administrator question (or the policy denies it)
_SEE_MASK = 0x40 | 0x100 | 0x400  # NOCLOSEPROCESS | NOASYNC | FLAG_NO_UI
_SW_HIDE = 0


class ElevationDeclined(Exception):
    """Administrator rights were refused; nothing was started and the office stays open."""


def _shell_execute_info():
    import ctypes
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    return ctypes, ShellExecuteInfo


def _windows_api(ctypes):
    """user32, shell32 and kernel32 with explicit handle types; shell32 keeps the error code of each call."""
    from ctypes import wintypes
    user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetProcessId.argtypes = (wintypes.HANDLE,)
    kernel32.GetProcessId.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return user32, shell32, kernel32


def owner_window(user32, pid=None):
    """The foreground window when it belongs to this process (the office the user just clicked in), else 0."""
    import ctypes
    from ctypes import wintypes
    hwnd = user32.GetForegroundWindow()
    owner = wintypes.DWORD(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    return hwnd if hwnd and owner.value == (os.getpid() if pid is None else pid) else 0


def run_elevated(program, parameters, api=None):
    """Start `program` with the command line `parameters` elevated. The office's foreground window owns the request,
    so the administrator question appears at once in front of the user. The process ID, or ElevationDeclined (No)."""
    ctypes, ShellExecuteInfo = _shell_execute_info()
    if api is None:
        user32, shell32, kernel32 = _windows_api(ctypes)
        last_error = ctypes.get_last_error  # saved by ctypes right after ShellExecuteExW (use_last_error)
    else:
        user32, shell32, kernel32 = api
        last_error = kernel32.GetLastError
    info = ShellExecuteInfo(cbSize=ctypes.sizeof(ShellExecuteInfo), fMask=_SEE_MASK, hwnd=owner_window(user32),
                            lpVerb="runas", lpFile=program, lpParameters=parameters, nShow=_SW_HIDE)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = last_error()
        if error == ERROR_CANCELLED:
            raise ElevationDeclined()
        raise OSError(error, "ShellExecuteExW failed")
    pid = kernel32.GetProcessId(info.hProcess) if info.hProcess else 0
    if info.hProcess:
        kernel32.CloseHandle(info.hProcess)
    return pid
