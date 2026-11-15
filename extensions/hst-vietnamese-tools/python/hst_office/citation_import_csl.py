# SPDX-License-Identifier: AGPL-3.0-only
"""CSL-JSON import: an array of items, one item, or an HST library file ({"schemaVersion", "items"}). Zotero,
Mendeley and doi.org write this format; it is also the format HST stores, so nothing is converted, only validated
by citation_model.normalize_item. Pure Python (no uno)."""
import json

from . import citation_model as model
from .citation_import_common import ImportResult
from .citation_text_io import ImportFailure

MAX_ITEMS = 20_000


def parse(text):
    """ImportResult of CSL-JSON text. Raises ImportFailure when the text is not JSON at all."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        line = getattr(exc, "lineno", None)
        raise ImportFailure("không phải JSON hợp lệ (%s)" % getattr(exc, "msg", exc), line) from exc
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        data = data["items"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ImportFailure("CSL-JSON phải là một mảng các mục")
    result = ImportResult(fmt="csl-json")
    if len(data) > MAX_ITEMS:
        result.warnings.append("Chỉ nhập %d mục đầu tiên" % MAX_ITEMS)
    for index, raw in enumerate(data[:MAX_ITEMS], 1):
        try:
            item, warnings = model.normalize_item(raw)
        except ValueError as exc:
            result.warnings.append("Mục %d: %s" % (index, exc))
            continue
        result.items.append(item)
        result.warnings += ["Mục %d: %s" % (index, text) for text in warnings]
    return result
