# SPDX-License-Identifier: AGPL-3.0-only
"""Local stand-in for POST /hst-office/api/error-reports on system.hasontech.vn, enforcing the server's reading of
the contract (plans/261106-0144-error-report/api-contract.md, "Server interpretation"). Tests and the runtime check
send to this server only, never to the real endpoint.

Written independently of the client's error_report_payload so that a client bug is not mirrored here.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
import uuid

PATH = "/hst-office/api/error-reports"
MAX_BODY = 262144
BYTE_LIMITS = {"systemInfo": 16384, "log": 196608, "crash": 16384}
CHAR_LIMITS = {"description": 5000, "contactEmail": 254}
UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


def invalid(doc):
    """Reason the server answers 400, or ''."""
    if not isinstance(doc, dict):
        return "not an object"
    get = lambda key: None if doc.get(key) is None else doc.get(key)  # noqa: E731 - null is absent
    if get("schemaVersion") != 1:
        return "schemaVersion"
    if not isinstance(get("reportId"), str) or not UUID4.fullmatch(get("reportId")):
        return "reportId"
    if get("kind") not in ("user", "crash"):
        return "kind"
    if not isinstance(get("createdAt"), str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", get("createdAt")):
        return "createdAt"
    product, system = get("product") or {}, get("os") or {}
    version = product.get("version") if isinstance(product, dict) else None
    if not isinstance(version, str) or not 0 < len(version) <= 80:
        return "product.version"
    if not isinstance(system, dict) or system.get("family") not in ("windows", "macos", "linux"):
        return "os.family"
    if get("app") not in ("writer", "calc", "impress", "draw", "math", "base", "start", "unknown"):
        return "app"
    if doc["kind"] == "user" and not (isinstance(get("description"), str) and get("description").strip()):
        return "description"
    for key, limit in CHAR_LIMITS.items():
        if get(key) is not None and (not isinstance(get(key), str) or len(get(key)) > limit):
            return key
    email = get("contactEmail")
    if email is not None and (re.search(r"[<>\"'`]", email) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        return "contactEmail"
    for key, value in (get("diagnostics") or {}).items():
        if value is not None and (not isinstance(value, str) or len(value.encode("utf-8")) > BYTE_LIMITS.get(key, 0)):
            return "diagnostics." + key
    return ""


class FakeServer:
    """Threaded HTTP server on 127.0.0.1; `mode` forces an answer: None (contract), 429, 500, 'slow', 'redirect'."""

    def __init__(self, per_hour=10):
        self.reports, self.tickets, self.requests, self.mode, self.per_hour = [], {}, [], None, per_hour
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                owner.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                status, reply = owner.answer(self.path, body, self.headers)
                if status == 302:
                    self.send_response(302)
                    self.send_header("Location", "/elsewhere")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                data = json.dumps(reply).encode() if reply is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = "http://127.0.0.1:%d%s" % (self.httpd.server_address[1], PATH)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def answer(self, path, body, headers):
        if self.mode == "slow":
            time.sleep(3)
        if self.mode == "redirect":
            return 302, None
        if isinstance(self.mode, int):
            return self.mode, None
        if path != PATH or not headers.get("Content-Type", "").startswith("application/json"):
            return 400, {"error": "invalid"}
        if len(body) > MAX_BODY:
            return 413, None
        try:
            doc = json.loads(body.decode("utf-8"))
        except ValueError:
            return 400, {"error": "invalid"}
        if invalid(doc):
            return 400, {"error": "invalid"}
        if doc["reportId"] in self.tickets:
            return 200, {"ticket": self.tickets[doc["reportId"]]}
        if len(self.reports) >= self.per_hour:
            return 429, None
        self.reports.append(doc)
        ticket = "HSTO-%06d" % len(self.reports)
        self.tickets[doc["reportId"]] = ticket
        return 201, {"ticket": ticket}

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def report(**changes):
    """A minimal valid kind=user report for the server tests."""
    doc = {"schemaVersion": 1, "reportId": str(uuid.uuid4()), "kind": "user", "createdAt": "2026-11-06T01:02:03Z",
           "product": {"version": "1.0.0-beta.5", "build": "500", "engine": "26.8.1.1"},
           "os": {"family": "linux", "version": "Ubuntu 24.04", "arch": "x86_64"}, "locale": "vi-VN", "app": "writer",
           "description": "Lỗi thử"}
    doc.update(changes)
    return doc
