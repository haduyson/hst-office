# SPDX-License-Identifier: AGPL-3.0-only
"""Decode reference files before parsing: UTF-8 (with or without BOM) or UTF-16 with BOM, at most 10 MB.

A byte that is not valid UTF-8 is reported with its line number instead of being replaced silently (the same rule
as the CSV import), so a file saved in a legacy encoding is not imported with broken Vietnamese letters.
"""
import codecs
import unicodedata

MAX_BYTES = 10 * 1024 * 1024


class ImportFailure(ValueError):
    """A file that cannot be imported at all; ``line`` is 1-based when known."""

    def __init__(self, message, line=None):
        super().__init__(("Dòng %d: %s" % (line, message)) if line else message)
        self.line = line


def decode(data):
    """Text of a reference file (NFC, "\\n" line ends). Raises ImportFailure."""
    if not isinstance(data, (bytes, bytearray)):
        raise ImportFailure("dữ liệu nhập phải là byte")
    if len(data) > MAX_BYTES:
        raise ImportFailure("tệp lớn hơn 10 MB")
    if data.startswith(codecs.BOM_UTF8):
        encoding, body = "utf-8", bytes(data[3:])
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding, body = "utf-16", bytes(data)
    else:
        encoding, body = "utf-8", bytes(data)
    try:
        text = body.decode(encoding)
    except UnicodeDecodeError as exc:
        line = body[:exc.start].count(b"\n") + 1 if encoding == "utf-8" else None
        raise ImportFailure("tệp không phải UTF-8 (có byte không hợp lệ); hãy lưu lại tệp với mã UTF-8", line) from exc
    if "\x00" in text:
        raise ImportFailure("tệp chứa ký tự NUL (có thể là tệp nhị phân)")
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def read_file(path):
    """Decoded text of a file chosen by the user (size checked before reading)."""
    with open(path, "rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    return decode(data)
