# SPDX-License-Identifier: AGPL-3.0-only
"""File primitives of the "Phiên bản trước" store (version_store): document identity, hashed copies that can be
cancelled, atomic writes and the store-wide lock shared by every office process of the user. Pure Python, no uno."""
import calendar
import errno
import hashlib
import os
import tempfile
import time
import unicodedata
from contextlib import contextmanager

LOCK_NAME = "store.lock"
LOCK_TIMEOUT = 5.0
CHUNK = 1024 * 1024


class StoreBusy(Exception):
    """Another process held the store lock for longer than the wait allowed."""


class Cancelled(Exception):
    """A copy stopped because it was cancelled or ran past its deadline."""


class Changed(Exception):
    """The file changed while it was being copied; the copy is not a consistent version."""


class Staged:
    """A complete copy of a document file in a staging file, with what the file looked like when it was copied."""

    def __init__(self, path, size, mtime_ns, sha256):
        self.path, self.size, self.mtime_ns, self.sha256 = path, size, mtime_ns, sha256

    def matches(self, stat):
        """True while the document file is still the one that was copied (same size and modification time)."""
        return stat.st_size == self.size and stat.st_mtime_ns == self.mtime_ns

    def discard(self):
        remove_quietly(self.path)


def normalized(path):
    """The document identity: absolute, NFC (macOS file dialogs may give NFD Vietnamese) and, on Windows, any case."""
    path = unicodedata.normalize("NFC", os.path.abspath(path))
    return os.path.normcase(path) if os.name == "nt" else path


def key_for(path):
    return hashlib.sha1(normalized(path).encode("utf-8")).hexdigest()


def remove_quietly(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def utc_stamp(seconds):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(max(0, seconds)))


def stamp_seconds(stamp):
    return float(calendar.timegm(time.strptime(stamp, "%Y%m%dT%H%M%SZ")))

def hash_copy(source, target, cancel=None, deadline=None, clock=time.monotonic):
    """Copy `source` to the new file `target`, returning (size, sha256 hex) of what was copied.

    Stops with Cancelled when the event `cancel` is set or `deadline` (clock() value) passes; `target` is then removed.
    The data is flushed to disk before returning, so a version survives a power cut once it is in the index."""
    digest, size = hashlib.sha256(), 0
    try:
        with open(source, "rb") as src, open(target, "xb") as dst:
            while True:
                if (cancel is not None and cancel.is_set()) or (deadline is not None and clock() > deadline):
                    raise Cancelled()
                chunk = src.read(CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                dst.write(chunk)
                size += len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
    except BaseException:
        remove_quietly(target)
        raise
    return size, digest.hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path, data):
    """Write bytes to `path` through a temporary file in the same folder and a rename."""
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=folder)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        remove_quietly(tmp)
        raise


@contextmanager
def store_lock(root, timeout=LOCK_TIMEOUT, clock=time.monotonic, sleep=time.sleep):
    """Exclusive store-wide lock across processes; StoreBusy after `timeout` seconds. The kernel drops it on exit."""
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, LOCK_NAME), "a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)

            def attempt():
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def attempt():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        end = clock() + timeout
        while True:
            try:
                attempt()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) and not isinstance(exc, BlockingIOError):
                    raise
                if clock() >= end:
                    raise StoreBusy() from exc
                sleep(0.05)
        try:
            yield
        finally:
            release()
