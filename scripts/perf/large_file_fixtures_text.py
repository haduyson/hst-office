# SPDX-License-Identifier: AGPL-3.0-only
"""Plain-text fixtures of scripts/perf/large_file_fixtures.py: Vietnamese text opened in Writer.

Shapes that stress the text import differently: many short lines (one paragraph each), long lines, a few huge lines
(the import splits a line every ~250 000 characters), no line break at all, a UTF-8 byte order mark with CRLF line
ends, UTF-16LE with a byte order mark (what a "Unicode" save in a Windows editor writes) and a legacy single-byte
code page without any mark (encoding guessed from the first 4 KB)."""
import random

from large_file_fixture_words import sentence


def write_txt(path, megabytes, line_words, encoding="utf-8", bom=False, newline="\n"):
    """About <megabytes> MB (encoded) of lines of <line_words> words each."""
    rnd = random.Random(23)
    target = megabytes * 1_000_000
    with open(path, "wb") as f:
        if bom:
            f.write("﻿".encode(encoding if encoding != "utf-16-le" else "utf-16-le"))
        size, chunk = 0, []
        while size < target:
            data = (sentence(rnd, line_words) + "." + newline).encode(encoding, "replace")
            chunk.append(data)
            size += len(data)
            if len(chunk) >= 256:
                f.write(b"".join(chunk))
                chunk = []
        f.write(b"".join(chunk))


TEXT_JOBS = {
    "text-lines-10mb.txt": lambda p: write_txt(p, 10, 14),
    "text-longlines-10mb.txt": lambda p: write_txt(p, 10, 6000),  # ~60 KB paragraphs
    "text-oneline-10mb.txt": lambda p: write_txt(p, 10, 1_500_000),  # no line break at all
    "text-lines-50mb.txt": lambda p: write_txt(p, 50, 14),
    "text-short-50mb.txt": lambda p: write_txt(p, 50, 2),  # ~3 million very short paragraphs
    "text-hugelines-50mb.txt": lambda p: write_txt(p, 50, 1_000_000),  # 7 lines of ~7 MB
    "text-oneline-50mb.txt": lambda p: write_txt(p, 50, 8_000_000),
    "text-bom-crlf-50mb.txt": lambda p: write_txt(p, 50, 14, bom=True, newline="\r\n"),
    "text-utf16-50mb.txt": lambda p: write_txt(p, 50, 14, encoding="utf-16-le", bom=True, newline="\r\n"),
    "text-cp1258-50mb.txt": lambda p: write_txt(p, 50, 14, encoding="cp1258", newline="\r\n"),
}
