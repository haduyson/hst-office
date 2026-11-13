# SPDX-License-Identifier: AGPL-3.0-only
"""The citation style of a document: the user-defined document property HSTCitationStyle (UNO, plus pure checks).

Value: {"style": "vn-so", "preset": null, "opts": {...}} as compact JSON, at most 255 characters, so other word
processors keep it when they save the file again. A document without the property has no HST citations; the save
job uses that to do nothing for every other document.
"""
import json

PROPERTY = "HSTCitationStyle"
MAX_CHARS = 255
REMOVABLE = 128  # com.sun.star.beans.PropertyAttribute.REMOVABLE


class SettingsError(ValueError):
    pass


def default_settings(ui_language):
    """The style a new citation document starts with: the Vietnamese thesis style, APA 7 for an English UI."""
    return {"style": "vn-so" if ui_language == "vi" else "apa-7", "preset": None, "opts": {}}


def stored_options(chosen, base_options, keep_language=None):
    """The options to store: those that differ from the style and preset (plus a language the user had set)."""
    opts = {k: v for k, v in chosen.items() if base_options.get(k) != v}
    if keep_language:
        opts["language"] = keep_language
    return opts


def encode(settings):
    body = {"style": settings["style"], "preset": settings.get("preset") or None, "opts": settings.get("opts") or {}}
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_CHARS:
        raise SettingsError("thiết lập kiểu trích dẫn quá dài (tối đa %d ký tự)" % MAX_CHARS)
    return text


def decode(text):
    """Settings from the property text; None when missing or unreadable (the caller falls back to a default)."""
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(body, dict) or not isinstance(body.get("style"), str) or not body["style"]:
        return None
    opts = body.get("opts") if isinstance(body.get("opts"), dict) else {}
    preset = body.get("preset") if isinstance(body.get("preset"), str) else None
    return {"style": body["style"], "preset": preset, "opts": opts}


def _properties(doc):
    return doc.getDocumentProperties().getUserDefinedProperties()


def read(doc):
    """The document's settings, or None when it has none."""
    props = _properties(doc)
    if not props.getPropertySetInfo().hasPropertyByName(PROPERTY):
        return None
    return decode(props.getPropertyValue(PROPERTY))


def write(doc, settings):
    text = encode(settings)
    props = _properties(doc)
    if props.getPropertySetInfo().hasPropertyByName(PROPERTY):
        props.setPropertyValue(PROPERTY, text)
    else:
        props.addProperty(PROPERTY, REMOVABLE, text)
