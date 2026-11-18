# SPDX-License-Identifier: AGPL-3.0-only
"""What the office does at the first start after "Cập nhật ngay" closed it: reopen the documents, say how it went.

Right before the office quits for an update, update_install writes update-pending.json beside update.log: the release
it ran (`from`), the one being installed (`to`), the time, and the file URLs of the documents that were open. The
helper reopens HST Office after installing (or, when the install failed, the old build). At that start this module:
- opens those documents again (files that still exist; untitled documents cannot be reopened);
- `to` runs: a short note on the first reopened document that the update is installed;
- `from` still runs and the helper recorded a failure (update-result.json): update_outcome shows it, nothing here;
- `from` still runs, no failure record and the helper has had time to finish: the helper never installed anything
  (stopped, killed or never started), which is reported once instead of passing in silence.
A record younger than HELPER_GRACE with `from` still running is kept: the user may have opened the office by hand
while the helper still waits or installs. A record older than MAX_AGE is dropped without a word.
The file stays on this machine.
"""
import json
import os
import stat
import time

PENDING_NAME = "update-pending.json"
MAX_SIZE = 64 * 1024
MAX_DOCUMENTS = 50
HELPER_GRACE = 40 * 60  # the helper waits up to 30 minutes for the office to exit, then installs
MAX_AGE = 24 * 3600
INFOBAR_ID = "hst-update-installed"


def document_urls(desktop):
    """file:// URLs of the documents open in the office's frames, in frame order, without duplicates."""
    urls = []
    frames = desktop.getFrames()
    for index in range(frames.getCount()):
        try:
            controller = frames.getByIndex(index).getController()
            model = controller.getModel() if controller is not None else None
            url = model.getURL() if model is not None and hasattr(model, "getURL") else ""
        except Exception:  # noqa: BLE001 - a frame closing meanwhile, or the Start Center (no model)
            continue
        if isinstance(url, str) and url.startswith("file:///") and url not in urls:
            urls.append(url)
    return urls[:MAX_DOCUMENTS]


def write(cache, release_from, release_to, urls, now=None):
    """Write the record (atomic rename); returns its path."""
    os.makedirs(cache, mode=0o700, exist_ok=True)
    path = os.path.join(cache, PENDING_NAME)
    record = {"schema": 1, "from": release_from, "to": release_to, "time": int(time.time() if now is None else now),
              "documents": list(urls)[:MAX_DOCUMENTS]}
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
    os.replace(temp, path)
    return path


def discard(cache):
    try:
        os.unlink(os.path.join(cache, PENDING_NAME))
    except FileNotFoundError:
        pass


def read(cache):
    """The record as a dict, or None when there is none or it is not valid (a broken file is removed)."""
    path = os.path.join(cache, PENDING_NAME)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(MAX_SIZE + 1) if stat.S_ISREG(os.fstat(handle.fileno()).st_mode) else b""
        record = json.loads(raw.decode("utf-8")) if 0 < len(raw) <= MAX_SIZE else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        record = None
    valid = isinstance(record, dict) and record.get("schema") == 1 and all(
        isinstance(record.get(key), str) for key in ("from", "to")) and type(record.get("time")) is int \
        and isinstance(record.get("documents"), list) and all(
            isinstance(url, str) and url.startswith("file:///") for url in record["documents"])
    if not valid:
        discard(cache)
        return None
    return record


def decide(record, current_release, failure_recorded, now):
    """Pure: (action, keep). action: "installed" | "failed" (update_outcome reports it) | "stopped" | "wait" | "stale"."""
    age = now - record["time"]
    if age > MAX_AGE or age < -300:
        return "stale", False
    if current_release == record["to"]:
        return "installed", False
    if current_release != record["from"]:
        return "stale", False  # another version runs: installed some other way
    if failure_recorded:
        return "failed", False
    if age < HELPER_GRACE:
        return "wait", True
    return "stopped", False


def _show_installed(ctx, frame, release):
    from .update_texts import texts
    try:
        controller = frame.getController()
        if controller is not None and hasattr(controller, "appendInfobar"):
            controller.appendInfobar(INFOBAR_ID, texts(ctx)["installed"] % release, "", 0, (), True)  # 0 = INFO
    except Exception:  # noqa: BLE001 - cosmetic
        pass


def _show_stopped(ctx, record, log):
    from .update_install import _ask, manual_download
    from .update_texts import texts
    text = texts(ctx)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = desktop.getCurrentFrame()
    message = "%s\n%s" % (text["outcome_stopped"] % ("HST Office %s" % record["to"]), text["outcome_next"] % log)
    if _ask(ctx, frame.getContainerWindow() if frame else None, text["install_title"], message,
            [(text["download"], "download"), (text["close"], "close")], text_height=52) == "download":
        manual_download(ctx)


def reopen(ctx, urls):
    """Load each still existing document; returns the frame of the first one loaded, or None."""
    import uno
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    first = None
    for url in urls:
        try:
            if not os.path.isfile(uno.fileUrlToSystemPath(url)):
                continue
            model = desktop.loadComponentFromURL(url, "_default", 0, ())
            if first is None and model is not None:
                first = model.getCurrentController().getFrame()
        except Exception:  # noqa: BLE001 - a document that cannot be opened again must not stop the others
            from . import diag_log
            diag_log.exception("update_resume")
    return first


def start_up(ctx):
    """Called by the start-up dispatcher (startup_prompts.run) on every start: one stat when nothing is pending; the work runs on the main thread
    after the start-up event. Must run before update_outcome.show_pending, which removes the failure record."""
    import platform
    from . import update_installer as installer
    from .update_fetch import release_info
    from .update_outcome import STATE_NAME
    cache = installer.cache_dir(platform.system())
    if not os.path.lexists(os.path.join(cache, PENDING_NAME)):
        return False
    failure_recorded = os.path.lexists(os.path.join(cache, STATE_NAME))
    release = release_info()["release"]
    from . import update_ui as ui
    ui.on_main_thread(ctx, lambda: handle(ctx, cache, release, failure_recorded))
    return True


def handle(ctx, cache, current_release, failure_recorded, now=None):
    """Start-up step (main thread; failure_recorded was read before update_outcome took its record). Returns the action."""
    record = read(cache)
    if record is None:
        return None
    action, keep = decide(record, current_release, failure_recorded, int(time.time() if now is None else now))
    if not keep:
        discard(cache)
    if action in ("installed", "failed", "stopped"):
        frame = reopen(ctx, record["documents"])
        if action == "installed" and frame is not None:
            _show_installed(ctx, frame, record["to"])
        elif action == "stopped":
            _show_stopped(ctx, record, os.path.join(cache, "update.log"))
    return action
