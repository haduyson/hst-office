# SPDX-License-Identifier: AGPL-3.0-only
"""Windows UNO checks that tell "the office is waiting on a dialog" from "the office hangs".

Why: a document loaded from the UNO bridge thread (no OnMainThread) whose import removes a drawing shape (every .docx
with an OLE object: writerfilter drops the OLE replacement shape) waits in vcl Scheduler::IdlesLockGuard until the
main thread is back in Application::Execute. A synchronous modal dialog on the main thread (the HST start-up
questions on the first visible window, "Document in Use" for a stale lock file, any Dialog::Execute) keeps it in a
nested loop, so the load waits until a user closes the dialog. The same dialogs veto close(): a harness that then
kills the office leaves a .~lock file, and the next visible open of that file waits on "Document in Use".
The 1.0.2 smoke reported such waits as an embedded-Calc .docx hang on HST3 (plans/reports/
debugger-261116-0000-docx-ole-reopen-hang.md). The rules here, used by check-windows-embedded-calc-roundtrip.py:
- load through uno_main_thread_load (OnMainThread=True);
- run in a private profile settled and QUIET-seeded after the initialising soffice.bin has exited (quiet_profile);
- open a fresh copy per load (fresh_copy) and, after a forced stop, remove only our own lock files (remove_own_locks);
- on a timeout or a close veto, record the office's modal window titles before calling anything a hang (bounded,
  close_or_report).
The pure parts (names, lock ownership, the verdict) are unit-tested on any platform; window queries need Windows.
"""
import itertools
import os
import shutil
import threading
import uuid

QUIET = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
         ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")]
_COUNTER = itertools.count(1)


def fresh_copy(src, folder, tag):
    """Copy `src` to a name never used before in `folder` (no lock file of an earlier run can apply to it)."""
    stem, ext = os.path.splitext(os.path.basename(src))
    dst = os.path.join(folder, "%s-%s-%03d-%s%s" % (stem, tag, next(_COUNTER), uuid.uuid4().hex[:8], ext))
    os.makedirs(folder, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def lock_path(document):
    folder, name = os.path.split(document)
    return os.path.join(folder, ".~lock.%s#" % name)


def _norm_url(url):
    return url.strip().rstrip("/").replace("\\", "/").lower()


def lock_owner_url(text):
    """The profile URL a lock file names: its last comma field (",user,host,time,<UserInstallation URL>;")."""
    fields = text.strip().rstrip(";").split(",")
    return fields[-1] if len(fields) >= 5 else ""


def remove_own_locks(documents, profile_url):
    """After a forced stop: delete the lock files of `documents` written by our profile, never another's."""
    removed = []
    for document in documents:
        path = lock_path(document)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                owner = lock_owner_url(handle.read())
        except OSError:
            continue
        if owner and _norm_url(owner) == _norm_url(profile_url):
            os.remove(path)
            removed.append(path)
    return removed


def registry_has(xcu_text, config):
    """True when every (node, property, value) of `config` is in a registrymodifications.xcu text as seeded."""
    return all('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>' % item in xcu_text
               for item in config)


def quiet_profile(program, profile, workdir, config=()):
    """Create, settle and seed `profile` with QUIET + `config`; raise when the seed is not in the file afterwards.

    settle_profile runs soffice.bin itself (not the soffice.exe launcher, which returns before soffice.bin has
    rewritten the profile), and seeding starts only once no soffice.bin of this profile is left."""
    import time
    from hst_gui_profile import seed_profile
    from hst_gui_windows import settle_profile
    import windows_gui_processes as processes
    shutil.rmtree(profile, ignore_errors=True)
    os.makedirs(profile, exist_ok=True)
    if not settle_profile(program, profile, workdir):
        raise RuntimeError("profile %s did not settle (bundled extensions not synchronised)" % profile)
    url = "file:///" + os.path.abspath(profile).replace("\\", "/")
    for _ in range(60):
        if not processes.profile_bin_pids(url):
            break
        time.sleep(1)
    else:
        raise RuntimeError("a soffice.bin of %s is still running; seeding now would be overwritten" % profile)
    wanted = QUIET + list(config)
    seed_profile(profile, wanted)
    with open(os.path.join(profile, "user", "registrymodifications.xcu"), encoding="utf-8") as handle:
        if not registry_has(handle.read(), wanted):
            raise RuntimeError("QUIET seed missing from %s" % profile)
    return url


def modal_titles(rows):
    """Titles of the visible owned windows (rows: hwnd, class, title, visible, owner hwnd) that are dialogs: VCL
    dialogs are SALSUBFRAME windows owned by a frame; an owned window without a title is a tooltip or popup."""
    return [title for _hwnd, cls, title, visible, owner in rows if visible and owner and title and cls == "SALSUBFRAME"]


def verdict(finished, titles):
    """'done' | 'waiting-on-dialog' (a modal is up: the wait is the dialog's, not a hang) | 'hang'."""
    if finished:
        return "done"
    return "waiting-on-dialog" if titles else "hang"


def window_rows(pids):
    """(hwnd, class, title, visible, owner) of every top-level window of the processes `pids` (Windows only)."""
    import ctypes
    user32, rows = ctypes.windll.user32, []
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def visit(hwnd, _param):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value in pids:
            title, cls = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 128)
            rows.append((hwnd, cls.value, title.value, bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd))),
                         user32.GetWindow(ctypes.c_void_p(hwnd), 4) or 0))  # GW_OWNER
        return True
    user32.EnumWindows(proto(visit), 0)
    return rows


def office_modal_titles(profile_url):
    import windows_gui_processes as processes
    return modal_titles(window_rows(set(processes.profile_bin_pids(profile_url))))


def bounded(call, timeout, profile_url, titles_of=office_modal_titles):
    """Run `call()` in a thread for at most `timeout` s. Returns (verdict, value or exception, modal titles); the
    titles are read when the call has not returned, so a report names the dialog the office is waiting on."""
    box = {}

    def run():
        try:
            box["value"] = call()
        except Exception as error:  # noqa: BLE001 - reported to the caller
            box["error"] = error
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)
    finished = not thread.is_alive()
    titles = [] if finished else titles_of(profile_url)
    return verdict(finished, titles), box.get("value", box.get("error")), titles


def close_or_report(document, profile_url, titles_of=office_modal_titles):
    """close(True); on a veto return the modal titles that caused it (None when the document closed)."""
    try:
        document.close(True)
        return None
    except Exception as error:  # noqa: BLE001 - CloseVetoException over the bridge
        return {"error": str(error)[:120], "modal": titles_of(profile_url)}
