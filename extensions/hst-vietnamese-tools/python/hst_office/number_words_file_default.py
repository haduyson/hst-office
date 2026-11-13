# SPDX-License-Identifier: AGPL-3.0-only
"""The file's own default money unit of "Đọc số thành chữ" (Sheets): two user-defined document properties,
HST.DocTien.DonVi and HST.DocTien.DonViLe (File ▸ Properties ▸ Custom Properties). They are saved in .ods
(meta:user-defined) and .xlsx (docProps/custom.xml) alike, so the file carries its default to every HST Office.

The property only pre-fills the dialog: a formula written by the dialog spells out its unit whenever it is not
the program default, so DOCTIEN() never depends on the property and the cell reads the same everywhere. It is the
"file" layer of number_words_defaults.resolve() (unit_layer turns the pair into one)."""
from . import diag_log
from .number_words_defaults import clean_unit

UNIT, SUB_UNIT = "HST.DocTien.DonVi", "HST.DocTien.DonViLe"
REMOVEABLE = 128  # com.sun.star.beans.PropertyAttribute.REMOVEABLE: the user can delete it in File ▸ Properties


def _properties(doc):
    return doc.getDocumentProperties().getUserDefinedProperties()


def _get(props, name):
    return props.getPropertyValue(name) if props.getPropertySetInfo().hasPropertyByName(name) else None


def parse(unit, sub_unit):
    """(unit, sub-unit) from the stored values, or None when the file has no usable default."""
    unit = clean_unit(unit, "")
    return (unit, clean_unit(sub_unit, "")) if unit else None


def read(doc):
    """The file's (unit, sub-unit), or None (no default, or the document has no properties)."""
    try:
        props = _properties(doc)
        return parse(_get(props, UNIT), _get(props, SUB_UNIT))
    except Exception:  # noqa: BLE001 - a document without user-defined properties has no default
        diag_log.exception("number_words")
        return None


def _set(props, name, value):
    if props.getPropertySetInfo().hasPropertyByName(name):
        props.setPropertyValue(name, value)
    else:
        props.addProperty(name, REMOVEABLE, value)


def store(doc, default):
    """Make `default` (unit, sub-unit) the file's default, or remove it when `default` is None. Writes only what
    changes, so confirming the same default does not mark the document modified. Returns False if it failed."""
    try:
        if default == read(doc):
            return True
        props = _properties(doc)
        if default is None:
            for name in (UNIT, SUB_UNIT):
                if props.getPropertySetInfo().hasPropertyByName(name):
                    props.removeProperty(name)
        else:
            _set(props, UNIT, default[0])
            _set(props, SUB_UNIT, default[1])
        doc.setModified(True)
        return True
    except Exception:  # noqa: BLE001 - read-only document or a property of another type with the same name
        diag_log.exception("number_words")
        return False
