# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic icon archives and directory sync for build-hst-icon-theme.py."""
import io
import zipfile


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def sync(directory, files, check=False):
    expected = set(files)
    existing = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    errors = []
    for name in sorted(existing - expected):
        if check:
            errors.append(f"unexpected: {directory / name}")
        else:
            (directory / name).unlink()
    for name, data in files.items():
        path = directory / name
        if path.is_file() and path.read_bytes() == data:
            continue
        if check:
            errors.append(f"missing or stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    if errors:
        raise ValueError("\n".join(errors))


# Notice shipped in every HST command icon archive (COPYING.txt).
COPYING = (
    "HST Ribbon Icons — HASON TECH, 2026, CC BY 4.0\n"
    "Copyright (c) 2026 Công ty TNHH Công nghệ Hà Sơn (HASON TECH).\n"
    "Command glyphs: original HST artwork, see LICENSE-CC-BY-4.0.txt, except the marks below.\n"
    "Source: https://github.com/haduyson/hst-office/tree/main/icon-themes-src/hst\n"
    "Licence: https://creativecommons.org/licenses/by/4.0/\n"
    "Changes: palette exports of the original masters, pixel-snapped per size (16/24/32 px,\n"
    "whole-pixel pens) with strokes painted as filled outlines; hand-tuned 16 px masters\n"
    "for the Home and quick-access glyphs (glyphs/stage-1-16).\n"
    "res/mainapp_*: existing HST Office application marks, copied unchanged from\n"
    "branding/icon-themes; these are HASON TECH trademarks, not CC BY glyphs.\n"
    "cmd/sc_showsolutions.svg, cmd/lc_showsolutions.svg, cmd/32/showsolutions.svg:\n"
    "the HASON TECH mark of res/mainapp_* in brand blue (branding/icon-themes/\n"
    "hasontech-mark.svg); a HASON TECH trademark, not a CC BY glyph.\n"
    "The artwork and source licences grant no trademark rights (see product NOTICE).\n"
    "Generator and mapping code: AGPL-3.0-only, in the source repository.\n"
)
