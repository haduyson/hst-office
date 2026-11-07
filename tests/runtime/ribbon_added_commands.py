# SPDX-License-Identifier: AGPL-3.0-only
"""Commands the 1.0.0 ribbon content adds (btnHst* items of notebookbar.ui), for check-ribbon-tabs.py."""
import os
import re

MODULES = {"writer": "swriter", "calc": "scalc", "impress": "simpress"}


def added_commands(instdir, app):
    """Commands of the btnHst* items. Items of contextual tabs (btnHstCtx*, btnHstLaunchCtx*) act on a selected table,
    picture or shape and are left to check-ribbon-contextual.py: the document frame has no dispatch for them."""
    path = os.path.join(instdir, f"share/config/soffice.cfg/modules/{MODULES[app]}/ui/notebookbar.ui")
    with open(path, encoding="utf-8") as handle:
        found = re.findall(r'id="(btnHst\w+)">(?:(?!</object>).)*?name="action-name">([^<]+)<', handle.read(), re.S)
    return sorted({command for ident, command in found if not ident.startswith(("btnHstCtx", "btnHstLaunchCtx"))})
