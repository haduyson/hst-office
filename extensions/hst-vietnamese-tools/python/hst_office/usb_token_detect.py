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


def p11_modules(root, home):
    """Read p11-kit registrations; user settings override admin/vendor settings.

    No module is loaded during detection. Relative module names use the usual
    Linux p11-kit module directories. Trust stores are not signing devices.
    """
    configs = {}
    dirs = [Path(root) / p for p in ("usr/share/p11-kit/modules", "etc/pkcs11/modules")]
    dirs.append(Path(home) / ".config/pkcs11/modules")
    if str(root) == "/" and os.environ.get("XDG_CONFIG_HOME"):
        dirs[-1] = Path(os.environ["XDG_CONFIG_HOME"]) / "pkcs11/modules"
    for directory in dirs:
        for path in sorted(directory.glob("*.module")):
            fields = {}
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for line in lines:
                if ":" in line and not line.lstrip().startswith("#"):
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            configs[path.name] = fields
    for name, fields in configs.items():
        module = fields.get("module", "")
        if not module or fields.get("trust-policy") == "yes":
            continue
        programs = {"soffice", "soffice.bin"}
        enabled = set(fields.get("enable-in", "").replace(",", " ").split())
        disabled = set(fields.get("disable-in", "").replace(",", " ").split())
        if (enabled and not enabled & programs) or disabled & programs:
            continue
        patterns = [module] if module.startswith("/") else [
            directory + module for directory in ("/usr/lib/*/pkcs11/", "/usr/lib/pkcs11/", "/usr/lib64/pkcs11/")]
        for pattern in patterns:
            for path in _paths(root, pattern):
                yield {"vendor": "p11-kit", "label": "p11-kit: " + name[:-7], "path": str(path)}


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
    if platform == "linux":
        found.extend(p11_modules(root, home or Path.home()))
    unique = {}
    for item in found:
        path = Path(item["path"])
        if path.is_file() and os.access(path, os.R_OK):
            unique.setdefault(str(path.resolve()), item)
    return list(unique.values())
