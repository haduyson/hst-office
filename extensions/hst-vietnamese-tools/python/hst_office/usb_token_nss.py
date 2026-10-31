# SPDX-License-Identifier: AGPL-3.0-only
"""Append NSS SQL module records, preserving existing content and module names.

pkcs11.txt uses blank-line-separated key=value records, not INI or shell syntax.
NSS utilmod.c accepts raw values (spaces/backslashes included) or double quotes.
"""
import fcntl
import os
import re
import shutil
import stat
import subprocess
import tempfile


def _value(raw):
    if not raw.startswith('"'):
        return raw
    match = re.fullmatch(r'"((?:\\.|[^"\\])*)"\s*', raw)
    if not match:
        raise ValueError("pkcs11.txt có giá trị đặt trong dấu nháy không hợp lệ.")
    return re.sub(r'\\(.)', r'\1', match[1])


def parse(text):
    records, record = [], {}
    for line in text.splitlines() + [""]:
        if not line:
            if record:
                records.append(record)
            record = {}
        elif not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.lower()
            if key in ("library", "name"):
                if key in record:
                    raise ValueError("pkcs11.txt có bản ghi trùng trường; chưa thay đổi tệp.")
                record[key] = _value(value)
    return records


def _safe(value):
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value) or len(value.encode("utf-8")) > 1000:
        raise ValueError("Tên hoặc đường dẫn thư viện không hợp lệ.")


def addition(text, label, library):
    """Return the extra stanza and a collision-free name, or ('', name) if present."""
    _safe(label)
    _safe(library)
    records = parse(text)
    for record in records:
        current = record.get("library", "")
        if current and os.path.realpath(current) == os.path.realpath(library):
            return "", record.get("name", label)
    names = {r.get("name") for r in records}
    name, index = label, 2
    while name in names:
        name = "%s (%d)" % (label, index)
        index += 1
    # Always quote: NSS accepts this, including leading quotes, = and backslashes.
    quote = lambda value: '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return "\nlibrary=%s\nname=%s\n\n" % (quote(library), quote(name)), name


def read_text(path):
    return path.read_bytes().decode("utf-8", "surrogateescape") if path.exists() else ""


def append_atomic(path, original, extra):
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".hst-pkcs11-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            text = original + ("\n" if original and not original.endswith("\n") else "") + extra
            handle.write(text.encode("utf-8", "surrogateescape"))
            handle.flush()
            os.fsync(handle.fileno())
        # NSS/Firefox do not take our lock. Refuse if another writer changed the DB.
        if read_text(path) != original:
            raise OSError("Kho chứng thư vừa thay đổi. Đóng ứng dụng dùng kho và thử lại.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_tool(args):
    # No shell, no login, no PIN arguments or stdin; never echo vendor/tool output.
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=30, check=False)
    if result.returncode:
        raise OSError("Công cụ NSS không đăng ký được thư viện (mã %d)." % result.returncode)


def tool(name):
    # Runtime harness simulates macOS without NSS CLI tools; no production default changes.
    if os.environ.get("HST_USB_TOKEN_TEST_NO_TOOLS") == "1":
        return None
    return shutil.which(name)


def register(db, modules):
    from .usb_token_db import user_database
    user_database(db)
    results = []
    # Protect repeated menu invocations/processes. The lock never contains credentials.
    fd = os.open(db / ".hst-usb-token.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        modutil = tool("modutil")
        certutil = tool("certutil")
        if not (db / "cert9.db").exists() and certutil:
            run_tool([certutil, "-N", "-d", "sql:" + str(db), "--empty-password"])
        path = db / "pkcs11.txt"
        for module in modules:
            row = dict(module, status="existing")
            try:
                original = read_text(path)
                extra, label = addition(original, module["label"], module["path"])
                if extra:
                    if modutil:
                        run_tool([modutil, "-add", label, "-libfile", module["path"], "-dbdir", "sql:" + str(db), "-force"])
                    else:
                        append_atomic(path, original, extra)
                    row["status"] = "added"
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                row.update(status="error", error=str(exc) if not isinstance(exc, subprocess.TimeoutExpired)
                           else "Công cụ NSS không phản hồi. Đóng ứng dụng dùng token và thử lại.")
            results.append(row)
    return results
