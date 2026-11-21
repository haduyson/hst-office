# SPDX-License-Identifier: AGPL-3.0-only
"""Commands of actions.COMMANDS whose code is imported only when they run (version history, citations)."""


def previous_versions(host):
    """Tệp tin ▸ Phiên bản trước: the versions a save overwrote (version_dialog, imported on use)."""
    from .version_dialog import run
    run(host.ctx, host.frame)


def citation_command(name):
    """Trích dẫn commands: the citation code is imported only when one of them runs."""
    def run(host):
        from . import citation_actions
        return citation_actions.COMMANDS[name](host)
    return run
