# SPDX-License-Identifier: AGPL-3.0-only
"""W1 MSI with full UI defaults; never force the default-app property."""
from pathlib import Path
import subprocess
import time
import winreg
from native import screenshot


def install(msi, out):
    from pywinauto import Desktop
    out = Path(out)
    command = ["msiexec.exe", "/i", str(msi), "/norestart", "/l*v", str(out / "msi-install.log")]
    process = subprocess.Popen(command)
    seen, checked, shots = [], None, []
    try:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline and process.poll() is None:
            windows = [w for w in Desktop(backend="uia").windows() if "HST Office" in w.window_text()]
            for window in windows:
                title = window.window_text()
                if title not in seen:
                    seen.append(title)
                window.set_focus()
                for control in window.descendants(control_type="CheckBox"):
                    label = control.window_text()
                    if "HST Office" in label and ("tài liệu" in label or "documents" in label):
                        checked = control.get_toggle_state() == 1
                        shot = out / "W1-default-apps.png"
                        screenshot(shot)
                        shots.append(shot.name)
                        if not checked:
                            raise AssertionError("Ô mở tài liệu không được tích sẵn")
                buttons = [b for b in window.descendants(control_type="Button") if b.is_enabled()]
                for labels in (("Tiếp", "Next"), ("Cài đặt", "Install"), ("Hoàn tất", "Finish")):
                    button = next((b for b in buttons if any(t in b.window_text().replace("&", "") for t in labels)), None)
                    if button:
                        button.click_input()
                        time.sleep(1)
                        break
            time.sleep(0.5)
        code = process.wait(10)
        if code not in (0, 3010) or checked is not True:
            raise AssertionError(f"Cài đặt chưa đạt: exit={code}, checkbox={checked}")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\HASON TECH\HST Office\DefaultApps") as key:
            chosen = winreg.QueryValueEx(key, "ChosenAtInstall")[0]
        if chosen != 1:
            raise AssertionError("Không ghi nhận lựa chọn ứng dụng mặc định lúc cài")
        roots = [p.parent.parent for p in Path("C:/Program Files").glob("HST*/program/soffice.exe")]
        if len(roots) != 1:
            raise RuntimeError("Không xác định được đúng bản HST đã cài")
        return roots[0], dict(message="Cài MSI bằng giao diện mặc định", exit_code=code,
                              checkbox=checked, chosen_at_install=chosen, windows=seen, screenshots=shots)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(10)


def product_version(path):
    """ProductVersion of a Windows binary: HST_RELEASE (include/default.rc), the text the About dialog shows."""
    import ctypes
    from ctypes import wintypes
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise OSError("Không có thông tin phiên bản: " + str(path))
    data = ctypes.create_string_buffer(size)
    version.GetFileVersionInfoW(str(path), 0, size, data)
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    version.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(pointer), ctypes.byref(length))
    lang, codepage = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD * 2)).contents
    key = "\\StringFileInfo\\%04x%04x\\ProductVersion" % (lang, codepage)
    if not version.VerQueryValueW(data, key, ctypes.byref(pointer), ctypes.byref(length)):
        raise OSError("Không đọc được ProductVersion")
    return ctypes.wstring_at(pointer, length.value).rstrip("\0")
