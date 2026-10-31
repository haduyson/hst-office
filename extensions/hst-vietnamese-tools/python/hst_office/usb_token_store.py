# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only migration to an HST-owned module DB; never copy keys or certificates."""
import os
from pathlib import Path
import shutil
import tempfile

from . import usb_token_nss as nss
from .usb_token_binding import relocate
from .usb_token_errors import SetupError, vietnamese_error
from .usb_token_transaction import create_new

MARKER = ".hst-office-nssdb"
IDENTITY = b"HST Office NSS module store v1\n"


def owned(path):
    path = Path(path)
    marker = path / MARKER
    try:
        return (path.is_absolute() and not path.is_symlink() and path.is_dir() and path.stat().st_uid == os.geteuid()
                and path.stat().st_mode & 0o777 == 0o700
                and not marker.is_symlink() and marker.is_file() and marker.stat().st_uid == os.geteuid()
                and marker.stat().st_mode & 0o777 == 0o600 and marker.read_bytes() == IDENTITY)
    except OSError:
        return False


def directory(home, platform, configured=""):
    # A current CertDir is potentially in use, even before NSS initializes.
    # Reuse it only while its module file is absent; never rewrite that file.
    if configured and owned(configured):
        current = Path(configured)
        if not os.path.lexists(current / "pkcs11.txt"):
            return current
    relative = "Library/Application Support/HST Office" if platform == "macos" else ".local/share/hst-office"
    parent = Path(home)
    for part in ("", *Path(relative).parts):
        parent = parent / part
        parent.mkdir(mode=0o700, exist_ok=True)
        if parent.is_symlink() or parent.stat().st_uid != os.geteuid():
            raise SetupError("Thư mục kho HST phải thuộc tài khoản đang sử dụng và không là liên kết.")
    index = 1
    while True:
        target = parent / ("nssdb" if index == 1 else "nssdb-%d" % index)
        try:
            target.mkdir(mode=0o700)
        except FileExistsError:
            # Even an empty directory without our marker is not ours to claim.
            index += 1
            continue
        with (target / MARKER).open("xb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(IDENTITY)
            handle.flush()
            os.fsync(handle.fileno())
        return target


def publish(source, target, original, text):
    # Recovery data belongs to the NEW store. Never write even a backup into
    # Firefox/Thunderbird, and never open its SQL files or initialize its NSS.
    backup = Path(tempfile.mkdtemp(prefix=".hst-token-backup-", dir=target))
    success = False
    try:
        with (backup / "pkcs11.txt").open("xb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(original.encode("utf-8", "surrogateescape"))
            handle.flush()
            os.fsync(handle.fileno())
        if nss.read_text(source / "pkcs11.txt") != original:
            raise SetupError("Kho chứng thư vừa thay đổi; chưa chọn kho mới. Hãy thử lại.")
        create_new(target / "pkcs11.txt", text.encode("utf-8", "surrogateescape"), backup)
        success = True
    finally:
        if not success:
            shutil.rmtree(backup)


def register_private(db, modules, home, platform, configured):
    if os.environ.get("MOZILLA_CERTIFICATE_FOLDER"):
        raise SetupError("MOZILLA_CERTIFICATE_FOLDER đang cố định kho chứng thư; chưa thay đổi tệp hay chọn kho mới. "
                         "Trên Linux, hãy đóng ứng dụng đang dùng kho rồi đăng ký vào kho đã cố định khi có thể khóa an toàn. "
                         "Nếu không, hãy bỏ thiết lập biến MOZILLA_CERTIFICATE_FOLDER trong môi trường khởi chạy "
                         "rồi khởi động lại HST Office và thử lại.")
    original = nss.read_text(db / "pkcs11.txt")
    rows = nss.register(db, modules, probe=True)
    if not any(row["status"] == "added" for row in rows):
        return db, rows, False
    try:
        text = original
        duplicates = []
        for row in rows:
            if row["status"] == "added":
                extra, _ = nss.addition(text, row["label"], row["path"])
                text += ("\n" if text and not text.endswith("\n") else "") + extra
                if not extra:
                    duplicates.append(row)
        if nss.read_text(db / "pkcs11.txt") != original:
            raise SetupError("Kho chứng thư vừa thay đổi; chưa chọn kho mới. Hãy thử lại.")
        relocate(text, db)  # Validate every binding/policy before allocating anything.
        target = directory(home, platform, configured)
        publish(db, target, original, relocate(text, target))
    except Exception as exc:  # noqa: BLE001 - no native or OS text in the dialog
        for row in rows:
            if row["status"] == "added":
                row.update(status="error", error=vietnamese_error(exc))
        return db, rows, False
    for row in duplicates:
        row["status"] = "existing"
    for row in rows:
        if row["status"] != "error":
            row["private_store"] = True
    return target, rows, True


def register(db, modules, home, platform, configured=""):
    # Test override exercises the Darwin policy with native Linux NSS/drivers.
    if os.environ.get("HST_USB_TOKEN_TEST_PLATFORM") == "darwin":
        platform = "macos"
    if platform != "linux" or ((db / "pkcs11.txt").exists()
                               and not nss.worker(db, lease=True).get("available", False)):
        return register_private(db, modules, home, platform, configured)
    # Normal Linux publication, backups, SQL locks and lease rollback unchanged.
    return db, nss.register(db, modules), False
