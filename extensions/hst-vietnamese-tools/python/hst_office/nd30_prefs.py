# SPDX-License-Identifier: AGPL-3.0-only
"""The ND30 wizard's remembered choices, per user in /org.hasontech.hstoffice.Nd30 (nd30.xcs): the length of the rule
under the agency name (nd30_rule_length). Read when the wizard opens, written when it is accepted; a missing schema or
an unreadable profile falls back to the default and never stops the wizard."""
from . import diag_log
from .nd30_rule_length import DEFAULT, encode, parse

CONFIG_PATH = "/org.hasontech.hstoffice.Nd30"


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load_agency_rule(ctx):
    """The remembered rule choice, checked ("2/5" when none or damaged)."""
    try:
        return encode(*parse(_access(ctx, False).getPropertyValue("AgencyRule")))
    except Exception:  # noqa: BLE001 - schema missing or profile unreadable: the default
        diag_log.exception("nd30_prefs")
        return DEFAULT


def save_agency_rule(ctx, value):
    """Remember `value` (checked first). Returns False if it could not be written."""
    try:
        node = _access(ctx, True)
        node.setPropertyValue("AgencyRule", encode(*parse(value)))
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001 - not remembering must not lose the document just inserted
        diag_log.exception("nd30_prefs")
        return False
