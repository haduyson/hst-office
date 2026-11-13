# SPDX-License-Identifier: AGPL-3.0-only
"""The two online buttons of the source form (UNO glue around citation_lookup); nothing else calls the network.

"Tra cứu" sends the identifier the user typed (DOI, ISBN, PubMed ID or arXiv ID) to the matching service;
"Tìm theo dòng đã dán" sends the pasted reference line (whitespace collapsed, first 500 characters) to Crossref.
Both run only when their button is clicked, through citation_lookup_http.py in its own process with a hard
deadline and the office's proxy setting (the same as the update check). The result only fills the form: the
library is written when the user saves the form (docs/PRIVACY.md). Administrators switch both off with
/org.hasontech.hstoffice.Citations/OnlineLookup = false (citations.xcs; lockable like every configuration key).
"""
from . import citation_ui as ui

CONFIG = "/org.hasontech.hstoffice.Citations"
KEY = CONFIG + "/OnlineLookup"
MAX_MATCHES = 3


def config(ctx):
    """citation_lookup.LookupConfig from the administrator's settings, the installed release and the proxy."""
    from .citation_lookup import LookupConfig
    from .office_proxy import proxy
    from .update_config import _node
    enabled, contact = True, None
    try:
        node = _node(ctx, CONFIG)
        enabled = bool(node.getPropertyValue("OnlineLookup"))
        contact = node.getPropertyValue("LookupContact") or None  # empty: HST's built-in project address
    except Exception:  # noqa: BLE001 - schema missing (development tree): lookups allowed, built-in contact
        pass
    try:
        from .update_fetch import release_info
        version = release_info()["release"]
    except Exception:  # noqa: BLE001 - unknown release: the User-Agent says 0
        version = "0"
    return LookupConfig(enabled=enabled, contact=contact, version=version, proxy=proxy(ctx))


def hints(texts, enabled):
    """(text beside "Tra cứu", text beside "Tìm theo dòng đã dán"): what each sends where, or that both are off."""
    t = texts["entry"]
    return (t["lookupHint"], t["lineHint"]) if enabled else (t["lookupOff"], t["lookupOff"])


def confirm_suggestions(ctx, peer, texts, items, suggestions):
    """Items with the suggestions applied when the user agrees (all or none, listed in the question)."""
    from . import citation_vn_fix
    if not suggestions:
        return items
    shown = "\n".join("- " + s["message"] for s in suggestions[:12])
    if ui.ask(ctx, peer, texts, texts["entry"]["fixNames"] % (len(suggestions), shown)):
        return citation_vn_fix.apply(items, suggestions)
    return items


def _guarded(ctx, peer, texts, call):
    """call(settings) with the administrator's switch checked first; failures are told, None is returned."""
    from .citation_lookup_ids import LookupFailure
    settings = config(ctx)
    if not settings.enabled:
        ui.inform(ctx, peer, texts, texts["entry"]["lookupOff"])
        return None
    try:
        return call(settings)
    except LookupFailure as exc:
        ui.inform(ctx, peer, texts, exc.message)
    except Exception as exc:  # noqa: BLE001 - a helper process that failed: say so, the form stays usable
        ui.inform(ctx, peer, texts, texts["common"]["error"] % exc)
    return None


def lookup(ctx, peer, texts, text):
    """The "Tra cứu" button: one item for the typed identifier, or None."""
    from . import citation_lookup
    found = _guarded(ctx, peer, texts, lambda settings: citation_lookup.lookup(
        text, settings, citation_lookup.http_transport()))
    if not found:
        return None
    items = confirm_suggestions(ctx, peer, texts, found["items"], found.get("suggestions"))
    return items[0] if items else None


def lookup_line(ctx, peer, texts, text):
    """The "Tìm theo dòng đã dán" button: the Crossref match the user picks for the pasted line, or None."""
    from . import citation_lookup, citation_vn_fix
    matches = _guarded(ctx, peer, texts, lambda settings: citation_lookup.lookup_reference(
        text, settings, citation_lookup.http_transport(), rows=MAX_MATCHES))
    if matches is None:
        return None
    if not matches:
        ui.inform(ctx, peer, texts, texts["entry"]["lineNone"])
        return None
    items = [item for item, _score in matches[:MAX_MATCHES]]
    shown = "\n".join("%d. %s" % (n, ui.short_label(item)) for n, item in enumerate(items, 1))
    labels = tuple(str(n) for n in range(1, len(items) + 1)) + (texts["common"]["cancel"],)
    picked = ui.choose(ctx, peer, texts["common"]["title"], texts["entry"]["linePick"] % shown, labels, 0)
    if not 0 <= picked < len(items):
        return None
    chosen = [items[picked]]
    return confirm_suggestions(ctx, peer, texts, chosen, citation_vn_fix.suggest(chosen))[0]
