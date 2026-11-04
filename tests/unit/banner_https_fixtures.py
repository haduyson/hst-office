# SPDX-License-Identifier: AGPL-3.0-only
"""Loopback HTTPS and an isolated helper with a temporary CA, for real deadline regressions."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
import threading
import time

from _paths import ROOT


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            if self.path.startswith("/redirect"):
                time.sleep(.35)
                self.send_response(302)
                self.send_header("Location", "/redirect" + str(int(self.path[9:] or '0') + 1))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", "20" if self.path == "/slow" else "2")
            self.end_headers()
            if self.path == "/slow":
                for _ in range(20):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(.2)
            else:
                self.wfile.write(b"ok")
        except (OSError, ssl.SSLError):
            pass  # expected: the deadline kills the client and closes its connection


def server(directory):
    cert, key = directory / "local.pem", directory / "local.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
                    "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, cert


def helper(directory, cert, stall_dns=False):
    path = directory / "test-helper.py"
    path.write_text('''import sys, ssl, time, socket
sys.path.insert(0, %r)
from hst_office import banner_http
# The loopback fixture uses an ephemeral port; production continues to require HTTPS port 443.
banner_http.https_url = lambda url: url.startswith("https://localhost:")
banner_http.tls_context = lambda: ssl.create_default_context(cafile=%r)
%s
raise SystemExit(banner_http.main())
''' % (str(Path(ROOT) / "extensions/hst-vietnamese-tools/python"), str(cert),
       'socket.getaddrinfo = lambda *a, **k: time.sleep(30)' if stall_dns else ''))
    return path
