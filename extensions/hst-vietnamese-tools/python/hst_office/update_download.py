# SPDX-License-Identifier: AGPL-3.0-only
"""Installer download of "Cập nhật ngay": the second module allowed to use the network (with update_fetch).

Runs on a worker thread, only after the user clicked "Cập nhật ngay". HTTPS to the URL the signed manifest names
(hasontech.vn or the project's GitHub release assets); redirects only to the release-asset hosts; the stream stops as
soon as it exceeds the size the manifest announced; the file is written as <name>.part, fully verified (size and SHA256
from the signed manifest) and only then renamed, so a complete-looking installer in the cache is always a verified one.
"""
import os
import urllib.error
import urllib.request
import uuid

from . import update_installer as installer
from . import update_logic as logic
from .update_fetch import UpdateError, tls_context

CHUNK = 256 * 1024
READ_TIMEOUT = 30


class RejectedDownload(UpdateError):
    """The bytes or the URL are not acceptable (refused URL, wrong size, wrong SHA256): never a connectivity problem."""


class DownloadCancelled(Exception):
    """The user pressed Cancel."""


class _AllowedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_test):
        self.allow_test = allow_test

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not installer.is_redirect_allowed(newurl, self.allow_test):
            raise urllib.error.HTTPError(newurl, code, "redirect to a foreign host refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(proxy, allow_test):
    handlers = [_AllowedRedirect(allow_test), urllib.request.HTTPSHandler(context=tls_context())]
    if proxy is not None:
        handlers.append(urllib.request.ProxyHandler(proxy))
    return urllib.request.build_opener(*handlers)


def download(entry, dest, agent, proxy=None, progress=None, cancelled=None, allow_test=False):
    """Fetch entry["url"] into `dest` (verified); raises UpdateError / DownloadCancelled, leaves no partial file."""
    if not installer.is_installer_url(entry["url"], allow_test):
        raise RejectedDownload("refused installer URL")
    total, part = entry["size"], "%s.%s.part" % (dest, uuid.uuid4().hex[:8])  # unique: a cancelled attempt never touches a retry
    request = urllib.request.Request(entry["url"], headers={"User-Agent": agent, "Accept": "*/*"})
    done = 0
    try:
        os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
        with _opener(proxy, allow_test).open(request, timeout=READ_TIMEOUT) as response, open(part, "wb") as out:
            if not installer.is_redirect_allowed(response.geturl(), allow_test):
                raise RejectedDownload("final URL refused")
            while True:
                if cancelled and cancelled():
                    raise DownloadCancelled()
                block = response.read(CHUNK)
                if not block:
                    break
                done += len(block)
                if done > total:
                    raise RejectedDownload("download larger than announced")
                out.write(block)
                if progress:
                    progress(done, total)
        installer.verify_file(part, entry)
        os.replace(part, dest)
    except (UpdateError, DownloadCancelled):  # RejectedDownload is an UpdateError
        _remove(part)
        raise
    except installer.InstallerError as exc:
        _remove(part)
        raise RejectedDownload("installer rejected: %s" % exc)
    except Exception as exc:  # noqa: BLE001 - network, disk full, TLS, HTTP status: all "download failed"
        _remove(part)
        raise UpdateError("%s: %s" % (type(exc).__name__, exc))


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
