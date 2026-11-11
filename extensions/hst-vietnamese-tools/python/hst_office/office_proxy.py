# SPDX-License-Identifier: AGPL-3.0-only
"""The office's proxy setting for HST's HTTPS requests (update check, banner feed).

A module of its own so the banner start-up job, which runs as the first window appears, reads the setting without
importing update_ui and the network modules it pulls in.
"""
from .update_config import _node


def proxy(ctx):
    """Proxy from Tools > Options > Internet > Proxy: None = system/environment, {} = none, else manual HTTPS proxy.

    Used by the update check and the banner feed."""
    try:
        node = _node(ctx, "/org.openoffice.Inet/Settings")
        kind = node.getPropertyValue("ooInetProxyType")
        if kind == 0:
            return {}
        host, port = node.getPropertyValue("ooInetHTTPSProxyName"), node.getPropertyValue("ooInetHTTPSProxyPort")
        if kind == 1 and host:
            return {"https": "%s:%s" % (host, port or 8080)}  # urllib reads host:port as an HTTP proxy
    except Exception:  # noqa: BLE001 - missing keys: fall back to urllib's defaults
        pass
    return None
