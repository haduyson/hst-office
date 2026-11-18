# SPDX-License-Identifier: AGPL-3.0-only
"""HST Writer, HST Sheets, HST Slides, HST Draw and HST PDF where Launchpad, Spotlight and Finder see them (macOS).

No uno here (tested in tests/unit); hst_office/mac_app_launchers_ui.py is the office side. The launcher apps ship
inside HST Office.app/Contents/Helpers (scripts/macos/make-app-launchers.py). sync() runs at every start of an
installed HST Office:
  - first start: copies all five into /Applications when this user can write it without an administrator password,
    else into ~/Applications, and leaves a one-time notice pending;
  - a new HST Office version: replaces the copies that are still there, adds launchers new in this version, and
    never re-adds one the user deleted;
  - after "Gỡ biểu tượng ứng dụng" (remove()): nothing, until "Thêm lại biểu tượng ứng dụng" (install()).
A folder that already holds HST launchers is reused (never a second set); only bundles with the id <HST Office
id>.launcher.* are replaced or removed. ditto keeps the code signature; --noqtn: no quarantine on the app's own copies.
"""
import json
import os
import plistlib
import shutil
import subprocess

NAMES = ("HST Writer", "HST Sheets", "HST Slides", "HST Draw", "HST PDF")
HELPERS = ("Contents", "Helpers")
SYSTEM_FOLDER = "/Applications"
STATE = ("Library", "Application Support", "HSTOffice", "app-launchers.json")
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/"
              "lsregister")
TIMEOUT = 60


class LauncherError(RuntimeError):
    """A failure the user is told about in Vietnamese (the message is the text shown)."""


def _home(home):
    return os.path.expanduser("~") if home is None else home


def read_info(app):
    """Info.plist of an app bundle as a dict, {} when it cannot be read."""
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as handle:
            info = plistlib.load(handle)
    except Exception:  # noqa: BLE001 - plistlib raises several types for a damaged file; absent counts as unknown
        return {}
    return info if isinstance(info, dict) else {}


def host_identity(bundle):
    """(bundle id, version) of the running HST Office. Raises LauncherError when its Info.plist lacks them."""
    info = read_info(bundle)
    host_id, version = info.get("CFBundleIdentifier"), info.get("CFBundleVersion")
    if not isinstance(host_id, str) or not host_id or not isinstance(version, str) or not version:
        raise LauncherError("Không đọc được thông tin của HST Office.")
    return host_id, version


def is_ours(app, host_id):
    """True when `app` is one of HST Office's launchers (pure apart from reading its Info.plist)."""
    bundle_id = read_info(app).get("CFBundleIdentifier")
    return isinstance(bundle_id, str) and bundle_id.startswith(host_id + ".launcher.")


def folders(home=None):
    """The two folders launchers may be copied to, in order of preference."""
    return [SYSTEM_FOLDER, os.path.join(_home(home), "Applications")]


def present(folder, host_id):
    """The names of HST's launchers in `folder`."""
    return [name for name in NAMES if is_ours(os.path.join(folder, name + ".app"), host_id)]


def target_folder(host_id, home=None, writable=None):
    """The folder that already holds HST launchers, else /Applications when writable without a password, else
    ~/Applications."""
    candidates = folders(home)
    found = [folder for folder in candidates if present(folder, host_id)]
    if found:
        return found[0]
    if (writable or (lambda path: os.access(path, os.W_OK)))(SYSTEM_FOLDER):
        return SYSTEM_FOLDER
    return candidates[1]


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LauncherError("Không chạy được %s: %s" % (os.path.basename(argv[0]), exc)) from exc


def copy_bundle(source, target, run=_run):
    """Copy an app bundle with ditto to a hidden name beside `target`, then swap it in (an old copy is replaced
    whole, never merged)."""
    folder, name = os.path.split(target)
    partial, old = os.path.join(folder, "." + name + ".partial"), os.path.join(folder, "." + name + ".old")
    for leftover in (partial, old):
        shutil.rmtree(leftover, ignore_errors=True)
    done = run(["ditto", "--noqtn", source, partial])
    if done.returncode != 0:
        shutil.rmtree(partial, ignore_errors=True)
        raise LauncherError("Không sao chép được %s." % os.path.splitext(name)[0])
    if os.path.lexists(target):
        os.rename(target, old)
    os.rename(partial, target)
    shutil.rmtree(old, ignore_errors=True)


def install(bundle, names=NAMES, home=None, writable=None, run=_run):
    """Copy the launchers `names` of the HST Office `bundle` into the target folder. Returns (folder, names copied).

    A same-named app that is not HST's is left alone. Raises LauncherError (or OSError) when a copy fails."""
    host_id, _version = host_identity(bundle)
    folder = target_folder(host_id, home, writable)
    os.makedirs(folder, exist_ok=True)
    copied = []
    for name in names:
        source = os.path.join(bundle, *HELPERS, name + ".app")
        target = os.path.join(folder, name + ".app")
        if not os.path.isdir(source):
            raise LauncherError("Bản HST Office này không có %s." % name)
        if os.path.lexists(target) and not is_ours(target, host_id):
            continue
        copy_bundle(source, target, run)
        copied.append(name)
    if copied:  # Launchpad and Spotlight notice new apps by themselves; registering now makes it immediate
        try:
            run([LSREGISTER, "-f"] + [os.path.join(folder, name + ".app") for name in copied])
        except LauncherError:
            pass  # best effort: the apps are in place either way
    return folder, copied


def remove(host_id, home=None):
    """Delete HST's launchers from both folders. Returns the paths removed."""
    removed = []
    for folder in folders(home):
        for name in present(folder, host_id):
            path = os.path.join(folder, name + ".app")
            shutil.rmtree(path)
            removed.append(path)
    return removed


def load_state(home=None):
    try:
        with open(os.path.join(_home(home), *STATE), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state, home=None):
    path = os.path.join(_home(home), *STATE)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    partial = path + ".tmp"
    with open(partial, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, sort_keys=True)
    os.replace(partial, path)


def plan(state, version, here):
    """The launchers to copy now (pure): all of them at the first start, none after a removal or when this version
    did it already; after an update the ones still in place (`here`) and those the last version did not install."""
    if state.get("removed"):
        return []
    if not state.get("version"):
        return list(NAMES)
    if state["version"] == version:
        return []
    before = state.get("installed") or []
    return [name for name in NAMES if name in here or name not in before]


def sync(bundle, home=None, writable=None, run=_run):
    """Start-up step of an installed HST Office. Returns the new state, or None when there was nothing to do."""
    host_id, version = host_identity(bundle)
    state = load_state(home)
    first = not state.get("version")
    here = present(target_folder(host_id, home, writable), host_id)
    names = plan(state, version, here)
    if not names and (state.get("removed") or state.get("version") == version):
        return None
    folder, copied = install(bundle, names, home, writable, run) if names else (state.get("folder"), [])
    state = dict(state, version=version, folder=folder, removed=False,
                 installed=sorted(set(state.get("installed") or []) | set(copied), key=NAMES.index))
    if first and copied:
        state["notice"] = "pending"
    save_state(state, home)
    return state


def set_removed(removed, version, folder=None, home=None):
    """Remember "Gỡ" (no copy at later starts) or "Thêm lại" (copies kept fresh again); no notice is left pending."""
    extra = {} if removed else {"folder": folder, "installed": list(NAMES)}
    save_state(dict(load_state(home), removed=removed, version=version, notice="shown", **extra), home)
