# SPDX-License-Identifier: AGPL-3.0-only
"""Append NSS SQL module records, preserving existing content and module names.

pkcs11.txt uses blank-line-separated key=value records, not INI or shell syntax.
NSS utilmod.c accepts raw values (spaces/backslashes included) or double quotes.
"""
import os
import re
import shutil
import subprocess
import hashlib
import json
import platform
from pathlib import Path
import struct
import sys
import tempfile

from .usb_token_errors import SetupError, vietnamese_error


def _value(raw):
    if not raw.startswith('"'):
        return raw
    match = re.fullmatch(r'"((?:\\.|[^"\\])*)"\s*', raw)
    if not match:
        raise SetupError("pkcs11.txt có giá trị đặt trong dấu nháy không hợp lệ.")
    return re.sub(r'\\(.)', r'\1', match[1])


def parse(text):
    if "\r" in text:
        raise SetupError("Kho chứng thư dùng ký tự xuống dòng chưa được hỗ trợ; chưa thay đổi tệp.")
    records, record = [], {}
    for line in text.splitlines() + [""]:
        if not line:
            if record:
                if "library" not in record or not record.get("name"):
                    raise SetupError("Định dạng kho chứng thư chưa được hỗ trợ; chưa thay đổi tệp.")
                records.append(record)
            record = {}
        elif not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.lower()
            if key not in ("library", "name", "parameters", "nss"):
                raise SetupError("Định dạng kho chứng thư chưa được hỗ trợ; chưa thay đổi tệp.")
            if key in ("library", "name"):
                if key in record:
                    raise SetupError("pkcs11.txt có bản ghi trùng trường; chưa thay đổi tệp.")
                record[key] = _value(value)
        elif not line.startswith("#"):
            raise SetupError("Định dạng kho chứng thư chưa được hỗ trợ; chưa thay đổi tệp.")
    return records


def _safe(value):
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value) or len(value.encode("utf-8")) > 1000:
        raise SetupError("Tên hoặc đường dẫn thư viện không hợp lệ.")


def addition(text, label, library):
    """Return the extra stanza and a collision-free name, or ('', name) if present."""
    _safe(label)
    _safe(library)
    records = parse(text)
    for record in records:
        current = record.get("library", "")
        if current and os.path.realpath(current) == os.path.realpath(library):
            return "", record.get("name", label)
    names = {r["name"] for r in records}
    digest = hashlib.sha256(os.path.realpath(library).encode()).hexdigest()[:16]
    name = "HST %s %s" % (label[:80], digest)
    # NSS's writer uses prefix matches. Refuse even the inverse relationship.
    if any(name.startswith(old) or old.startswith(name) for old in names):
        raise SetupError("Tên mô-đun xung đột với đăng ký hiện có; chưa thay đổi kho chứng thư.")
    # Always quote: NSS accepts this, including leading quotes, = and backslashes.
    quote = lambda value: '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return "\nlibrary=%s\nname=%s\n\n" % (quote(library), quote(name)), name


def read_text(path):
    return path.read_bytes().decode("utf-8", "surrogateescape") if path.exists() else ""



def run_tool(args):
    # No shell, credentials, inherited stdin, or vendor output.
    return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=30, check=False).returncode


def tool(name):
    if os.environ.get("HST_USB_TOKEN_TEST_NO_TOOLS") == "1":
        return None
    return shutil.which(name)


def macos_contents():
    """Find the enclosing app, also from a versioned Python framework prefix."""
    if sys.platform == "darwin":
        for location in (sys.executable, sys.base_prefix):
            path = Path(location).resolve()
            for parent in (path, *path.parents):
                if (parent.name == "Contents" and parent.parent.suffix == ".app"
                        and (parent / "MacOS").is_dir() and (parent / "Frameworks").is_dir()):
                    return parent
    return None


def helper_python():
    candidates = [sys.executable, str(Path(sys.base_prefix) / "bin/python3")]
    contents = macos_contents()
    if contents:
        framework = contents / "Frameworks/LibreOfficePython.framework"
        candidates.extend([str(framework / "bin/python3"), str(framework / "Versions/Current/bin/python3")])
        candidates.extend(str(path) for path in sorted(framework.glob("Versions/*/bin/python3")))
    candidates.append(shutil.which("python3"))
    for value in candidates:
        if value and Path(value).name.startswith("python") and os.access(value, os.X_OK):
            return value
    raise SetupError("Không tìm thấy trình kiểm tra thư viện phù hợp với HST Office; chưa thay đổi kho chứng thư.")


def nss_library():
    # Prefer the very NSS library used by this office, including bundled macOS NSS.
    if sys.platform == "linux":
        for line in Path("/proc/self/maps").read_text().splitlines():
            path = line.split()[-1]
            if path.startswith("/") and Path(path).name == "libnss3.so":
                return path
        return "libnss3.so"
    contents = macos_contents()
    parents = [contents / "Frameworks", contents / "MacOS"] if contents else []
    parents.extend([Path(sys.executable).resolve().parent, Path(sys.base_prefix)])
    for parent in parents:
        for name in (("libnss3.dylib",) if sys.platform == "darwin" else ("libnss3.so",)):
            if (parent / name).is_file():
                return str(parent / name)
    raise SetupError("Không tìm thấy thư viện NSS của HST Office; chưa thay đổi kho chứng thư.")


def register(db, modules):
    from .usb_token_db import user_database
    user_database(db)
    results = []
    for module in modules:
        row = dict(module, status="error")
        try:
            with tempfile.TemporaryDirectory(prefix="hst-token-check-") as temporary:
                request = Path(temporary) / "request.json"
                response = Path(temporary) / "response.json"
                request.write_text(json.dumps(dict(db=str(db), module=module, modutil=tool("modutil"),
                    certutil=tool("certutil"), machine=platform.machine(), bits=struct.calcsize("P"),
                    nss=nss_library(), response=str(response))))
                code = run_tool([helper_python(), str(Path(__file__).with_name("usb_token_worker.py")), str(request)])
                if code or not response.exists():
                    raise SetupError("Không thể kiểm tra thư viện USB Token. Kiểm tra kiến trúc, thư viện phụ thuộc và quyền chạy.")
                row.update(json.loads(response.read_text()))
        except Exception as exc:  # noqa: BLE001 - vendor crashes and OS messages must stay out of the UI
            row.update(status="error", error=vietnamese_error(exc))
        results.append(row)
    return results
