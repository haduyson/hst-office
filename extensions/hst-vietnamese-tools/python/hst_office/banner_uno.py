# SPDX-License-Identifier: AGPL-3.0-only
"""Registered XJob service: nonblocking JSON snapshots for the native ribbon, shared by every app."""
import uno
import unohelper
from com.sun.star.frame import XTerminateListener
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .banner_click import destination
from .banner_feed import BannerFeed, get_banners, test_mode_from_release
from .banner_snapshot import selected_json
from .data_files import load_data
from .office_proxy import proxy
from . import update_config
from .update_config import _node
from .update_install_id import SEND_KEY, current

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
        sending = _send_install_id(ctx)
        # The test feed URL/key environment is honoured only by test-stamped packages.
        _FEEDS[profile] = BannerFeed(profile, release["release"], override, proxy(ctx),
                                     test_mode=test_mode_from_release(release),
                                     impressions_allowed=lambda: current(sending) is True)
        _flush_on_exit(ctx, _FEEDS[profile])
    return _FEEDS[profile]


def _send_install_id(ctx):
    """SendInstallId as resolved for the update check (administrator locks included); False when unreadable.
    Display counts follow it: unticking the box in this session stops them at once (update_install_id.current);
    ticking it again takes effect at the next start at the latest."""
    try:
        return update_config.settings(ctx).get(SEND_KEY, True) is True
    except Exception:  # noqa: BLE001 - no settings: count nothing
        return False


class _FlushOnExit(unohelper.Base, XTerminateListener):
    """Writes the display counts of this session when the office terminates (one small atomic file)."""

    def __init__(self, feed):
        self.feed = feed

    def queryTermination(self, event):
        pass

    def notifyTermination(self, event):
        self.feed.impressions.flush()  # never raises

    def disposing(self, event):
        pass


def _flush_on_exit(ctx, feed):
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        desktop.addTerminateListener(_FlushOnExit(feed))
    except Exception:  # noqa: BLE001 - without it, at most the last 60 seconds of counts are lost
        pass


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
        """Scale/Slot[/Compact] -> bounded JSON for one weighted slot, ClickUrl -> URL to open, Shown -> "" after
        counting one display of that banner id; no UI/window/document access. Compact=True selects the compact
        art of narrow windows (slotCount 0: hide the slot)."""
        shown = next((a.Value for a in arguments if a.Name == "Shown"), None)
        if shown is not None:  # widget worker thread: a card stood one second in a visible window
            feed_for_context(self.ctx).shown(shown)
            return ""
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
