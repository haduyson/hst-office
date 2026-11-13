# SPDX-License-Identifier: AGPL-3.0-only
"""The file's own default of number and money reading (Sheets): user-defined document properties (Tệp tin ▸ Thuộc
tính ▸ Thuộc tính tùy chọn), saved in .ods (meta:user-defined) and .xlsx (docProps/custom.xml) alike.
  * money (DOCTIEN): HST.DocTien.DonVi, HST.DocTien.DonViLe, HST.DocTien.CachDoc (option text, e.g. "ngàn linh");
  * numbers (DOCSO): HST.DocSo.CachDoc.
It is the "file" layer of number_words_defaults: the dialog opens with it, and DOCSO()/DOCTIEN() use it for an
argument left out. Set from the dialog ("Dùng làm mặc định cho tệp này"), one group (money or numbers) at a time."""
from . import diag_log
from .number_words_defaults import valid_entries

PROPERTIES = {"unit": "HST.DocTien.DonVi", "sub_unit": "HST.DocTien.DonViLe", "money_options": "HST.DocTien.CachDoc",
              "number_options": "HST.DocSo.CachDoc"}
GROUPS = {True: ("unit", "sub_unit", "money_options"), False: ("number_options",)}
REMOVEABLE = 128  # com.sun.star.beans.PropertyAttribute.REMOVEABLE: the user can delete it in the file's properties


def group(money, values):
    """The entries of one group (money or numbers) taken from complete dialog values."""
    return {key: values[key] for key in GROUPS[money]}


def has_group(layer, money):
    return any(key in layer for key in GROUPS[money])


def matches(layer, money, values):
    """True when the file has a default for this group and `values` equal it."""
    return has_group(layer, money) and all(layer.get(key, values[key]) == values[key] for key in GROUPS[money])


def with_group(layer, money, entries):
    """The layer once `entries` (or None: remove) become the file's default for this group. Pure."""
    kept = {key: value for key, value in layer.items() if key not in GROUPS[money]}
    return valid_entries(dict(kept, **(entries or {})))


def _properties(doc):
    return doc.getDocumentProperties().getUserDefinedProperties()


def read(doc):
    """The file layer: the valid entries among the properties ({} without a document or a default)."""
    if doc is None:
        return {}
    try:
        props = _properties(doc)
        info = props.getPropertySetInfo()
        raw = {key: props.getPropertyValue(name) for key, name in PROPERTIES.items() if info.hasPropertyByName(name)}
        return valid_entries(raw)
    except Exception:  # noqa: BLE001 - a document without user-defined properties has no default
        diag_log.exception("number_words")
        return {}


def store(doc, money, entries):
    """Make `entries` the file's default for one group, or remove that group (None). Writes only what changes, so
    confirming the same default leaves the document unmodified. Returns True when something changed, False when
    nothing did, None when it failed (read-only document, a property of the same name with another type)."""
    try:
        before = read(doc)
        after = with_group(before, money, entries)
        if after == before:
            return False
        props = _properties(doc)
        info = props.getPropertySetInfo()
        for key in GROUPS[money]:
            name = PROPERTIES[key]
            if key not in after:
                if info.hasPropertyByName(name):
                    props.removeProperty(name)
            elif info.hasPropertyByName(name):
                props.setPropertyValue(name, after[key])
            else:
                props.addProperty(name, REMOVEABLE, after[key])
        doc.setModified(True)
        return True
    except Exception:  # noqa: BLE001 - see the docstring
        diag_log.exception("number_words")
        return None
