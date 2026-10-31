# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese USB Token setup command. Registers installed drivers; never logs in."""
import os
from pathlib import Path

from .data_files import load_data, load_locale
from .usb_token_detect import detect, platform_name

_pending_restart = set()


def setup(ctx):
    from .usb_token_db import office_state, select_db, set_fallback, user_database
    from .usb_token_nss import register
    platform = platform_name()
    configured, current, initialized, nss = office_state(ctx)
    db, fallback = select_db(Path.home(), configured, platform, core_path=current)
    modules = detect(platform, os.environ.get("HST_USB_TOKEN_TEST_ROOT", "/"), Path.home())
    if not modules:
        return db, [], False
    user_database(db)
    if fallback:
        set_fallback(ctx, db)
    rows = register(db, modules)
    added = any(row["status"] == "added" for row in rows)
    # NSS caches loaded modules and its path at first use (including PDF export).
    # Do not shut down or reload NSS in a running office: it holds signing keys.
    if added and initialized:
        _pending_restart.add(str(db))
    restart = str(db) in _pending_restart
    if initialized and current and Path(current.removeprefix("sql:")).resolve() != db:
        restart = True
    if not (db / "cert9.db").exists() and not initialized:
        # The office ships NSS on macOS. Its initializer creates cert9/key4 with
        # an empty internal password; no Homebrew or token PIN is involved.
        from com.sun.star.xml.crypto.DigestID import SHA256
        nss.getDigestContext(SHA256, ())
        if not (db / "cert9.db").exists():
            raise OSError("Chưa tạo được kho chứng thư. Khởi động lại HST Office rồi chạy thiết lập lần nữa.")
    if not (db / "cert9.db").exists():
        # NSS already owns another DB. On restart CertDir makes core create this
        # new SQL DB with an empty password, reading the stanzas just written.
        restart = True
    return db, rows, restart


def result_text(strings, db, rows, restart):
    parts = [strings["database"].format(path=db)]
    if not rows:
        parts.append(strings["notFound"])
        parts.extend(load_data("pkcs11-modules.json")["driver_guidance"])
    else:
        parts.extend(strings[row["status"]].format(label=row["label"], path=row["path"])
                     + ("\n" + row["error"] if row["status"] == "error" else "") for row in rows)
        parts.append(strings["restart"] if restart else strings["next"])
        if any(row["status"] == "error" for row in rows):
            parts.append(strings["retry"])
    return "\n\n".join(parts)


def run(ctx, frame):
    from .dialogs import message_box
    strings = load_locale("vi")["usbToken"]
    peer = frame.getContainerWindow() if frame else None
    error = False
    if platform_name() == "windows":
        text = strings["windows"]
    else:
        try:
            text = result_text(strings, *setup(ctx))
        except Exception as exc:  # noqa: BLE001 - one dialog; never log vendor output
            text, error = strings["failed"].format(error=exc), True
    message_box(ctx, peer, strings["title"], text, error=error)
