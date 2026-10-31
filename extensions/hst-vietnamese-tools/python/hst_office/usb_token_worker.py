# SPDX-License-Identifier: AGPL-3.0-only
"""Disposable, architecture-checked NSS probe. No login, PIN, or key operations."""
import ctypes
import json
import os
from pathlib import Path
import platform
import struct
import sys
import tempfile

# Executed in a fresh interpreter, never fork a running office's NSS state.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hst_office.usb_token_errors import SetupError, vietnamese_error
from hst_office.usb_token_nss import addition, parse, read_text, run_tool
from hst_office.usb_token_transaction import commit_addition, module_lease


class ModuleHeader(ctypes.Structure):
    # Public SECMODModule prefix from NSS secmodt.h; PRBool is a C int.
    _fields_ = [("arena", ctypes.c_void_p), ("internal", ctypes.c_int), ("loaded", ctypes.c_int)]


def validate(request, name):
    if platform.machine() != request["machine"] or struct.calcsize("P") != request["bits"]:
        raise SetupError("Trình kiểm tra khác kiến trúc HST Office; chưa thay đổi kho chứng thư.")
    nss = ctypes.CDLL(request["nss"])
    nss.NSS_NoDB_Init.argtypes = [ctypes.c_char_p]
    nss.SECMOD_LoadUserModule.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int]
    nss.SECMOD_LoadUserModule.restype = ctypes.POINTER(ModuleHeader)
    nss.SECMOD_DestroyModule.argtypes = [ctypes.POINTER(ModuleHeader)]
    if nss.NSS_NoDB_Init(None):
        raise SetupError("Không khởi tạo được trình kiểm tra NSS; chưa thay đổi kho chứng thư.")
    quote = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    spec = "name=%s library=%s" % (quote(name), quote(request["module"]["path"]))
    module = nss.SECMOD_LoadUserModule(spec.encode(), None, 0)
    loaded = bool(module and module.contents.loaded)
    if module:
        nss.SECMOD_DestroyModule(module)
    nss.NSS_Shutdown()
    if not loaded:
        raise SetupError("NSS không nạp được thư viện USB Token. Kiểm tra kiến trúc, thư viện phụ thuộc và quyền chạy của hệ điều hành.")


def prepare(request):
    db = Path(request["db"])
    original = read_text(db / "pkcs11.txt")
    extra, name = addition(original, request["module"]["label"], request["module"]["path"])
    validate(request, name)  # Also revalidate an existing text registration.
    if not extra:
        if read_text(db / "pkcs11.txt") != original:
            raise SetupError("Kho chứng thư vừa thay đổi. Hãy thử lại.")
        return {"status": "existing"}
    if request["modutil"]:
        # Never give a live module DB to the NSS deletion/rewrite implementation.
        with tempfile.TemporaryDirectory(prefix="hst-nss-probe-") as temporary:
            stage = Path(temporary)
            if not request["certutil"]:
                raise SetupError("Thiếu công cụ tạo kho NSS kiểm tra; chưa thay đổi kho chứng thư.")
            if run_tool([request["certutil"], "-N", "-d", "sql:" + temporary, "--empty-password"]):
                raise SetupError("Không tạo được kho NSS kiểm tra; chưa thay đổi kho chứng thư.")
            if run_tool([request["modutil"], "-add", name, "-libfile", request["module"]["path"],
                         "-dbdir", "sql:" + temporary, "-force"]):
                raise SetupError("Công cụ NSS không đăng ký được thư viện; chưa thay đổi kho chứng thư.")
            if not any(r.get("name") == name and r.get("library") == request["module"]["path"]
                       for r in parse(read_text(stage / "pkcs11.txt"))):
                raise SetupError("Không xác minh được đăng ký NSS; chưa thay đổi kho chứng thư.")
    if not request.get("probe"):
        commit_addition(db, original, extra)
    return {"status": "added"}


def lease_available(db):
    # Check without opening the source for writing or creating recovery files.
    fd = os.open(Path(db) / "pkcs11.txt", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            with module_lease(fd):
                return {"available": True}
        except (SetupError, OSError):
            return {"available": False}
    finally:
        os.close(fd)


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    try:
        result = lease_available(request["db"]) if request.get("lease") else prepare(request)
    except Exception as exc:  # noqa: BLE001 - never relay vendor/OS exception text
        result = {"status": "error", "error": vietnamese_error(exc)}
    Path(request["response"]).write_text(json.dumps(result))


if __name__ == "__main__":
    main()
