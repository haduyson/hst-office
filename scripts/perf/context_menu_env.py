# SPDX-License-Identifier: AGPL-3.0-only
"""Environment capture and profile preparation for context-menu runs."""
from __future__ import annotations

import itertools
import json
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path

# Process-name fragments of accessibility tools / window managers / clipboard managers / text
# tools that are known (or suspected) to hook mouse events, menus or the pasteboard.
WATCH_LIST = (
    "VoiceOver", "AccessibilityUIServer", "SwitchControl", "BetterTouchTool", "Moom", "Rectangle",
    "Magnet", "Amethyst", "yabai", "Hammerspoon", "Karabiner", "Keyboard Maestro", "Alfred",
    "Raycast", "Bartender", "Paste", "Maccy", "Clipy", "CleanClip", "Grammarly", "TextExpander",
    "Dropover", "1Password", "ScreenFlow", "TeamViewer", "AnyDesk", "Zoom", "Loom", "Sidecar")
UA = {"on": "true", "off": "false"}


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f"UNAVAILABLE: {exc}"


def lo_version(platform_name: str, app: Path) -> str:
    if platform_name == "macos":
        info = app / "Contents" / "Info.plist"
        if info.is_file():
            data = plistlib.loads(info.read_bytes())
            return f"{data.get('CFBundleShortVersionString', '?')} ({data.get('CFBundleVersion', '?')})"
        return "UNAVAILABLE: Info.plist not found"
    return run([str(app), "--version"])


def collect(platform_name: str, app: Path) -> dict:
    env = {"platform": platform_name, "uname_m": platform.machine(), "python": platform.python_version(),
           "libreoffice": lo_version(platform_name, app)}
    procs = run(["ps", "-axo", "comm"]).splitlines()
    env["watched_running"] = sorted({p for p in procs for w in WATCH_LIST if w.lower() in p.lower()})
    if platform_name == "macos":
        env["sw_vers"] = run(["sw_vers"])
        env["hw_model"] = run(["sysctl", "-n", "hw.model"])
        env["displays"] = run(["system_profiler", "SPDisplaysDataType", "-detailLevel", "mini"])[:1500]
    else:
        env["os_release"] = run(["sh", "-c", ". /etc/os-release && echo $PRETTY_NAME"])
        env["kernel"] = platform.release()
    return env


def expand_preset(matrix: dict, name: str) -> list[dict]:
    """Expand a preset into unique cells with an id, in stable order."""
    axes = matrix["axes"]
    if name not in matrix["presets"]:
        raise ValueError(f"unknown preset {name!r}; available: {sorted(matrix['presets'])}")
    seen: dict[str, dict] = {}
    for entry in matrix["presets"][name]["cells"]:
        values = [entry.get(a, [axes[a][0]]) for a in axes]
        for combo in itertools.product(*values):
            cell = dict(zip(axes, combo))
            cell["id"] = "{module}-{profile}-spell{autospell}-skia{skia}-{start}".format(**cell)
            seen.setdefault(cell["id"], cell)
    return list(seen.values())


def prepare_profile(cell: dict, work: Path, user_profile: Path | None) -> Path:
    """Create a per-launch profile dir (copy of user profile or fresh) with the cell's settings."""
    prof = work / "profile"
    if prof.exists():
        shutil.rmtree(prof)
    user = prof / "user"
    user.mkdir(parents=True)
    xcu = user / "registrymodifications.xcu"
    if cell["profile"] == "user" and user_profile and user_profile.is_dir():
        shutil.copytree(user_profile / "user" if (user_profile / "user").is_dir() else user_profile,
                        user, dirs_exist_ok=True, symlinks=True)
    items = (f'<item oor:path="/org.openoffice.Office.Linguistic/General"><prop oor:name="IsSpellAuto" '
             f'oor:op="fuse"><value>{UA[cell["autospell"]]}</value></prop></item>\n'
             '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="FirstRun" '
             'oor:op="fuse"><value>false</value></prop></item>\n'
             '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" '
             'oor:op="fuse"><value>false</value></prop></item>\n')
    if xcu.is_file():
        text = xcu.read_text(encoding="utf-8")
        xcu.write_text(text.replace("</oor:items>", items + "</oor:items>"), encoding="utf-8")
    else:
        xcu.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                       f'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n{items}</oor:items>\n',
                       encoding="utf-8")
    return prof


def load_matrix(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
