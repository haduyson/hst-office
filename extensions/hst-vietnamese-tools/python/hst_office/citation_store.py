# SPDX-License-Identifier: AGPL-3.0-only
"""Small file helpers of the citation library and the user's styles: atomic writes and size-limited reads."""
import os
import tempfile


def atomic_write(path, data):
    """Write bytes through a temporary file in the same folder, fsync, then os.replace (no half-written file)."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=".tmp-", dir=folder)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


def read_limited(path, limit):
    """Bytes of a file of at most ``limit`` bytes; ValueError when larger."""
    size = os.path.getsize(path)
    if size > limit:
        raise ValueError("tệp quá lớn (%d MB, tối đa %d MB)" % (size // 1_000_000 + 1, limit // 1_000_000))
    with open(path, "rb") as stream:
        return stream.read(limit + 1)
