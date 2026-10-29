# SPDX-License-Identifier: AGPL-3.0-only
"""Pure (uno-free) logic of the HASON TECH welcome dialog: UTM links and the dialog content model.

All text comes from data/solutions.json, which is bundled in the package; nothing is fetched at run time.
"""
import re

# scheme://host[/path][?query][#fragment]; plain string handling (no network-capable imports in this package)
_URL = re.compile(r"^(https:/{2}[^/?#\s]+)([^?#\s]*)(?:\?([^#\s]*))?(#\S*)?$")
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign")


def build_utm_url(url, medium, utm):
    """Return `url` with utm_source/utm_medium/utm_campaign appended to its query.

    Works with or without an existing query and keeps the fragment. Any utm_source/medium/campaign already in
    the URL is replaced so a parameter never appears twice. Only absolute https URLs are accepted.
    """
    if medium not in utm["mediums"]:
        raise ValueError("unknown utm medium: %r" % (medium,))
    match = _URL.match(url)
    if not match:
        raise ValueError("only absolute https URLs are allowed: %r" % (url,))
    base, path, query, fragment = match.group(1), match.group(2), match.group(3) or "", match.group(4) or ""
    kept = [pair for pair in query.split("&") if pair and pair.split("=", 1)[0] not in UTM_KEYS]
    kept += ["utm_source=" + utm["source"], "utm_medium=" + medium, "utm_campaign=" + utm["campaign"]]
    return "%s%s?%s%s" % (base, path, "&".join(kept), fragment)


def display_url(url):
    """Short label for a link: host and path without scheme or trailing slash."""
    return re.sub(r"^https:/{2}", "", url.split("#", 1)[0].split("?", 1)[0]).rstrip("/")


def build_model(data, medium):
    """Dialog content model from the parsed solutions.json.

    Returns {"company": {...}, "solutions": [{name, tagline, description, url, note}], "services": str,
    "contact": {address, phone, email, website, website_label}}; every url already carries the UTM query.
    Raises KeyError/ValueError when the data file is malformed (never shows partial content silently).
    """
    company, utm = data["company"], data["utm"]
    solutions = []
    for item in data["solutions"]:
        solutions.append({"id": item["id"], "name": item["name"], "tagline": item["tagline"],
                          "description": item["description"], "note": item.get("note", ""),
                          "url": build_utm_url(item["url"], medium, utm), "label": display_url(item["url"])})
    if not solutions:
        raise ValueError("solutions.json lists no solutions")
    return {
        "company": {"name": company["name"], "slogan": company["slogan"], "intro": company["intro"]},
        "solutions": solutions,
        "services": " · ".join(data["services"]),
        "contact": {"address": company["address"], "phone": company["phone"], "email": company["email"],
                    "website": build_utm_url(company["website"], medium, utm), "website_label": display_url(company["website"])},
    }
