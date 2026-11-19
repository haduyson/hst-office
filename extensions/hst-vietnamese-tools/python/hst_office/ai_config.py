# SPDX-License-Identifier: AGPL-3.0-only
"""Settings of the Trợ lý AI in /org.hasontech.hstoffice.AI (ai.xcs): Enabled (default off), Provider (default none)
and one model per provider. The API keys are not settings: see ai_keystore. A value an administrator finalized is
read as locked: the options page greys it out and never writes it."""
from . import diag_log
from .ai_providers import ORDER, PROVIDERS

CONFIG_PATH = "/org.hasontech.hstoffice.AI"
MODEL_KEYS = {"openai": "OpenAIModel", "gemini": "GeminiModel", "claude": "ClaudeModel"}
DEFAULTS = {"Enabled": False, "Provider": "", "OpenAIModel": "", "GeminiModel": "", "ClaudeModel": ""}
READONLY = 16  # com.sun.star.beans.PropertyAttribute.READONLY: a finalized property


def normalize(values):
    """Pure: clean settings (unknown provider -> none, booleans as bool, strings stripped)."""
    out = dict(DEFAULTS)
    out.update({k: v for k, v in values.items() if k in DEFAULTS})
    out["Enabled"] = bool(out["Enabled"])
    for key in ("Provider",) + tuple(MODEL_KEYS.values()):
        out[key] = str(out[key] or "").strip()
    if out["Provider"] not in PROVIDERS:
        out["Provider"] = ""
    return out


def model_for(values, provider):
    """Pure: the configured model of `provider`, else its first suggested model."""
    return values.get(MODEL_KEYS[provider]) or PROVIDERS[provider]["models"][0]


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load(ctx):
    """(values, locked names). A missing schema reads as the defaults: the assistant stays off."""
    try:
        node = _access(ctx, True)
        info = node.getPropertySetInfo()
        values, locked = {}, set()
        for name in DEFAULTS:
            if info.hasPropertyByName(name):
                values[name] = node.getPropertyValue(name)
                if info.getPropertyByName(name).Attributes & READONLY:
                    locked.add(name)
        return normalize(values), locked
    except Exception:  # noqa: BLE001 - schema missing or profile unreadable
        diag_log.exception("ai_config")
        return dict(DEFAULTS), set(DEFAULTS)


def save(ctx, changes):
    """Write the changed values that are not locked; True when written."""
    try:
        values, locked = load(ctx)
        changes = {k: v for k, v in normalize(dict(values, **changes)).items() if k not in locked and values[k] != v}
        if not changes:
            return True
        node = _access(ctx, True)
        for name, value in changes.items():
            node.setPropertyValue(name, value)
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001
        diag_log.exception("ai_config")
        return False


def enabled(ctx):
    values, _ = load(ctx)
    return values["Enabled"]


def active_provider(ctx):
    """(provider, model) when the assistant is on and a provider is chosen, else None."""
    values, _ = load(ctx)
    if not values["Enabled"] or values["Provider"] not in ORDER:
        return None
    return values["Provider"], model_for(values, values["Provider"])
