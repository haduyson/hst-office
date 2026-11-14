# SPDX-License-Identifier: AGPL-3.0-only
"""Load documents from a UNO client on the office's main thread (OnMainThread), as a user's open does.

Called over the UNO bridge, loadComponentFromURL builds the frame, sidebar and toolbars in the bridge thread. On
Windows each drop-down box's frame is then created by the main thread with the SolarMutex released
(WinSalInstance::SendWndMessage_impl), and the main thread's own sidebar and notebookbar work ran into the half-built
boxes: Sheets died at start in 3 of 20 fresh-profile starts on HST4 (12 of 20 with 1.0.1), 0 of 20 on the main
thread. Upstream's UI tests pass OnMainThread=True for the same reason. Every Windows check loads through here;
pass OnMainThread=False to test a bridge-thread load on purpose."""


def properties(**props):
    """PropertyValue tuple of props, OnMainThread=True unless given."""
    from com.sun.star.beans import PropertyValue
    args = []
    for name, value in dict({"OnMainThread": True}, **props).items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        args.append(prop)
    return tuple(args)


def load(desktop, url, target="_blank", flags=0, **props):
    """desktop.loadComponentFromURL(url, target, flags, props) on the office's main thread."""
    return desktop.loadComponentFromURL(url, target, flags, properties(**props))
