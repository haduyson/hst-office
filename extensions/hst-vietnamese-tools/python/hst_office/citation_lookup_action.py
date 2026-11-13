# SPDX-License-Identifier: AGPL-3.0-only
"""The "Tra cứu trực tuyến" button of the source form (UNO glue around citation_lookup).

Only the identifier the user typed (DOI, ISBN, PubMed ID or arXiv ID) is sent, only when the button is clicked,
through citation_lookup_http.py in its own process with a hard deadline (docs/PRIVACY.md). Administrators switch it
off with /org.hasontech.hstoffice.Citations/LookupEnabled (citations.xcs). The "sửa tên Việt" suggestions of the
result are shown before they are applied. Returns an item or None.
"""
from . import citation_ui as ui

CONFIG = "/org.hasontech.hstoffice.Citations"


def config(ctx):
    """citation_lookup.LookupConfig from the administrator's settings and the installed release."""
    from .citation_lookup import LookupConfig
    from .update_config import _node
    enabled, contact = True, None
    try:
        node = _node(ctx, CONFIG)
        enabled = bool(node.getPropertyValue("LookupEnabled"))
        contact = node.getPropertyValue("LookupContact") or None  # empty: HST's built-in project address
    except Exception:  # noqa: BLE001 - schema missing (development tree): lookups allowed, built-in contact
        pass
    try:
        from .update_fetch import release_info
        version = release_info()["release"]
    except Exception:  # noqa: BLE001 - unknown release: the User-Agent says 0
        version = "0"
    return LookupConfig(enabled=enabled, contact=contact, version=version)


def confirm_suggestions(ctx, peer, texts, items, suggestions):
    """Items with the suggestions applied when the user agrees (all or none, listed in the question)."""
    from . import citation_vn_fix
    if not suggestions:
        return items
    shown = "\n".join("- " + s["message"] for s in suggestions[:12])
    if ui.ask(ctx, peer, texts, texts["entry"]["fixNames"] % (len(suggestions), shown)):
        return citation_vn_fix.apply(items, suggestions)
    return items


def lookup(ctx, peer, texts, text):
    from . import citation_lookup
    from .citation_lookup_ids import LookupFailure
    settings = config(ctx)
    if not settings.enabled:
        ui.inform(ctx, peer, texts, texts["entry"]["lookupOff"])
        return None
    try:
        found = citation_lookup.lookup(text, settings, citation_lookup.http_transport())
    except LookupFailure as exc:
        ui.inform(ctx, peer, texts, exc.message)
        return None
    except Exception as exc:  # noqa: BLE001 - a helper process that failed: say so, the form stays usable
        ui.inform(ctx, peer, texts, texts["common"]["error"] % exc)
        return None
    items = confirm_suggestions(ctx, peer, texts, found["items"], found.get("suggestions"))
    return items[0] if items else None
