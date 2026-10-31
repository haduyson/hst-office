# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese USB Token setup command. Registers installed drivers; never logs in."""
import os
from pathlib import Path

from .data_files import load_data, load_locale
from .usb_token_detect import detect, platform_name
from .usb_token_errors import vietnamese_error

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
    rows = register(db, modules)
    added = any(row["status"] == "added" for row in rows)
    # NSS caches loaded modules and its path at first use (including PDF export).
    # Do not shut down or reload NSS in a running office: it holds signing keys.
    if added and initialized:
        _pending_restart.add(str(db))
    if any(row["status"] in ("added", "existing") for row in rows) and fallback:
        set_fallback(ctx, db)
    restart = str(db) in _pending_restart
    if any(row["status"] in ("added", "existing") for row in rows):
        # Never initialize or rewrite live SQL files during setup. Core creates
        # an empty SQL DB on restart if needed. A cached path also needs restart.
        if not (db / "cert9.db").exists() or not current or Path(current.removeprefix("sql:")).resolve() != db:
            restart = True
    if restart:
        _pending_restart.add(str(db))
    return db, rows, restart


def result_text(strings, db, rows, restart):
    parts = [strings["database"].format(path=db)]
    if not rows:
        parts.append(strings["notFound"])
        parts.extend(load_data("pkcs11-modules.json")["driver_guidance"])
    else:
        parts.extend(strings[row["status"]].format(label=row["label"], path=row["path"])
                     + ("\n" + row["error"] if row["status"] == "error" else "") for row in rows)
        if any(row["status"] != "error" for row in rows):
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
            text, error = strings["failed"].format(error=vietnamese_error(exc)), True
    message_box(ctx, peer, strings["title"], text, error=error)
