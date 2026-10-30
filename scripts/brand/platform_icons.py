# SPDX-License-Identifier: AGPL-3.0-only
"""Windows .ico and macOS .icns containers for the product and every module (Pillow writers).

Every size inside a container is rendered from the 1024 px master by render_icon, so small sizes
use the tight crop. macOS: hst-office.icns is the app/volume icon; per-module .icns are provided
for document or helper bundles that want them.
"""
import io

from .app_icons import render_icon

ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def ico_bytes(spec, master, sizes):
    """Multi-size ICO; Pillow stores each given image at its own size (largest as PNG)."""
    images = [render_icon(spec, master, s) for s in sorted(sizes)]
    buffer = io.BytesIO()
    images[-1].save(buffer, format="ICO", sizes=[im.size for im in images], append_images=images[:-1])
    return buffer.getvalue()


def icns_bytes(spec, master):
    images = [render_icon(spec, master, s) for s in ICNS_SIZES]
    buffer = io.BytesIO()
    images[-1].save(buffer, format="ICNS", append_images=images[:-1])
    return buffer.getvalue()


def build_platform_icons(spec, masters):
    cfg = spec["platformIcons"]
    product = spec["appIcons"]["productName"]
    outputs = {cfg["ico"]: ico_bytes(spec, masters[product], cfg["icoSizes"])}
    for name, master in sorted(masters.items()):
        path = cfg["icns"] if name == product else cfg["icnsPattern"].format(name=name)
        outputs[path] = icns_bytes(spec, master)
    return outputs

