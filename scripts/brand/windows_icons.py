# SPDX-License-Identifier: AGPL-3.0-only
"""HST replacements for the upstream application icons that ship inside the product.

- Windows: one multi-size .ico per upstream sysui/desktop/icons/<name>.ico (soffice.exe,
  per-module launchers, taskbar, shortcuts, Programs and Features). Every size is rendered
  natively (no downscaling of one bitmap) so 16/24 px stay crisp.
- Icon themes: the window/Start Center icon res/mainapp_<size>[_8].{png,svg} of every theme,
  rendered as the HST product icon at 16/24/32/48 px; SVG themes get the same raster wrapped
  in an SVG (no upstream vector art).
scripts/brand/apply-icon-overrides.py copies these into a LibreOffice tree at build time.
"""
import io

from PIL import Image

from .app_icons import module_icon, product_icon
from .common import png_bytes, svg_with_raster


def _ico(images):
    """Multi-size ICO; Pillow stores each given image at its own size (largest as PNG)."""
    images = sorted(images, key=lambda im: im.width)
    buffer = io.BytesIO()
    images[-1].save(buffer, format="ICO", sizes=[im.size for im in images], append_images=images[:-1])
    return buffer.getvalue()


def build_windows_icons(spec, square):
    cfg = spec["windowsAppIcons"]
    geometry = spec["appIcons"]["geometry"]
    modules = {m["id"]: m for m in spec["appIcons"]["modules"] + cfg["extraModules"]}
    padding = spec["outputs"]["iconPadding"]
    outputs = {}
    for name, kind in sorted(cfg["icons"].items()):
        if kind == "product":
            images = [product_icon(square, s, padding) for s in cfg["sizes"]]
        else:
            images = [module_icon(square, s, modules[kind], geometry) for s in cfg["sizes"]]
        outputs[f"{cfg['dir']}/{name}"] = _ico(images)
    theme = spec["themeMainapp"]
    for size in theme["sizes"]:
        png = png_bytes(product_icon(square, size, padding))
        outputs[f"{theme['dir']}/mainapp-{size}.png"] = png
        big = png_bytes(product_icon(square, size * 4, padding))
        outputs[f"{theme['dir']}/mainapp-{size}.svg"] = svg_with_raster(big, size, size, "HST Office")
    return outputs
