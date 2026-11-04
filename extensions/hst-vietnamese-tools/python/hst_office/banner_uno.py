# SPDX-License-Identifier: AGPL-3.0-only
"""Registered XJob service: nonblocking JSON snapshots for the native ribbon, shared by every app."""
import base64
import json

import uno
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .banner_feed import BannerFeed, get_banners
from .data_files import load_data
from .update_config import _node
from .update_ui import proxy

SERVICE_NAME = "org.hst.office.BannerFeed"
_START_NAME = "org.hst.office.BannerStartup"
_FEEDS = {}


def feed_for_context(ctx):
    """Read UNO configuration on the main thread, never from the network worker."""
    paths = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    profile = uno.fileUrlToSystemPath(paths.substituteVariables("$(user)", True))
    if profile not in _FEEDS:
        try:
            override = _node(ctx, "/org.hasontech.hstoffice.Banners").getPropertyValue("FeedURL")
        except Exception:  # noqa: BLE001 - schema absent: use production endpoint
            override = ""
        _FEEDS[profile] = BannerFeed(profile, load_data("release.json")["release"], override, proxy(ctx))
    return _FEEDS[profile]


class BannerService(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return SERVICE_NAME

    def getSupportedServiceNames(self):
        return (SERVICE_NAME, "com.sun.star.task.Job")

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def execute(self, arguments):
        """execute((NamedValue('Scale', 1.5),)) -> UTF-8 JSON as UNO string; no UI/window/document access."""
        scale = next((a.Value for a in arguments if a.Name == "Scale"), 1)
        snapshot = get_banners(feed_for_context(self.ctx))
        items = []
        for banner in snapshot["items"]:
            blob = banner.image_bytes_for_scale(scale)
            items.append({"id": banner["id"], "name": banner["name"], "tagline": banner["tagline"],
                          "click_url_with_utm": banner["click_url_with_utm"],
                          "image_base64": base64.b64encode(blob).decode("ascii")})
        return json.dumps({"rotateSeconds": snapshot["rotateSeconds"], "items": items}, ensure_ascii=False)


class BannerStartup(BannerService):
    def getImplementationName(self):
        return _START_NAME

    def getSupportedServiceNames(self):
        return (_START_NAME, "com.sun.star.task.Job")

    def execute(self, arguments):
        try:
            feed_for_context(self.ctx).refresh_async()
        except Exception:  # noqa: BLE001 - startup must succeed even if a profile/config is unavailable
            print("HST banners: startup unavailable", flush=True)
        return None
