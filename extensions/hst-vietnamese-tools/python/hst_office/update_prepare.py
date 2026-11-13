# SPDX-License-Identifier: AGPL-3.0-only
"""Worker-thread half of "Cập nhật ngay" (no uno): signed manifest -> installer for this OS -> verified file in the cache.

The manifest is fetched and its Ed25519 signature checked again at the click, so the SHA256 and size that gate the
installer always come from a signed manifest. A file left by "Để sau" is reused only after it passes the same check.
"""
import os
import platform

from . import update_fetch as fetch
from . import update_installer as installer
from . import update_linux_install as linux_install
from . import update_logic as logic
from .update_download import DownloadCancelled, RejectedDownload, download  # noqa: F401 - DownloadCancelled is re-exported


class PrepareError(Exception):
    """`code` is the key of the message in update_texts: err_network, err_verify, err_none, err_appimage_dir; or "uptodate"."""

    def __init__(self, code, detail=""):
        super().__init__("%s %s" % (code, detail))
        self.code = code


def prepare(info, proxy=None, progress=None, cancelled=None, environ=None, system=None, machine=None):
    """Returns {"release", "entry", "path"}; raises PrepareError / DownloadCancelled."""
    system, machine = system or platform.system(), machine or platform.machine()
    try:
        channels = fetch.fetch_channels(info, proxy, environ)
    except fetch.UpdateError as exc:
        raise PrepareError("err_network" if isinstance(exc, fetch.FetchError) else "err_verify", exc)
    release = logic.select_update(channels, info["release"], info["channel"])
    if release is None:
        raise PrepareError("uptodate")
    key = linux_install.install_platform(system, machine, environ)
    entry = installer.choose_installer(release, key)
    if entry is None:
        raise PrepareError("err_none")
    cache = installer.cache_dir(system, environ)
    if key == "linux-appimage":  # downloaded beside the AppImage, which the helper then replaces by one rename
        try:
            cache = linux_install.appimage_update_dir(environ)
        except ValueError as exc:
            raise PrepareError("err_appimage_dir", exc)
    path = installer.installer_path(cache, entry)
    installer.cleanup(cache, keep_name=entry["name"])
    if os.path.isfile(path):
        try:
            installer.verify_file(path, entry)
            return {"release": release, "entry": entry, "path": path}
        except installer.InstallerError:
            os.remove(path)  # damaged or replaced since "Để sau": download again
    url = fetch.manifest_url(info, environ)
    allow_test = url not in (logic.MANIFEST_URL, logic.LEGACY_MANIFEST_URL)
    try:
        download(entry, path, logic.user_agent(info["release"], system), proxy, progress, cancelled, allow_test)
    except fetch.UpdateError as exc:
        raise PrepareError("err_verify" if isinstance(exc, RejectedDownload) else "err_network", exc)
    return {"release": release, "entry": entry, "path": path}
