# SPDX-License-Identifier: AGPL-3.0-only
"""Add only: atomic no-clobber creation, or append under a kernel write lease.

NSS does not honor advisory module-file locks. Linux leases instead block its
open-before-rewrite operation, even in an already initialized NSS process.
The caller uses a separate HST store when leases are unavailable.
Lease/append operations run only in the disposable worker, away from UNO signals.
"""
from contextlib import contextmanager, ExitStack
import fcntl
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import sys
import tempfile

from .usb_token_errors import RecoveryError, SetupError

FILES = ("pkcs11.txt", "secmod.db", "cert9.db", "key4.db")
BUSY = "Không thể khóa độc quyền kho chứng thư. Đóng ứng dụng dùng kho rồi thử lại; chưa thay đổi đăng ký."


@contextmanager
def sql_locks(db):
    # These are the actual SQLite locks NSS observes, not an HST-only lock.
    with ExitStack() as stack:
        for name in ("cert9.db", "key4.db"):
            path = db / name
            if path.exists():
                connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=0)
                stack.callback(connection.close)
                try:
                    if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                        raise SetupError(BUSY)
                    connection.execute("BEGIN EXCLUSIVE")
                except sqlite3.Error:
                    raise SetupError(BUSY) from None
        yield


@contextmanager
def module_lease(fd):
    if sys.platform != "linux" or not hasattr(fcntl, "F_SETLEASE"):
        raise SetupError("Hệ điều hành chưa hỗ trợ khóa an toàn tệp mô-đun hiện có; chưa thay đổi kho chứng thư.")
    # A lease break is deferred by the kernel. Only the tiny append/rollback is
    # inside the lease; no subprocess, SQL wait or backup copy runs here.
    if int(Path("/proc/sys/fs/lease-break-time").read_text()) < 10:
        raise SetupError(BUSY)
    previous = signal.signal(signal.SIGIO, lambda *_: None)
    acquired = False
    try:
        try:
            fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_WRLCK)
            acquired = True
        except OSError:
            raise SetupError(BUSY) from None
        yield
    finally:
        if acquired:
            fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)
        signal.signal(signal.SIGIO, previous)


def backup_files(db, backup, handles):
    for name in FILES:
        source = db / name
        if source.is_symlink():
            raise SetupError("Tệp kho chứng thư là liên kết; chưa thay đổi kho chứng thư.")
        if source.exists():
            # Closing any descriptor of a SQLite inode drops this process's
            # POSIX locks. Keep source handles open until sql_locks has exited.
            reader = handles.enter_context(source.open("rb"))
            with (backup / name).open("wb") as writer:
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
            if name not in ("cert9.db", "key4.db"):
                reader.close()
            (backup / name).chmod(0o600)
    # No key parsing or extraction: these are opaque recovery copies only.


def append_leased(path, original, payload):
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
    try:
        with module_lease(fd):
            if os.fstat(fd).st_ino != path.stat().st_ino or os.pread(fd, len(original) + 1, 0) != original:
                raise SetupError("Kho chứng thư vừa thay đổi; chưa ghi thêm. Hãy thử lại.")
            if fcntl.fcntl(fd, fcntl.F_GETLEASE) != fcntl.F_WRLCK:
                raise SetupError(BUSY)
            try:
                if os.write(fd, payload) != len(payload):
                    raise OSError("short append")
                os.fsync(fd)
                if os.fstat(fd).st_ino != path.stat().st_ino:
                    raise SetupError("Kho chứng thư vừa được thay thế bởi ứng dụng khác. Hãy thử lại.")
            except BaseException:
                # The original bytes were never overwritten. Undo only our tail,
                # while competing NSS opens are still blocked by the lease.
                try:
                    os.ftruncate(fd, len(original))
                    os.fsync(fd)
                except OSError:
                    raise RecoveryError("Không khôi phục được tệp mô-đun. Giữ bản sao lưu để phục hồi kho chứng thư.") from None
                raise
    finally:
        os.close(fd)


def create_new(path, payload, backup):
    # link() is an atomic create-if-absent, never a compare/replace.
    staged = backup / "addition"
    staged.write_bytes(payload)
    staged.chmod(0o600)
    with staged.open("rb") as handle:
        os.fsync(handle.fileno())
    os.link(staged, path)
    # Nothing fallible may turn successful publication into a reported failure.
    try:
        staged.unlink()
    except OSError:
        pass


def commit_addition(db, original, extra):
    path = db / "pkcs11.txt"
    raw = original.encode("utf-8", "surrogateescape")
    payload = (("\n" if original and not original.endswith("\n") else "") + extra).encode("utf-8")
    with ExitStack() as handles, sql_locks(db):
        backup = Path(tempfile.mkdtemp(prefix=".hst-token-backup-", dir=db))
        success = False
        try:
            backup_files(db, backup, handles)
            saved = backup / "pkcs11.txt"
            if (saved.read_bytes() if saved.exists() else b"") != raw:
                raise SetupError("Kho chứng thư vừa thay đổi; chưa ghi thêm. Hãy thử lại.")
            if saved.exists():
                append_leased(path, raw, payload)
            else:
                create_new(path, payload, backup)
            success = True
        except RecoveryError as exc:
            success = True  # Preserve recovery data on a storage failure.
            raise SetupError(str(exc) + " Bản sao lưu: " + str(backup)) from None
        finally:
            if not success:
                shutil.rmtree(backup)
