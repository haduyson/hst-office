# SPDX-License-Identifier: AGPL-3.0-only
"""AI providers of the Trợ lý AI: OpenAI, Google Gemini and Anthropic Claude. Pure: no uno, no network.

Each provider turns (model, system text, user text) into one HTTPS request and its JSON answer back into text.
The API key never appears here: ai_http.py adds it as the provider's auth header inside its own process.
There is no default provider; the user picks one and enters their own key (they pay the provider directly).
Model IDs (checked 18/11/2026 on the providers' model pages): the list offers current ones, the first is the
preselected model, and "Tải danh sách" in the options asks the provider's own models endpoint for the rest.
"""
import json
import re
import urllib.parse

MAX_PROMPT = 60000  # characters of user text in one request (document excerpts are cut before this)
MAX_OUTPUT_TOKENS = 8192  # includes the hidden reasoning of thinking models
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")

PROVIDERS = {
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "host": "api.openai.com",
        "auth": ("Authorization", "Bearer "),
        "models": ("gpt-6.2-sol", "gpt-6.1-terra", "gpt-6-luna", "gpt-6.2-astra"),
        "keys_page": "https://platform.openai.com/api-keys",
    },
    "gemini": {
        "label": "Google Gemini",
        "host": "generativelanguage.googleapis.com",
        "auth": ("x-goog-api-key", ""),
        "models": ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"),
        "keys_page": "https://aistudio.google.com/apikey",
    },
    "claude": {
        "label": "Anthropic Claude",
        "host": "api.anthropic.com",
        "auth": ("x-api-key", ""),
        "models": ("claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"),
        "keys_page": "https://platform.claude.com/settings/keys",
    },
}
ORDER = ("openai", "gemini", "claude")
HOSTS = tuple(PROVIDERS[p]["host"] for p in ORDER)
CLAUDE_VERSION = "2023-06-01"


class AiError(Exception):
    """kind: key, quota, model, request, server, blocked, network, timeout, reply. detail: provider text or ''."""

    def __init__(self, kind, detail=""):
        super().__init__(kind)
        self.kind, self.detail = kind, detail


def check_provider(provider):
    if provider not in PROVIDERS:
        raise AiError("request", "unknown provider")
    return provider


def check_model(provider, model):
    check_provider(provider)
    if not isinstance(model, str) or not MODEL_ID.fullmatch(model):
        raise AiError("model")
    return model


def chat_request(provider, model, system, prompt, max_tokens=MAX_OUTPUT_TOKENS):
    """{"method", "url", "headers", "body"} of one completion (no key). Raises AiError("request") when too long."""
    check_model(provider, model)
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT:
        raise AiError("request", "prompt length")
    host = PROVIDERS[provider]["host"]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if provider == "openai":
        url = "https://" + host + "/v1/responses"
        body = {"model": model, "instructions": system, "input": prompt, "max_output_tokens": max_tokens,
                "store": False}
    elif provider == "gemini":
        url = "https://" + host + "/v1beta/models/" + urllib.parse.quote(model, safe="") + ":generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}}
    else:
        url = "https://" + host + "/v1/messages"
        headers["anthropic-version"] = CLAUDE_VERSION
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": prompt}]}
    return {"method": "POST", "url": url, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


def models_request(provider):
    """The provider's list-models request (no key)."""
    check_provider(provider)
    host = PROVIDERS[provider]["host"]
    headers = {"Accept": "application/json"}
    if provider == "claude":
        headers["anthropic-version"] = CLAUDE_VERSION
    path = {"openai": "/v1/models", "gemini": "/v1beta/models?pageSize=1000", "claude": "/v1/models?limit=1000"}
    return {"method": "GET", "url": "https://" + host + path[provider], "headers": headers, "body": None}


def _json(body):
    try:
        doc = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (ValueError, UnicodeError) as exc:
        raise AiError("reply") from exc
    if not isinstance(doc, dict):
        raise AiError("reply")
    return doc


def _error_detail(body):
    try:
        message = _json(body).get("error", {}).get("message", "")
    except (AiError, AttributeError):
        return ""
    return message[:300] if isinstance(message, str) else ""


def check_status(status, body):
    """Raise the AiError of a failed HTTP status (the provider's message as detail)."""
    if 200 <= status < 300:
        return
    detail = _error_detail(body)
    if status in (401, 403) or (status == 400 and "API key not valid" in detail):  # Gemini: 400 "API key not valid"
        raise AiError("key", detail)
    if status == 429:
        raise AiError("quota", detail)
    if status == 404:
        raise AiError("model", detail)
    if 400 <= status < 500:
        raise AiError("request", detail)
    raise AiError("server", detail)


def parse_chat(provider, status, body):
    """(text, truncated) of a completion answer."""
    check_status(status, body)
    doc = _json(body)
    parts, truncated = [], False
    if provider == "openai":
        for item in doc.get("output") or ():
            if isinstance(item, dict) and item.get("type") == "message":
                parts += [c.get("text", "") for c in item.get("content") or ()
                          if isinstance(c, dict) and c.get("type") == "output_text"]
                blocked = [c for c in item.get("content") or () if isinstance(c, dict) and c.get("type") == "refusal"]
                if blocked and not parts:
                    raise AiError("blocked", str(blocked[0].get("refusal", ""))[:300])
        truncated = doc.get("status") == "incomplete"
    elif provider == "gemini":
        if (doc.get("promptFeedback") or {}).get("blockReason"):
            raise AiError("blocked")
        candidate = (doc.get("candidates") or [{}])[0]
        content = candidate.get("content") or {}
        parts = [p.get("text", "") for p in content.get("parts") or () if isinstance(p, dict) and not p.get("thought")]
        if candidate.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII") and not parts:
            raise AiError("blocked")
        truncated = candidate.get("finishReason") == "MAX_TOKENS"
    else:
        parts = [c.get("text", "") for c in doc.get("content") or () if isinstance(c, dict) and c.get("type") == "text"]
        if doc.get("stop_reason") == "refusal" and not "".join(parts).strip():
            raise AiError("blocked")
        truncated = doc.get("stop_reason") == "max_tokens"
    text = "".join(p for p in parts if isinstance(p, str)).strip()
    if not text:
        raise AiError("reply")
    return text, truncated


def parse_models(provider, status, body):
    """Sorted model IDs the provider offers for text generation."""
    check_status(status, body)
    doc = _json(body)
    if provider == "gemini":
        names = [m.get("name", "") for m in doc.get("models") or () if isinstance(m, dict)
                 and "generateContent" in (m.get("supportedGenerationMethods") or ())]
        ids = [n[len("models/"):] if n.startswith("models/") else n for n in names]
    else:
        ids = [m.get("id", "") for m in doc.get("data") or () if isinstance(m, dict)]
    return sorted({i for i in ids if isinstance(i, str) and MODEL_ID.fullmatch(i)})
