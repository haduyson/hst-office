# SPDX-License-Identifier: AGPL-3.0-only
"""What each document type really requires, read from tests/fixtures/templates/requirements.json, not assumed per module.

A template's requirements are its kind's settings with the template's own overrides; its writer blocks become a flat list
of [paragraph style, required text] pairs. A catalog id without an entry is a failure, never a silent pass.
"""
import re
from .odf import BASE, read_json
from .validation import require

PATH = BASE / "tests/fixtures/templates/requirements.json"


def load_requirements(catalog_ids, path=PATH):
    """The table, after checking it names exactly the generated catalog: a stale entry hides a renamed template."""
    table = read_json(path)
    stale = sorted(set(table["templates"]) - set(catalog_ids))
    require(not stale, "Requirements name templates missing from the catalog: " + ", ".join(stale))
    return table


def resolve(table, ident):
    entry = table["templates"].get(ident)
    require(entry is not None, "No requirements entry for template " + ident)
    kind = table["kinds"].get(entry["kind"])
    require(kind is not None, "Unknown requirements kind: " + entry["kind"])
    spec = {"marker": table["editMarker"], **kind, **{k: v for k, v in entry.items() if k not in ("kind", "expect")}}
    spec["expect"] = [pair for name in spec.get("blocks", []) for pair in table["blocks"][name]] + entry.get("expect", [])
    if "page" in spec:
        spec["page"] = table["pages"][spec["page"]]
    if "margins" in spec:
        spec["margins"] = table["margins"][spec["margins"]]
    return spec


def role(style_name):
    """The layout role of a paragraph style: identical formats share a style, variants get a numeric suffix (Body2)."""
    return re.sub(r"\d+$", "", style_name or "")


def check_paragraphs(paragraphs, spec, where):
    """`paragraphs` are (style, text) pairs; every required pair must appear, and no forbidden text anywhere."""
    for wanted_role, wanted_text in spec["expect"]:
        found = any(role(style) == wanted_role and wanted_text in text for style, text in paragraphs)
        require(found, f"{where} lacks {wanted_role} paragraph with {wanted_text!r}")
    whole = "\n".join(text for _, text in paragraphs)
    for text in spec.get("forbid", []):
        require(text not in whole, f"{where} must not contain {text!r}")
