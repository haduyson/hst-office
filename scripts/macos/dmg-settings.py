# SPDX-License-Identifier: AGPL-3.0-only
# dmgbuild settings for the HST Office disk image (executed by `python -m dmgbuild -s`).
# Defines: -D app=<path to "HST Office.app"> -D repo=<repository root>.
# Replaces upstream's dmg layout (setup_native/source/packinfo/osxdndinstall.png and the binary
# DS_Store whose icon positions name "LibreOffice.app"): HST background with Vietnamese text,
# HST volume icon, app + Applications link at the positions drawn on the background.
# No licence (SLA) dialog: upstream's Rez/`hdiutil unflatten` path is inert on current macOS too.
# pylint: disable=undefined-variable  # `defines` is injected by dmgbuild
import os.path

application = defines["app"]  # noqa: F821
repo = defines["repo"]  # noqa: F821
appname = os.path.basename(application)

format = "ULFO"  # lzfse, as upstream (tdf#151341)
filesystem = "HFS+"
files = [application]
symlinks = {"Applications": "/Applications"}
icon = os.path.join(repo, "branding", "macos", "hst-office.icns")
# dmgbuild combines this with dmg-background@2x.png into a HiDPI TIFF (tiffutil).
background = os.path.join(repo, "branding", "macos", "dmg-background.png")
window_rect = ((200, 120), (550, 442))
default_view = "icon-view"
show_icon_preview = False
icon_size = 96
text_size = 13
# Keep in sync with APP_POS / APPLICATIONS_POS in scripts/macos/make-dmg-background.py.
icon_locations = {appname: (140, 205), "Applications": (410, 205)}
