# SPDX-License-Identifier: AGPL-3.0-only
"""Per-user desktop integration of the HST Office AppImage (no root): launchers, icons and MIME types in
$XDG_DATA_HOME (default ~/.local/share), pointing at the AppImage file itself.

Run by AppRun with the bundled python:
  --auto      first start, or the AppImage was moved/renamed: (re)write the integration; nothing when the user
              removed it before, or when HST Office is installed system-wide (.deb/.rpm launchers already exist)
  --install   write it now (also over a system-wide install, also after an earlier removal)
  --remove    delete every file it wrote and remember the choice (the "Gỡ khỏi menu ứng dụng" launcher action)
State: $XDG_DATA_HOME/hst-office/appimage-integration.json (written files) and appimage-integration.state
(one line: the integrated AppImage path, or "removed"; AppRun compares it in sh to skip python on normal starts).
Launcher IDs are the system package's (vn.hasontech.hstoffice-*.desktop), so window matching (StartupWMClass,
Wayland app_id) and HST's default-apps question work the same.
"""
import json
import os
import shutil
import subprocess
import sys

PREFIX = "vn.hasontech.hstoffice"
SYSTEM_LAUNCHER = "/usr/share/applications/%s-startcenter.desktop" % PREFIX
MIME_NAME = PREFIX + "-appimage.xml"
REMOVE_ACTION = ("\n[Desktop Action RemoveIntegration]\nName=Gỡ khỏi menu ứng dụng\n"
                 "Name[en]=Remove from the application menu\nExec=%s --remove-desktop-integration\n")


def data_home(environ):
    return environ.get("XDG_DATA_HOME") or os.path.join(environ.get("HOME") or os.path.expanduser("~"), ".local", "share")


def state_paths(environ):
    base = os.path.join(data_home(environ), "hst-office")
    return os.path.join(base, "appimage-integration.json"), os.path.join(base, "appimage-integration.state")


def exec_quote(path):
    """The AppImage path as one Exec argument (Desktop Entry spec: quoted, `"` `` ` `` `$` `\\` escaped, `%` doubled),
    then string-escaped for the key file (backslashes doubled)."""
    if any(ord(c) < 32 for c in path):
        raise ValueError("control character in the AppImage path")
    inner = "".join("\\" + c if c in '"`$\\' else c for c in path).replace("%", "%%")
    return ('"%s"' % inner).replace("\\", "\\\\")


def rewrite_desktop(text, appimage, startcenter=False):
    """Launcher text of the AppImage: every Exec runs the AppImage; the Start Center gets the removal action."""
    command = exec_quote(appimage)
    out = []
    for line in text.splitlines():
        if line.startswith("TryExec="):
            continue
        if line.startswith("Exec="):
            words = line[5:].split(" ", 1)
            line = "Exec=" + command + (" " + words[1] if len(words) > 1 else "")
        if startcenter and line.startswith("Actions="):
            line = line.rstrip(";") + ";RemoveIntegration;"
        out.append(line)
    text = "\n".join(out) + "\n"
    return text + REMOVE_ACTION % command if startcenter else text


def launchers(appdir):
    """{desktop id: source file} as the system package installs them (usr/share/applications links into the tree)."""
    apps, found = os.path.join(appdir, "usr", "share", "applications"), {}
    for name in sorted(os.listdir(apps)):
        if name.startswith(PREFIX) and name.endswith(".desktop"):
            target = os.readlink(os.path.join(apps, name)) if os.path.islink(os.path.join(apps, name)) else os.path.join(apps, name)
            found[name] = os.path.join(appdir, target.lstrip("/")) if os.path.isabs(target) else os.path.join(apps, target)
    return found


def _write(path, data, written):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".hst-tmp"
    with open(temp, "wb") as handle:
        handle.write(data)
    os.replace(temp, path)
    written.append(path)


def _refresh(home):
    for argv in (["update-mime-database", os.path.join(home, "mime")],
                 ["update-desktop-database", "-q", os.path.join(home, "applications")],
                 ["gtk-update-icon-cache", "-q", "-t", "-f", os.path.join(home, "icons", "hicolor")]):
        if shutil.which(argv[0]) and os.path.isdir(argv[-1]):
            subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def _load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def remove(environ):
    """Delete the files of the last integration (only those, and only inside $XDG_DATA_HOME); remember it."""
    manifest, state = state_paths(environ)
    home = os.path.realpath(data_home(environ))
    for path in _load(manifest).get("files", []):
        if isinstance(path, str) and os.path.realpath(path).startswith(home + os.sep):
            try:
                os.unlink(path)
            except OSError:
                pass
    _refresh(home)
    _write(manifest, b'{"files": []}\n', [])
    _write(state, b"removed\n", [])
    return 0


def install(appdir, appimage, environ):
    manifest, state = state_paths(environ)
    home = data_home(environ)
    if _load(manifest).get("files"):
        remove(environ)  # an older location: start from a clean slate
    written = []
    for desktop_id, source in launchers(appdir).items():
        with open(source, encoding="utf-8") as handle:
            text = rewrite_desktop(handle.read(), appimage, desktop_id.endswith("-startcenter.desktop"))
        _write(os.path.join(home, "applications", desktop_id), text.encode("utf-8"), written)
    icons = os.path.join(appdir, "usr", "share", "icons", "hicolor")
    for base, _, names in os.walk(icons):
        for name in names:
            if name.startswith(PREFIX):
                with open(os.path.join(base, name), "rb") as handle:
                    rel = os.path.relpath(os.path.join(base, name), icons)
                    _write(os.path.join(home, "icons", "hicolor", rel), handle.read(), written)
    mime = os.path.join(appdir, "usr", "share", "mime", "packages")
    for name in os.listdir(mime) if os.path.isdir(mime) else []:
        with open(os.path.join(mime, name), "rb") as handle:
            _write(os.path.join(home, "mime", "packages", MIME_NAME), handle.read(), written)
    _write(manifest, (json.dumps({"appimage": appimage, "files": written}, indent=1) + "\n").encode("utf-8"), [])
    _write(state, (appimage + "\n").encode("utf-8"), [])
    _refresh(home)
    return 0


def auto(appdir, appimage, environ, system_launcher=SYSTEM_LAUNCHER):
    """AppRun's start-up call: True when it (re)integrated."""
    _, state = state_paths(environ)
    try:
        with open(state, encoding="utf-8") as handle:
            current = handle.read().strip()
    except OSError:
        current = None
    if current == "removed" or current == appimage:
        return False
    if current is None and os.path.exists(system_launcher):
        return False  # a .deb/.rpm install owns the menu; --install overrides
    install(appdir, appimage, environ)
    if current is None and shutil.which("notify-send"):
        subprocess.run(["notify-send", "-i", PREFIX + "-startcenter", "HST Office",
                        "Đã thêm HST Office vào menu ứng dụng. Gỡ: chuột phải biểu tượng → Gỡ khỏi menu ứng dụng."],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return True


def main(argv, environ):
    appdir, appimage = environ.get("APPDIR"), environ.get("APPIMAGE")
    if len(argv) != 2 or argv[1] not in ("--auto", "--install", "--remove"):
        print("usage: %s --auto|--install|--remove" % argv[0], file=sys.stderr)
        return 64
    if argv[1] == "--remove":
        return remove(environ)
    if not appdir or not appimage or not os.path.isabs(appimage) or not os.path.isfile(appimage):
        print("HST Office: not started from an AppImage (APPDIR/APPIMAGE unset)", file=sys.stderr)
        return 2
    if argv[1] == "--install":
        return install(appdir, appimage, environ)
    auto(appdir, appimage, environ)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv, os.environ))
    except (OSError, ValueError) as exc:
        print("HST Office desktop integration: %s" % exc, file=sys.stderr)
        sys.exit(1)
