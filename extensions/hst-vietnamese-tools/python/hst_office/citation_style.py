# SPDX-License-Identifier: AGPL-3.0-only
"""Citation style registry: HST styles (JSON written by HST from the style manuals and university guides), the
user's own styles (an HST style plus changed options) and CSL files the user imported (a subset is understood).

Bundled styles live in <extension>/data/citation-styles/<id>.json (source tree: data/citation/styles/). The user's
styles live in <user profile>/hst-citations/styles/: ``<id>.json`` = {"id", "name", "basedOn", "preset", "options"}
and ``<id>.csl``. Pure Python (no uno).
"""
import json
import os
import re

from . import citation_style_check as check
from . import citation_style_options as style_options
from .citation_store import atomic_write
from .data_files import EXT_ROOT, REPO_ROOT

StyleError = check.StyleError
USER_PREFIX = "user-"
_CACHE = {}


def builtin_dirs():
    return [os.path.join(EXT_ROOT, "data", "citation-styles"), os.path.join(REPO_ROOT, "data", "citation", "styles")]


def user_styles_dir(user_dir):
    return os.path.join(user_dir, "hst-citations", "styles")


class Style:
    """A ready-to-use HST style: the file's layouts plus the merged options."""
    kind = "json"

    def __init__(self, data, options, warnings=()):
        self.data, self.options, self.warnings = data, options, list(warnings)
        self.id, self.name, self.cls = data["id"], data["name"], data["class"]
        self.terms = data.get("terms") or {}
        self.macros = data.get("macros") or {}

    def layout(self, item_type, note=False):
        table = self.data["notes"]["layouts"] if note else self.data["layouts"]
        alias = self.data.get("alias") or {}
        return table.get(item_type) or table.get(alias.get(item_type, ""), None) or table["default"]

    def short_note(self):
        return self.data["notes"]["short"]


def _read_json(path):
    key = (path, os.path.getmtime(path))
    if key not in _CACHE:
        with open(path, encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except ValueError as exc:
                raise StyleError("%s: không phải JSON hợp lệ (%s)" % (os.path.basename(path), exc)) from exc
        check.check_style(data, os.path.basename(path))
        _CACHE[key] = data
    return _CACHE[key]


def _builtin_path(style_id):
    if not re.match(r"^[a-z0-9-]+$", style_id or ""):
        return None
    for folder in builtin_dirs():
        path = os.path.join(folder, style_id + ".json")
        if os.path.isfile(path):
            return path
    return None


def builtin_ids():
    for folder in builtin_dirs():
        if os.path.isdir(folder):
            return sorted(name[:-5] for name in os.listdir(folder) if name.endswith(".json"))
    return []


def _user_entry(user_dir, style_id):
    if not user_dir or not re.match(r"^user-[a-z0-9-]+$", style_id or ""):
        return None
    for suffix in (".json", ".csl"):
        path = os.path.join(user_styles_dir(user_dir), style_id + suffix)
        if os.path.isfile(path):
            return path
    return None


def load_style(style_id, options=None, preset=None, user_dir=None):
    """The style ready for the engine; ``options`` (document settings) win over the preset, which wins over the
    style's defaults. Unknown or bad document options are skipped and listed in ``style.warnings``."""
    path = _builtin_path(style_id)
    if path:
        data = _read_json(path)
        chosen = next((p["options"] for p in data.get("presets", []) if p["id"] == preset), {}) if preset else {}
        merged, warnings = style_options.merge(data["options"], chosen, options)
        return Style(data, merged, warnings)
    path = _user_entry(user_dir, style_id)
    if path and path.endswith(".csl"):
        from . import citation_csl_style
        return citation_csl_style.load(path, style_id, options)
    if path:
        with open(path, encoding="utf-8") as handle:
            own = json.load(handle)
        base = load_style(own.get("basedOn", ""), own.get("options"), own.get("preset"))
        merged, warnings = style_options.merge(base.options, options)
        style = Style(base.data, merged, base.warnings + warnings)
        style.id, style.name = style_id, own.get("name") or style.name
        return style
    raise StyleError("không có kiểu trích dẫn: %s" % style_id)


def list_styles(user_dir=None):
    """[{"id", "name", "class", "presets": [{"id", "name"}], "user": bool, "kind": "json"|"csl"}] for dialogs."""
    result = []
    for style_id in builtin_ids():
        data = _read_json(_builtin_path(style_id))
        result.append({"id": style_id, "name": data["name"], "class": data["class"], "user": False, "kind": "json",
                       "presets": [{"id": p["id"], "name": p["name"]} for p in data.get("presets", [])]})
    folder = user_styles_dir(user_dir) if user_dir else None
    for name in sorted(os.listdir(folder)) if folder and os.path.isdir(folder) else []:
        style_id, suffix = os.path.splitext(name)
        if suffix not in (".json", ".csl") or not style_id.startswith(USER_PREFIX):
            continue
        try:
            style = load_style(style_id, user_dir=user_dir)
        except (StyleError, ValueError, OSError):
            continue  # a broken file never hides the other styles
        result.append({"id": style_id, "name": style.name, "class": style.cls, "presets": [], "user": True,
                       "kind": style.kind})
    return result


def new_user_id(name):
    from .vietnamese_text import remove_diacritics
    slug = re.sub(r"[^a-z0-9]+", "-", remove_diacritics(name).lower()).strip("-")[:40] or "kieu"
    return USER_PREFIX + slug


def save_user_style(user_dir, name, based_on, options, preset=None):
    """Save "my style" (an HST style with changed options); returns its id. Options are checked strictly."""
    if not _builtin_path(based_on):
        raise StyleError("kiểu gốc không có: %s" % based_on)
    style_options.merge({}, options, strict=True)
    style_id = new_user_id(name)
    body = {"id": style_id, "name": name.strip(), "basedOn": based_on, "preset": preset, "options": options}
    atomic_write(os.path.join(user_styles_dir(user_dir), style_id + ".json"),
                 json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8"))
    return style_id


def delete_user_style(user_dir, style_id):
    path = _user_entry(user_dir, style_id)
    if path:
        os.remove(path)
    return bool(path)
