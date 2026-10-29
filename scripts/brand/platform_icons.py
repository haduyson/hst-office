# SPDX-License-Identifier: AGPL-3.0-only
"""Windows .ico and macOS .icns containers built with Pillow (not tested on their OS)."""
import io

from PIL import Image


def _encode(image, fmt, **kwargs):
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def build_platform_icons(spec, square):
    cfg = spec["platformIcons"]
    base = square.resize((1024, 1024), Image.LANCZOS)
    ico_sizes = cfg["icoSizes"]
    ico = _encode(base, "ICO", sizes=[(s, s) for s in ico_sizes])
    icns = _encode(base, "ICNS")
    return {cfg["ico"]: ico, cfg["icns"]: icns}
