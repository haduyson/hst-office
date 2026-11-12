# SPDX-License-Identifier: AGPL-3.0-only
"""File steps of "Khôi phục" and "Mở xem" in the "Phiên bản trước" dialog (pure Python; the office steps, closing
and reopening the document, are in version_dialog).

Restore order, so that a failure at any step leaves the user's file as it was:
1. keep_current: the file on disk now becomes a stored version (whatever its size: the user asked for the restore);
2. stage_restore: the chosen version is copied next to the file and its SHA-256 checked;
3. (the dialog closes the document, which releases the office's hold on the file)
4. replace: an atomic rename over the file, retried for a few seconds (a virus scanner or the office's handle may
   linger on Windows); on failure the staged copy is removed and the file is untouched.
"""
import os
import shutil
import tempfile
import time
import uuid

from .version_files import hash_copy, remove_quietly
from .version_store import StoreBusy
from . import version_texts as T

REPLACE_SECONDS = 3.0
VIEW_FOLDER = "hst-xem-phien-ban"
VIEW_KEEP_SECONDS = 86400


class RestoreError(Exception):
    """A restore or view step failed; `code` selects the Vietnamese message (version_texts.ERRORS)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def keep_current(store, path):
    """Store the file as it is on disk now. "missing" when it no longer exists (nothing to keep)."""
    try:
        return store.capture(path, max_bytes=None)
    except FileNotFoundError:
        return "missing"
    except StoreBusy as exc:
        raise RestoreError("busy") from exc
    except Exception as exc:  # noqa: BLE001 - never replace a file whose current content is not kept
        raise RestoreError("keep") from exc


def stage_restore(version, path):
    """Copy `version` into the document's folder (same file system: the final rename is atomic); returns its path."""
    folder, ext = os.path.dirname(path), os.path.splitext(path)[1]
    target = os.path.join(folder, ".~hst-restore-%s%s" % (uuid.uuid4().hex[:12], ext))
    try:
        _, sha256 = hash_copy(version.path, target)
    except FileNotFoundError as exc:
        if not os.path.exists(version.path):
            raise RestoreError("missing") from exc
        raise RestoreError("stage") from exc
    except OSError as exc:
        raise RestoreError("stage") from exc
    if sha256 != version.sha256:
        remove_quietly(target)
        raise RestoreError("corrupt")
    try:
        shutil.copymode(path, target)  # keep the file's permissions
    except OSError:
        pass
    return target


def replace(staged, path, wait=REPLACE_SECONDS, clock=time.monotonic, sleep=time.sleep):
    """Rename the staged copy over the file; RestoreError("replace") (staged copy removed) when it keeps failing."""
    deadline = clock() + wait
    while True:
        try:
            os.replace(staged, path)
            return
        except OSError as exc:
            if clock() >= deadline:
                remove_quietly(staged)
                raise RestoreError("replace") from exc
            sleep(0.2)


def view_copy(version, path, localtime=time.localtime, base=None, clock=time.time):
    """A copy of `version` to open read-only, in a temporary folder, named after the file and the version's time.
    Copies older than a day are removed first (an open one on Windows simply stays until the next time)."""
    folder = os.path.join(base or tempfile.gettempdir(), VIEW_FOLDER)
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        try:
            if clock() - os.stat(full).st_mtime > VIEW_KEEP_SECONDS:
                os.remove(full)
        except OSError:
            pass
    stem, ext = os.path.splitext(os.path.basename(path))
    stamp = time.strftime("%d-%m-%Y %H.%M.%S", localtime(version.saved))
    target = os.path.join(folder, T.VIEW_NAME % (stem, stamp, ext))
    n = 1
    while os.path.exists(target):
        n += 1
        target = os.path.join(folder, T.VIEW_NAME % (stem, "%s %d" % (stamp, n), ext))
    try:
        hash_copy(version.path, target)
    except FileNotFoundError as exc:
        raise RestoreError("missing") from exc
    except OSError as exc:
        raise RestoreError("open") from exc
    return target
