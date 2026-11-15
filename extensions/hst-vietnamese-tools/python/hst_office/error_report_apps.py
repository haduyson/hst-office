# SPDX-License-Identifier: AGPL-3.0-only
"""Names of the HST Office apps in error reports: a stable key for the server and the product name users read.

The key (payload "app") is what system.hasontech.vn accepts and groups by since 1.0.0-beta.5: writer, calc, impress,
draw, math, base, start, unknown. They are internal identifiers (the engine's module names) and are never shown as
the app's name: the dialog summary, systemInfo "App:", the crash text and the e-mail use the product name, which the
payload also carries as "appName". HST PDF has no key of its own on the server: it is sent as "unknown" with the
appName "HST PDF". Web, global and master documents are HST Writer documents.
"""

SERVER_KEYS = ("writer", "calc", "impress", "draw", "math", "base", "start", "unknown")
NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides", "draw": "HST Draw", "math": "HST Math",
         "base": "HST Base", "pdf": "HST PDF", "start": "Trang bắt đầu", "unknown": "Không rõ"}


def server_key(app):
    """The payload "app" value the server accepts for an app key."""
    return app if app in SERVER_KEYS else "unknown"


def app_name(app):
    """Product name of an app key ("calc" -> "HST Sheets"); unknown keys read "Không rõ", never the raw key."""
    return NAMES.get(app, NAMES["unknown"])
