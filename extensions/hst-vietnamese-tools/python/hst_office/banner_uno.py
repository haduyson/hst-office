# SPDX-License-Identifier: AGPL-3.0-only
"""Registered XJob service: nonblocking JSON snapshots for the native ribbon, shared by every app."""
import uno
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .banner_click import destination
from .banner_feed import BannerFeed, get_banners, test_mode_from_release
from .banner_snapshot import selected_json
from .data_files import load_data
from .update_config import _node, proxy

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
        release = load_data("release.json")
        # The test feed URL/key environment is honoured only by test-stamped packages.
        _FEEDS[profile] = BannerFeed(profile, release["release"], override, proxy(ctx),
                                     test_mode=test_mode_from_release(release))
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
        """Scale/Slot[/Compact] -> bounded JSON for one weighted slot, ClickUrl -> URL to open; no UI/window/document
        access. Compact=True selects the compact art of narrow windows (slotCount 0: hide the slot)."""
        click = next((a.Value for a in arguments if a.Name == "ClickUrl"), None)
        if click is not None:  # called by the widget's worker thread, after a user click only
            feed = feed_for_context(self.ctx)
            return destination(click, feed.utm, feed.version, feed.proxy)
        scale = next((a.Value for a in arguments if a.Name == "Scale"), 1)
        slot = next((a.Value for a in arguments if a.Name == "Slot"), 0)
        compact = next((a.Value for a in arguments if a.Name == "Compact"), False) is True
        snapshot = get_banners(feed_for_context(self.ctx), compact)
        return selected_json(snapshot, scale, slot, compact)


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
