# SPDX-License-Identifier: AGPL-3.0-only
"""Find installed libraries, without opening a token or asking for credentials."""
import glob
import os
from pathlib import Path
import sys

from .data_files import load_data


def platform_name():
    return "macos" if sys.platform == "darwin" else "windows" if sys.platform == "win32" else "linux"


def _paths(root, pattern):
    return sorted(Path(p) for p in glob.glob(str(Path(root) / pattern.lstrip("/"))))


def _fields(path):
    if not path.exists():
        return {}
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def _module_paths(root, module):
    if not module:
        return []
    patterns = [module] if module.startswith("/") else [
        directory + module for directory in ("/usr/lib/*/pkcs11/", "/usr/lib/pkcs11/", "/usr/lib64/pkcs11/")]
    return [path for pattern in patterns for path in _paths(root, pattern)]


def p11_policy(root, home):
    """Resolve global policy and canonical exclusions before catalog merging."""
    from .usb_token_errors import SetupError
    user = Path(home) / ".config/pkcs11"
    if str(root) == "/" and os.environ.get("XDG_CONFIG_HOME"):
        user = Path(os.environ["XDG_CONFIG_HOME"]) / "pkcs11"
    admin = Path(root) / "etc/pkcs11"
    policy = _fields(admin / "pkcs11.conf").get("user-config", "merge")
    if policy != "none":
        policy = _fields(user / "pkcs11.conf").get("user-config", policy)
    if policy not in ("none", "merge", "only"):
        raise SetupError("Chính sách p11-kit không hợp lệ; chưa thay đổi kho chứng thư.")
    dirs = [] if policy == "only" else [Path(root) / "usr/share/p11-kit/modules", admin / "modules"]
    if policy != "none":
        dirs.append(user / "modules")
    configs, excluded = {}, set()
    for directory in dirs:
        for path in sorted(directory.glob("*.module")):
            fields = _fields(path)
            old = configs.get(path.name, {})
            if old.get("module") != fields.get("module"):
                excluded.update(str(p.resolve()) for p in _module_paths(root, old.get("module", "")))
            configs[path.name] = fields
    found = []
    for name, fields in configs.items():
        paths = _module_paths(root, fields.get("module", ""))
        programs = {"soffice", "soffice.bin"}
        enabled = set(fields.get("enable-in", "").replace(",", " ").split())
        disabled = set(fields.get("disable-in", "").replace(",", " ").split())
        if fields.get("trust-policy") == "yes" or (enabled and not enabled & programs) or disabled & programs:
            excluded.update(str(path.resolve()) for path in paths)
        else:
            found.extend(dict(vendor="p11-kit", label="p11-kit: " + name[:-7], path=str(path)) for path in paths)
    return found, excluded


def p11_modules(root, home):
    found, excluded = p11_policy(root, home)
    return [row for row in found if str(Path(row["path"]).resolve()) not in excluded]


def detect(platform=None, root="/", home=None, entries=None):
    platform = platform or platform_name()
    entries = load_data("pkcs11-modules.json")["modules"] if entries is None else entries
    found = []
    for entry in entries:
        if platform != entry["platform"]:
            continue
        for pattern in entry["paths"]:
            found.extend(dict(vendor=entry["vendor"], label=entry["label"], path=str(path))
                         for path in _paths(root, pattern))
    excluded = set()
    if platform == "linux":
        modules, excluded = p11_policy(root, home or Path.home())
        found.extend(modules)
    unique = {}
    for item in found:
        path = Path(item["path"])
        if str(path.resolve()) not in excluded and path.is_file() and os.access(path, os.R_OK):
            unique.setdefault(str(path.resolve()), item)
    return list(unique.values())
