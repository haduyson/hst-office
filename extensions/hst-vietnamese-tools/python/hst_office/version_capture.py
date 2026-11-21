# SPDX-License-Identifier: AGPL-3.0-only
"""When to copy a document file into the "Phiên bản trước" store, without stalling the office's UI thread.

The copy must hold the bytes that are on disk just before a save replaces them. The office announces a save with
OnSave synchronously on the UI thread and writes the file right after the listeners return
(SfxBaseModel::storeSelf), so a copy taken later is too late, and a copy still reading while the office replaces the
file can make that replace fail on Windows (an open handle without FILE_SHARE_DELETE) or yield a mixed copy.

So the copy is taken earlier, in a background thread: when the document becomes modified (OnModifyChanged), the file
on disk is the one the next save will overwrite. prepare() copies it to a staging file of the store. At OnSave,
before_save() only checks that the file is unchanged (size and modification time) and renames the staged copy into
the store (version_store.add: a rename and a small index write). Only when there is no usable staged copy (saved
without a change, the file changed on disk, a copy still running) does OnSave wait or copy itself, bounded by
WAIT_SECONDS; past that the version is skipped, so a slow network or USB drive costs at most WAIT_SECONDS, never a
failed save. Nothing here raises into the save: every outcome is a status string for the local log.

A save of an unmodified document rewrites the file with new bytes (OOXML and ODF store the save time inside), so the
SHA-256 dedupe of the store cannot see it as a repeat. remember() records, after each save of this office (OnSaveDone,
OnSaveAsDone), the identity of the file it wrote (size, modification time, file id: one stat, no read). An OnSave of an
unmodified document whose file still has that identity keeps nothing ("unchanged"): the file is what this office last
wrote and its content is the open document. If another program changed the file since, the identity differs and the
file is kept as before. With no record (the first save after opening) the file is kept: it may hold content that was
never stored, and a duplicate of it is at most one copy per opening.

AutoSave ("Tự động lưu", owner decision 21/11/2026) saves the document into its file every few minutes; a copy for each
of those saves would fill the KEEP_PER_FILE copies of the document within half an hour. An AutoSave keeps a copy only
when it is the first AutoSave of this opening of the document (the file as it was before this session's changes) or
when the newest copy of the document is older than AUTOSAVE_SPACING_SECONDS (autosave_keeps). A save by the user
always keeps one, as before.
"""
import os
import threading
import time

from .version_store import MAX_FILE_BYTES, Cancelled, Changed, StoreBusy, key_for

WAIT_SECONDS = 3.0  # longest OnSave may wait for a copy (finishing a staged one, or a copy of its own)
AUTOSAVE_SPACING_SECONDS = 30 * 60  # at most one copy per this time from AutoSave, plus the first of each opening
_LOCK = threading.Lock()
_PENDING = {}  # key_for(path) -> Pending
_PRUNING = {}  # "thread": the background store-wide prune, if one runs
_WRITTEN = {}  # key_for(path) -> identity of the file this office last wrote there (remember)
_AUTOSAVED = set()  # key_for(path) of documents AutoSave already saved during this opening


class Pending:
    """One background copy of a document file into a staging file."""

    def __init__(self, store, path, max_bytes):
        self.store, self.path, self.max_bytes = store, path, max_bytes
        self.cancel = threading.Event()
        self.staged, self.error = None, None
        self.thread = threading.Thread(target=self._run, name="hst-version-stage", daemon=True)

    def _run(self):
        try:
            self.staged = self.store.stage(self.path, self.cancel, max_bytes=self.max_bytes)
        except Exception as exc:  # noqa: BLE001 - kept for before_save; a failed copy only loses this version
            self.error = exc
        if self.cancel.is_set() and self.staged is not None:
            self.staged.discard()

    def discard(self):
        """Stop the copy and remove its staging file (the thread removes it if it finishes afterwards)."""
        self.cancel.set()
        if not self.thread.is_alive() and self.staged is not None:
            self.staged.discard()


def _stat(path):
    try:
        return os.stat(path)
    except OSError:
        return None


def _identity(stat):
    return None if stat is None else (stat.st_size, stat.st_mtime_ns, stat.st_ino)


def remember(path):
    """A save of this office finished (OnSaveDone, OnSaveAsDone): record the identity of the file it wrote.
    Returns "recorded" or "missing"."""
    identity = _identity(_stat(path))
    with _LOCK:
        if identity is None:
            _WRITTEN.pop(key_for(path), None)
            return "missing"
        _WRITTEN[key_for(path)] = identity
    return "recorded"


def prepare(store, path, max_bytes=MAX_FILE_BYTES):
    """The document became modified: start copying its file in the background, unless a copy of the current file
    is already staged or running. Returns "started", "pending", "missing" or "too-large"."""
    stat = _stat(path)
    if stat is None:
        return "missing"
    key = key_for(path)
    with _LOCK:
        pending = _PENDING.get(key)
        if pending is not None:
            if pending.thread.is_alive() or (pending.staged is not None and pending.staged.matches(stat)):
                return "pending"
            pending.discard()
            del _PENDING[key]
        if stat.st_size > max_bytes:
            return "too-large"
        pending = _PENDING[key] = Pending(store, path, max_bytes)
        pending.thread.start()
    return "started"


def autosave_keeps(store, path, clock=None):
    """Whether the next AutoSave of `path` keeps a copy: the first AutoSave of this opening, or the newest copy is older
    than AUTOSAVE_SPACING_SECONDS (or there is none). Errors of the store count as "keep" (the save decides then)."""
    with _LOCK:
        if key_for(path) not in _AUTOSAVED:
            return True
    try:
        newest = store.newest_captured(path)
    except Exception:  # noqa: BLE001 - a busy or damaged store: before_save reports it
        return True
    now = clock() if clock is not None else time.time()
    return newest is None or now - newest >= AUTOSAVE_SPACING_SECONDS


def autosaved(path):
    """An AutoSave of `path` ran in this opening (OnSave of an AutoSave, kept or not)."""
    with _LOCK:
        _AUTOSAVED.add(key_for(path))


def skip(path):
    """An AutoSave keeps no copy: drop the staged copy, the next change stages the file AutoSave wrote."""
    with _LOCK:
        pending = _PENDING.pop(key_for(path), None)
    if pending is not None:
        pending.discard()
    return "coalesced"


def discard(path):
    """The document was closed (or the feature turned off): drop any staged copy of its file and its save record."""
    with _LOCK:
        _WRITTEN.pop(key_for(path), None)
        _AUTOSAVED.discard(key_for(path))
        pending = _PENDING.pop(key_for(path), None)
    if pending is not None:
        pending.discard()


def prune_soon(store):
    """Apply the store-wide limits (2 GB, and the age of copies of documents not saved lately) in the background:
    it reads every index, which on a large store would cost the save a noticeable pause. One run at a time."""
    def run():
        try:
            store.prune()
        except Exception:  # noqa: BLE001 - a busy store prunes on the next save
            from . import diag_log
            diag_log.exception("version_capture")

    with _LOCK:
        running = _PRUNING.get("thread")
        if running is not None and running.is_alive():
            return running
        thread = _PRUNING["thread"] = threading.Thread(target=run, name="hst-version-prune", daemon=True)
        thread.start()
        return thread


def before_save(store, path, modified=True, wait=WAIT_SECONDS, max_bytes=MAX_FILE_BYTES, clock=time.monotonic):
    """OnSave: store the file as it is on disk now. Returns "stored", "duplicate", "unchanged" (unmodified document,
    file still as this office wrote it), "missing" (first save, nothing to keep), "too-large", "timeout", "changed",
    "busy" or "failed"."""
    deadline = clock() + wait
    stat = _stat(path)
    with _LOCK:
        pending = _PENDING.pop(key_for(path), None)
        unchanged = not modified and stat is not None and _WRITTEN.get(key_for(path)) == _identity(stat)
    if unchanged:
        if pending is not None:
            pending.discard()
        return "unchanged"
    if stat is None or stat.st_size > max_bytes:
        if pending is not None:
            pending.discard()
        return "missing" if stat is None else "too-large"
    try:
        if pending is not None:
            pending.thread.join(max(0.0, deadline - clock()))
            if pending.thread.is_alive():
                pending.discard()  # stops within one chunk; its handle is closed before the office replaces the file
                pending.thread.join(1.0)
                return "timeout"
            if pending.staged is not None and pending.staged.matches(stat):
                return _added(store, store.add(path, pending.staged))
            pending.discard()
        return _added(store, store.capture(path, deadline=deadline, max_bytes=max_bytes))
    except Cancelled:
        return "timeout"
    except Changed:
        return "changed"
    except StoreBusy:
        return "busy"
    except FileNotFoundError:
        return "missing"
    except Exception:  # noqa: BLE001 - copy failures never block the save (the job logs the traceback)
        from . import diag_log
        diag_log.exception("version_capture")
        return "failed"


def _added(store, outcome):
    if outcome == "stored":
        prune_soon(store)
    return outcome
