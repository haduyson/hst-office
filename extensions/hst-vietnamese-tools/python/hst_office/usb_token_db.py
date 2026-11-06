# SPDX-License-Identifier: AGPL-3.0-only
"""Select the user's NSS SQL database, following NSSInitializer/MozillaBootstrap."""
import configparser
import os
from pathlib import Path

from .usb_token_errors import SetupError

CONFIG = "/org.openoffice.Office.Common/Security/Scripting"
ROOTS = (
    ("MOZILLA_THUNDERBIRD_PROFILE_ROOT", (".thunderbird", ".mozilla-thunderbird", ".mozilla/thunderbird", ".icedove",
                                       "snap/thunderbird/common/.thunderbird", ".var/app/org.mozilla.Thunderbird/.thunderbird")),
    ("MOZILLA_FIREFOX_PROFILE_ROOT", (".mozilla/firefox", "snap/firefox/common/.mozilla/firefox",
                                    ".var/app/org.mozilla.firefox/.mozilla/firefox")),
    ("MOZILLA_PROFILE_ROOT", (".mozilla/seamonkey",)),
)
MAC_ROOTS = ("Library/Thunderbird", "Library/Application Support/Firefox", "Library/Mozilla/SeaMonkey")


def profile_in(root):
    parser = configparser.RawConfigParser(strict=False)
    parser.read(Path(root) / "profiles.ini", encoding="utf-8")
    profiles, default = {}, ""
    # Core's IniSectionMap is sorted, and default-release wins even over Default=1.
    for section in sorted(parser.sections()):
        values = parser[section]
        name, path = values.get("name", ""), values.get("path", "")
        if not name and not path:
            continue
        profiles[name] = Path(root) / path if values.get("isrelative") == "1" else Path(path)
        if values.get("default") == "1":
            default = name
        if name == "default-release":
            default = name
            break
    return profiles.get(default or min(profiles, default=""))


def normalize(value):
    if value.startswith("dbm:"):
        raise SetupError("Kho NSS cũ (dbm) chưa được hỗ trợ. Hãy chọn kho NSS SQL trong Bảo mật → Chứng chỉ")
    path = Path(value)
    if not path.is_absolute():
        raise SetupError("Đường dẫn kho chứng thư phải là đường dẫn tuyệt đối.")
    return path.resolve()


def select_db(home, configured="", platform="linux", env=None, core_path=""):
    env = os.environ if env is None else env
    home = Path(home)
    # NSSPath is already selected/cached by core, even before NSS initializes.
    if core_path:
        return normalize(core_path.removeprefix("sql:")), False
    value = env.get("MOZILLA_CERTIFICATE_FOLDER", "")
    if value:
        return normalize(value.removeprefix("sql:")), False
    # Core accepts an existing filesystem directory, not sql: or shell syntax.
    if configured and Path(configured).is_absolute() and Path(configured).is_dir():
        return normalize(configured), False
    for index, (variable, roots) in enumerate(ROOTS):
        if platform == "macos":
            roots = (MAC_ROOTS[index],)
        candidates = [Path(env[variable])] if env.get(variable) else [home / r for r in roots]
        for root in candidates:
            if (root / "profiles.ini").is_file():
                profile = profile_in(root)
                if profile:
                    return normalize(str(profile)), False
                break  # core uses only the first registry per product
    return home / ".pki/nssdb", True


def user_database(path, create=True):
    """Only a SQL DB owned by this user; never migrate or modify another user's DB."""
    if os.geteuid() == 0:
        raise SetupError("Hãy chạy HST Office bằng tài khoản người dùng thông thường.")
    if (path / "secmod.db").exists() or ((path / "cert8.db").exists() and not (path / "cert9.db").exists()):
        raise SetupError("Kho chứng thư dùng định dạng NSS cũ. Hãy chọn kho NSS SQL trong Bảo mật → Chứng chỉ")
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    if ancestor.stat().st_uid != os.geteuid():
        raise SetupError("Kho chứng thư phải thuộc tài khoản đang sử dụng.")
    for name in ("cert9.db", "key4.db", "secmod.db", "pkcs11.txt", ".hst-usb-token.lock"):
        item = path / name
        if item.is_symlink() or (item.exists() and item.stat().st_uid != os.geteuid()):
            raise SetupError("Tệp trong kho chứng thư không thuộc tài khoản đang sử dụng hoặc là liên kết.")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)


def office_state(ctx):
    from .ui_language import _node
    configured = _node(ctx, CONFIG).getPropertyValue("CertDir") or ""
    nss = ctx.ServiceManager.createInstanceWithContext("com.sun.star.xml.crypto.NSSInitializer", ctx)
    return configured, nss.NSSPath, nss.IsNSSinitialized, nss


def set_fallback(ctx, path):
    # The core's ~/.pki/nssdb fallback is Linux-only. Persist CertDir on macOS too.
    from .ui_language import _node
    node = _node(ctx, CONFIG, True)
    node.setPropertyValue("CertDir", str(path))
    node.commitChanges()
