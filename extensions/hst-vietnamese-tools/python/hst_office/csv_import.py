# SPDX-License-Identifier: AGPL-3.0-only
"""Safe CSV decoding and parsing for the Calc import helper (pure logic, no `uno`).

Limits and the text-by-default policy come from data/vietnamese/number-formats.json ("csv"). Nothing is
repaired silently: malformed UTF-8, ragged quoting, NUL bytes, oversize input or too many rows/columns raise
CsvError and the caller writes nothing. Values are never evaluated; formula-looking text stays literal text.
"""
import csv
import io
import re

from .data_files import load_data

MAX_CELL_CHARS = 32767
_NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,14})(?:\.\d{1,15})?")


class CsvError(ValueError):
    """Raised with a machine-readable .code: too-large, invalid-utf8, unsupported-encoding, nul-byte, malformed,
    too-many-rows, too-many-columns, cell-too-long, bad-delimiter, empty."""

    def __init__(self, code, detail=""):
        super().__init__("%s%s" % (code, ": " + detail if detail else ""))
        self.code, self.detail = code, detail


def limits(data=None):
    return (data or load_data("number-formats.json"))["csv"]["limits"]


def decode_bytes(raw, data=None):
    """Strict UTF-8 with or without BOM. Returns (text, had_bom)."""
    if len(raw) > limits(data)["maxBytes"]:
        raise CsvError("too-large", "%d bytes" % len(raw))
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise CsvError("unsupported-encoding", "UTF-16 BOM; re-save the file as UTF-8")
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw[3 if bom else 0:].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CsvError("invalid-utf8", "byte offset %d" % (exc.start + (3 if bom else 0))) from exc
    if "\x00" in text:
        raise CsvError("nul-byte")
    return text, bom


def suggest_delimiter(text, data=None):
    """Advice only: the candidate delimiter with the most consistent per-line count in the first 20 lines."""
    candidates = (data or load_data("number-formats.json"))["csv"]["delimiters"]
    head = [line for line in text.splitlines()[:20] if line.strip()]
    best, best_score = candidates[0], -1
    for d in candidates:
        counts = [line.count(d) for line in head]
        score = counts[0] * len(counts) if counts and counts[0] and len(set(counts)) == 1 else (sum(1 for c in counts if c) if counts else 0)
        if score > best_score:
            best, best_score = d, score
    return best


def parse(text, delimiter, data=None):
    """Parse into a rectangular list of rows of str. Embedded newlines/quotes/empty fields are preserved."""
    lim = limits(data)
    if delimiter not in (data or load_data("number-formats.json"))["csv"]["delimiters"]:
        raise CsvError("bad-delimiter", repr(delimiter))
    csv.field_size_limit(MAX_CELL_CHARS + 1)
    rows, width = [], 0
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar='"', strict=True):
            if len(rows) >= lim["maxRows"]:
                raise CsvError("too-many-rows", str(lim["maxRows"]))
            if len(row) > lim["maxColumns"]:
                raise CsvError("too-many-columns", str(lim["maxColumns"]))
            if any(len(cell) > MAX_CELL_CHARS for cell in row):
                raise CsvError("cell-too-long", str(MAX_CELL_CHARS))
            rows.append(row)
            width = max(width, len(row))
    except csv.Error as exc:
        raise CsvError("malformed", "row %d: %s" % (len(rows) + 1, exc)) from exc
    if not rows:
        raise CsvError("empty")
    return [row + [""] * (width - len(row)) for row in rows]


def typed_cell(value, mode="text"):
    """('s', str) or ('n', float). Default mode 'text' keeps everything literal (00123, =1+1, +84..., -x, @a).
    Mode 'general' converts only plain decimals without leading zeros or plus sign; formula-like text stays text."""
    if mode == "general" and _NUMBER.fullmatch(value):
        return "n", float(value)
    if mode not in ("text", "general"):
        raise ValueError("unknown-mode")
    return "s", value


def preview(rows, count=10):
    return rows[:count]
