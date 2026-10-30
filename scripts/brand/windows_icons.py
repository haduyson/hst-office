# SPDX-License-Identifier: AGPL-3.0-only
"""HST replacements for the upstream application icons that ship inside the product.

- Windows: one multi-size .ico per upstream sysui/desktop/icons/<name>.ico (soffice.exe,
  per-module launchers, taskbar, shortcuts, Programs and Features). Every size is rendered
  from the module's 1024 px master (tight crop at small sizes), so 16/24 px stay crisp.
- Icon themes: the window/Start Center icon res/mainapp_<size>[_8].{png,svg} of every theme,
  rendered as the HST Office tile at 16/24/32/48 px; SVG themes get a 4x raster of the same
  tile wrapped in an SVG.
scripts/brand/apply-icon-overrides.py copies these into a LibreOffice tree at build time.
"""
from .app_icons import module_names, render_icon
from .common import png_bytes, svg_with_raster
from .platform_icons import ico_bytes


def build_windows_icons(spec, masters):
    cfg = spec["windowsAppIcons"]
    names = module_names(spec)
    outputs = {}
    for name, kind in sorted(cfg["icons"].items()):
        outputs[f"{cfg['dir']}/{name}"] = ico_bytes(spec, masters[names[kind]], cfg["sizes"])
    product = masters[names["product"]]
    theme = spec["themeMainapp"]
    for size in theme["sizes"]:
        outputs[f"{theme['dir']}/mainapp-{size}.png"] = png_bytes(render_icon(spec, product, size))
        big = png_bytes(render_icon(spec, product, size * 4))
        outputs[f"{theme['dir']}/mainapp-{size}.svg"] = svg_with_raster(big, size, size, "HST Office")
    return outputs
