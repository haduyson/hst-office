# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Requests of the Trợ lý AI, sent only when the user presses a button that says it sends (never in the background).

Network access is injected: ``transport(request, provider, key) -> (status, body bytes)``; production uses
``http_transport`` (ai_http.py in its own process, killed at DEADLINE). Tests pass recorded answers.
What one request carries: the system text of the action, the user's own text (their question, or the selection /
formula they chose to send, shown before sending), the model name and the API key. Nothing else from the document,
no file names, no user name, no machine ID.
"""
import json
import threading

from .ai_providers import AiError, PROVIDERS, chat_request, models_request, parse_chat, parse_models

DEADLINE = 120  # seconds, DNS + TLS + generation; thinking models can take a minute
MODELS_DEADLINE = 20
# The helper's own deadline starts when its turn comes: the interpreter probe (once per session) and banner or
# citation helpers queued ahead of it come on top. Past DEADLINE + GRACE the dialog gets the timeout message anyway.
GRACE = 30


def _bounded(call, limit):
    """call() on its own thread; TimeoutError when it has not returned within `limit` seconds (it is abandoned: a
    helper it starts later is still killed at its own deadline and its answer dropped)."""
    box = {}

    def target():
        try:
            box["value"] = call()
        except BaseException as exc:  # noqa: BLE001 - handed to the caller as is
            box["error"] = exc
    worker = threading.Thread(target=target, name="hst-ai-helper", daemon=True)
    worker.start()
    worker.join(limit)
    if worker.is_alive():
        raise TimeoutError("AI request deadline")
    if "error" in box:
        raise box["error"]
    return box["value"]


class Settings:
    """What one request needs from the configuration: provider, model, key (from ai_keystore), release, proxy."""

    def __init__(self, provider, model, key, version="0", proxy=None):
        self.provider, self.model, self.key, self.version, self.proxy = provider, model, key, version, proxy

    def check(self):
        if self.provider not in PROVIDERS:
            raise AiError("provider")
        if not self.key:
            raise AiError("nokey")
        return self


def http_transport(timeout=DEADLINE):
    """Transport running ai_http.py in its own process, with proxy and release taken from `settings`."""
    from . import banner_fetch

    def run(request, settings):
        payload = dict(request, provider=settings.provider, key=settings.key, version=settings.version,
                       proxy=settings.proxy)
        try:
            data = _bounded(lambda: banner_fetch._run(json.dumps(payload).encode("utf-8"), timeout, "ai_http.py"),
                            timeout + GRACE)
        except TimeoutError as exc:
            raise AiError("timeout") from exc
        except (OSError, ValueError) as exc:  # no answer at all: offline, DNS, TLS, proxy, refused request
            raise AiError("network") from exc
        try:
            reply = json.loads(data)
        except ValueError as exc:
            raise AiError("reply") from exc
        if isinstance(reply, dict) and reply.get("timeout") is True:  # the helper's own socket timeout fired
            raise AiError("timeout")
        try:
            return int(reply["status"]), reply.get("body", "").encode("utf-8")
        except (ValueError, KeyError, TypeError) as exc:
            raise AiError("reply") from exc
    return run


def complete(settings, system, prompt, transport=None):
    """(text, truncated) of one completion; raises AiError with a kind the UI explains (ai_texts.ERRORS)."""
    settings.check()
    request = chat_request(settings.provider, settings.model, system, prompt)
    status, body = (transport or http_transport())(request, settings)
    return parse_chat(settings.provider, status, body)


def list_models(settings, transport=None):
    """Model IDs the provider offers to this key (the options page's "Tải danh sách")."""
    settings.check()
    status, body = (transport or http_transport(MODELS_DEADLINE))(models_request(settings.provider), settings)
    return parse_models(settings.provider, status, body)
