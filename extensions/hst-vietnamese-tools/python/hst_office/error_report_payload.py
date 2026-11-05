# SPDX-License-Identifier: AGPL-3.0-only
"""Error report body (schema 1 of the system.hasontech.vn error-report API): build, bound, validate, encode.

Pure logic without UNO or network, shared by the dialog, the crash prompt and the tests. The body sent is exactly
encode(payload); the dialog's "Xem nội dung sẽ gửi" shows preview_text(payload), the same object indented.
"""
import json
import platform
import re
import time
import urllib.parse
import uuid

from .update_logic import TEST_HOST

ENDPOINT = "https://system.hasontech.vn/hst-office/api/error-reports"
SCHEMA_VERSION = 1
MAX_BODY = 256 * 1024
MAX_DESCRIPTION = 5000  # characters
MAX_EMAIL = 254
MAX_OS_VERSION = 120
MAX_VERSION = 80  # product.version, characters
LIMITS = {"systemInfo": 16 * 1024, "log": 192 * 1024, "crash": 16 * 1024}  # UTF-8 bytes per diagnostics field
LOG_LINES, LOG_BYTES = 200, 32 * 1024  # the client keeps the log far below the API limit
KINDS = ("user", "crash")
APPS = ("writer", "calc", "impress", "draw", "math", "base", "start", "unknown")
FAMILIES = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
ARCHES = {"x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
_EMAIL = re.compile(r"[^@\s\"'`<>(),;:\\\[\]]{1,64}@(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+")


# Server side: control characters except tab and LF are dropped, CRLF/CR become LF, bidi controls and invisible
# characters become U+FFFD. The client does the same so that the preview equals what is stored.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INVISIBLE = re.compile("[\u061c\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u206f\ufeff]")
CUT_HEAD = "[… đã cắt bớt phần đầu]\n"
CUT_TAIL = "\n[… đã cắt bớt phần cuối]"


def sanitize(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return _INVISIBLE.sub("\ufffd", _CONTROL.sub("", text))


def allowed_url(url, allow_test=False):
    """The fixed endpoint; plain HTTP to 127.0.0.1 only for test packages (--update-test-mode)."""
    if url == ENDPOINT:
        return True
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for a bad port
    except (ValueError, TypeError, AttributeError):
        return False
    return bool(allow_test and isinstance(url, str) and not any(c.isspace() for c in url) and parts.scheme == "http"
                and parts.hostname == TEST_HOST and parts.username is None)


def new_report_id():
    return str(uuid.uuid4())


def utc_now(clock=time.time):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock()))


def arch_of(machine):
    return ARCHES.get((machine or "").lower(), (machine or "unknown").lower()[:20])


def os_info(system=None, release=None, version=None, machine=None, mac_version=None, pretty_name=None):
    """{"family", "version", "arch"} of this machine; the version names the OS release only (no host name)."""
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    family = FAMILIES.get(system, system.lower() or "unknown")
    if family == "macos":
        text = "macOS " + (platform.mac_ver()[0] if mac_version is None else mac_version)
    elif family == "windows":
        text = "Windows %s (%s)" % (platform.release() if release is None else release,
                                    platform.version() if version is None else version)
    else:
        if pretty_name is None:
            pretty_name = _os_release_name()
        kernel = platform.release() if release is None else release
        text = ("%s, kernel %s" % (pretty_name, kernel)) if pretty_name else "%s %s" % (system, kernel)
    return {"family": family, "version": text.strip()[:MAX_OS_VERSION], "arch": arch_of(machine)}


def _os_release_name():
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            continue
    return ""


def utf8_len(text):
    return len(text.encode("utf-8"))


def fit_bytes(text, limit, keep_tail=False):
    """`text` within `limit` UTF-8 bytes, marker included; a log keeps its end (the recent lines), the rest their start."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    marker = CUT_HEAD if keep_tail else CUT_TAIL
    room = limit - utf8_len(marker)
    cut = data[len(data) - room:] if keep_tail else data[:room]
    cut = cut.decode("utf-8", "ignore")
    return marker + cut if keep_tail else cut + marker


def build_payload(report_id, kind, created_at, product, os, locale, app, description="", contact_email="",
                  diagnostics=None):
    """The request object; empty optional fields are left out, diagnostics are cut to their limits."""
    product = {key: sanitize(str(value)) for key, value in product.items()}
    product["version"] = product["version"][:MAX_VERSION]
    os = dict(os, version=sanitize(os.get("version", ""))[:MAX_OS_VERSION])
    payload = {"schemaVersion": SCHEMA_VERSION, "reportId": report_id, "kind": kind, "createdAt": created_at,
               "product": product, "os": os, "locale": locale or "vi-VN",
               "app": app if app in APPS else "unknown"}
    description = sanitize(description).strip()
    if description or kind == "user":
        payload["description"] = description
    if (contact_email or "").strip():
        payload["contactEmail"] = contact_email.strip()
    extra = {}
    for name, limit in LIMITS.items():
        value = sanitize((diagnostics or {}).get(name))
        if value.strip():
            extra[name] = fit_bytes(value, limit, keep_tail=name == "log")
    if extra:
        payload["diagnostics"] = extra
    return payload


def encode(payload):
    """The exact request body: compact UTF-8 JSON."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def preview_text(payload):
    """What the user reviews: the same object, indented."""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def is_email(text):
    return len(text) <= MAX_EMAIL and bool(_EMAIL.fullmatch(text))


def problems(payload):
    """Codes of what stops sending: description_missing, description_long, email_invalid, too_large."""
    found = []
    description = payload.get("description", "")
    if payload["kind"] == "user" and not description:
        found.append("description_missing")
    if len(description) > MAX_DESCRIPTION:
        found.append("description_long")
    email = payload.get("contactEmail")
    if email is not None and not is_email(email):
        found.append("email_invalid")
    if len(encode(payload)) > MAX_BODY:
        found.append("too_large")
    return found


def schema_errors(payload):
    """Contract checks the server applies too (the tests run them on every payload the client can build)."""
    errors = []
    if payload.get("schemaVersion") != SCHEMA_VERSION or payload.get("kind") not in KINDS:
        errors.append("schemaVersion/kind")
    try:
        if str(uuid.UUID(payload["reportId"])) != payload["reportId"] or uuid.UUID(payload["reportId"]).version != 4:
            errors.append("reportId")
    except (KeyError, ValueError, TypeError):
        errors.append("reportId")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", payload.get("createdAt", "")):
        errors.append("createdAt")
    if payload.get("os", {}).get("family") not in ("windows", "macos", "linux"):
        errors.append("os.family")
    if not 0 < len(payload.get("product", {}).get("version") or "") <= MAX_VERSION:
        errors.append("product.version")
    if len(payload.get("os", {}).get("version", "")) > MAX_OS_VERSION:
        errors.append("os.version")
    if payload.get("app") not in APPS:
        errors.append("app")
    for name, value in payload.get("diagnostics", {}).items():
        if name not in LIMITS or utf8_len(value) > LIMITS[name]:
            errors.append("diagnostics." + name)
    return errors + problems(payload)
