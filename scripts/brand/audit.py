# SPDX-License-Identifier: AGPL-3.0-only
"""Brand audit: generated-asset verification and leftover upstream-name scan."""
import fnmatch
import json
import os
import re
import xml.etree.ElementTree as ET

from PIL import Image

FORBIDDEN = re.compile(r"libre\s?office|document\s+foundation|openoffice", re.IGNORECASE)
# Extensions / names of files that can show text to users. Binary libraries are not scanned.
SCAN_SUFFIXES = {".xcd", ".xcu", ".xml", ".ui", ".desktop", ".ini", ".rc", ".html", ".htm", ".txt", ".md",
                 ".svg", ".properties", ".mo", ".json", ".xhp", ".xlf", ".appdata", ".metainfo", ".po", ".sh"}
SCAN_NAMES = re.compile(r"(^|/)(\w*rc|bootstrap\.ini|\w*\.ini|LICENSE\w*|NOTICE\w*|CREDITS\w*)$", re.IGNORECASE)
MAX_BYTES = 32 * 1024 * 1024


def _read(path, mode="r", limit=-1):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read(limit)


def _png_size(path):
    with Image.open(path) as image:
        return image.format, image.size


def check_assets(spec, root):
    """Return a list of human-readable problems (empty == OK)."""
    errors = []
    lo = spec["libreofficeBranding"]
    base = os.path.join(root, lo["dir"])
    for name in lo["requiredByConfigure"] + lo["optional"]:
        if not os.path.isfile(os.path.join(base, name)):
            errors.append(f"missing {lo['dir']}/{name}")
    if errors:
        return errors
    w, h = lo["introSize"]
    expect = {"intro.png": (w, h), "intro-highres.png": (2 * w, 2 * h), "donate1.png": (200, 200),
              "donate2.png": (150, 150)}
    for name, size in expect.items():
        fmt, got = _png_size(os.path.join(base, name))
        if fmt != "PNG" or got != size:
            errors.append(f"{name}: expected PNG {size}, got {fmt} {got}")
    for name in (n for n in lo["requiredByConfigure"] if n.endswith(".svg")):
        errors += _check_svg(os.path.join(base, name), name)
    conf = _read(os.path.join(base, "progress.conf"))
    for key in lo["progress"]:
        if not re.search(rf'^{key}="[\d, ]+"$', conf, re.M):
            errors.append(f"progress.conf: bad or missing {key}")
    icons = spec["appIcons"]
    names = [icons["productName"]] + [m["name"] for m in icons["modules"]]
    for name in names:
        for size in icons["sizes"]:
            path = os.path.join(root, icons["pattern"].format(name=name, size=size))
            if not os.path.isfile(path) or _png_size(path) != ("PNG", (size, size)):
                errors.append(f"icon {name}-{size}.png missing or wrong size")
        for rel in (icons["scalablePattern"].format(name=name), f"{icons['masters']['dir']}/{name}.svg"):
            path = os.path.join(root, rel)
            if not os.path.isfile(path) or not _read(path, "rb", 200).lstrip().startswith(b"<"):
                errors.append(f"{rel} missing or not SVG")
    plat = spec["platformIcons"]
    containers = [(plat["ico"], b"\x00\x00\x01\x00"), (plat["icns"], b"icns")]
    containers += [(plat["icnsPattern"].format(name=m["name"]), b"icns") for m in icons["modules"]]
    win = spec["windowsAppIcons"]
    containers += [(f"{win['dir']}/{name}", b"\x00\x00\x01\x00") for name in win["icons"]]
    for rel, magic in containers:
        path = os.path.join(root, rel)
        if not os.path.isfile(path) or _read(path, "rb", 4) != magic:
            errors.append(f"{rel} missing or not a valid container")
    return errors


def _check_svg(path, name):
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return [f"{name}: invalid XML ({exc})"]
    problems = []
    if not tree.getroot().tag.endswith("}svg"):
        problems.append(f"{name}: root is not svg")
    images = [e for e in tree.iter() if e.tag.endswith("}image")]
    if not images:
        problems.append(f"{name}: no embedded image")
    for element in images:
        href = next((v for k, v in element.attrib.items() if k.endswith("href")), "")
        if not href.startswith("data:image/png;base64,"):
            problems.append(f"{name}: image must be an embedded data URI")
    text = re.sub(r"base64,[A-Za-z0-9+/=]+", "", _read(path))
    if FORBIDDEN.search(text):
        problems.append(f"{name}: contains upstream product name")
    return problems


def load_allowlist(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    for entry in data["entries"]:
        if not entry.get("reason") or not entry.get("path"):
            raise ValueError(f"allowlist entry needs path and reason: {entry}")
    return data["entries"]


def _allowed(rel, line, entries):
    for entry in entries:
        if fnmatch.fnmatch(rel, entry["path"]) and (not entry.get("regex") or re.search(entry["regex"], line)):
            return True
    return False


def _scannable(rel):
    return os.path.splitext(rel)[1].lower() in SCAN_SUFFIXES or SCAN_NAMES.search(rel) is not None


def scan_tree(install_root, entries):
    """Return (hits, scanned_count); hit = (relative path, line number, excerpt)."""
    hits, scanned = [], 0
    for folder, _dirs, files in os.walk(install_root):
        for name in sorted(files):
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, install_root).replace(os.sep, "/")
            if os.path.islink(full) or not _scannable(rel) or os.path.getsize(full) > MAX_BYTES:
                continue
            scanned += 1
            with open(full, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace")
            for number, line in enumerate(re.split(r"[\r\n\x00]+", text), 1):
                match = FORBIDDEN.search(line)
                if match and not _allowed(rel, line, entries):
                    start = max(0, match.start() - 30)
                    hits.append((rel, number, line[start:match.end() + 30].strip()))
    return hits, scanned
