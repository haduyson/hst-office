# SPDX-License-Identifier: AGPL-3.0-only
"""What the update server sees with the anonymous install ID (local plain-HTTP server, test-build override), that
both check entry points attach it, and that it never reaches an error message, the local log or an error report."""
import http.server
import os
import tempfile
import threading
import unittest
from unittest import mock

from install_id_support import ID, cfg
from hst_office import diag_log  # noqa: E402
from hst_office import update_fetch as fetch  # noqa: E402
from hst_office import update_install_id as iid  # noqa: E402
from hst_office import update_job as job  # noqa: E402
from hst_office import update_logic as logic  # noqa: E402
from hst_office.error_report_filter import scrub  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}
    lines = []

    def do_GET(self):  # noqa: N802 - http.server API
        self.lines.append((self.requestline, self.headers.get("User-Agent")))
        status, headers, body = self.routes.get(self.path.split("?")[0], (404, {}, b""))  # a static server
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Request(unittest.TestCase):
    """What the server sees, against a local plain-HTTP server (test-build override)."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def fetch(self, routes, install_id, url=None):
        _Handler.routes, _Handler.lines = routes, []
        info = {"release": "1.0.1", "channel": "stable", "test_mode": True, "install_id": install_id}
        try:
            fetch.fetch_channels(info, proxy={}, environ={fetch.TEST_URL_ENV: url or self.base + "/latest.json"})
        except fetch.UpdateError as exc:
            return exc
        return None

    def test_manifest_request_carries_the_id_and_nothing_else(self):
        error = self.fetch({"/latest.json": (200, {}, b"{}"), "/latest.json.sig": (200, {}, b"AAAA\n")}, ID)
        self.assertIsInstance(error, fetch.UpdateError)  # bad signature: irrelevant here, both requests were made
        lines = [line for line, _agent in _Handler.lines]
        self.assertEqual(lines, ["GET /latest.json?i=%s HTTP/1.1" % ID, "GET /latest.json.sig HTTP/1.1"])
        for _line, agent in _Handler.lines:
            self.assertRegex(agent, r"^HSTOffice/1\.0\.1 \((Windows|macOS|Linux|Other)\)$")

    def test_opted_out_request_has_no_query(self):
        self.fetch({"/latest.json": (200, {}, b"{}"), "/latest.json.sig": (200, {}, b"AAAA\n")}, None)
        self.assertEqual([line for line, _agent in _Handler.lines],
                         ["GET /latest.json HTTP/1.1", "GET /latest.json.sig HTTP/1.1"])

    def test_limits_still_apply(self):
        cases = {"oversized": {"/latest.json": (200, {}, b" " * (logic.MAX_BYTES + 1))},
                 "foreign redirect": {"/latest.json": (302, {"Location": "https://evil.example/latest.json"}, b"")}}
        for label, routes in cases.items():
            with self.subTest(label):
                self.assertIsInstance(self.fetch(routes, ID), fetch.UpdateError)

    def test_errors_never_carry_the_id(self):
        cases = {"server error": ({"/latest.json": (500, {}, b"")}, None),
                 "not found": ({}, None),
                 "connection refused": ({}, "http://127.0.0.1:1/latest.json")}
        for label, (routes, url) in cases.items():
            with self.subTest(label):
                error = self.fetch(routes, ID, url)
                self.assertIsNotNone(error)
                text = "%s %r %r" % (error, error.args, error.__cause__)
                self.assertNotIn(ID, text)

    def test_unticked_during_a_check_drops_the_id_from_its_retries(self):
        iid.set_sending(False)
        self.addCleanup(iid.set_sending, True)
        self.fetch({"/latest.json": (200, {}, b"{}"), "/latest.json.sig": (200, {}, b"AAAA\n")}, ID)
        self.assertEqual(_Handler.lines[0][0], "GET /latest.json HTTP/1.1")

    def test_signature_request_never_carries_the_id(self):
        self.fetch({"/latest.json": (200, {}, b"{}")}, ID)
        self.assertTrue(all(ID not in line for line, _agent in _Handler.lines if ".sig" in line))


class JobAttachesTheId(unittest.TestCase):
    def setUp(self):
        self.seen = []
        for target, name, value in (
                (job.ui, "release_info_for", lambda ctx: {"release": "1.0.1", "channel": "stable", "test_mode": False}),
                (job.ui, "settings", lambda ctx: dict(cfg.DEFAULTS)),
                (job.ui, "proxy", lambda ctx: None),
                (job.ui, "save", lambda ctx, name, value: True),
                (job.ui, "on_main_thread", lambda ctx, fn: fn()),
                (job, "fetch_channels", lambda info, proxy: self.seen.append(info) or {"stable": None, "beta": None})):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_automatic_and_manual_checks_send_it(self):
        with mock.patch.object(job.update_install_id, "for_check", return_value=ID):
            thread = job.automatic_check(object(), 2_000_000_000)
            thread.join(10)
            job.start_background(object(), iid.add_to(object(), {"release": "1.0.1", "channel": "stable"}), lambda *a: None).join(10)
        self.assertEqual([info["install_id"] for info in self.seen], [ID, ID])

    def test_opted_out(self):
        with mock.patch.object(job.update_install_id, "for_check", return_value=None):
            self.assertIsNone(iid.add_to(object(), {"release": "1.0.1"})["install_id"])


class NeverLogged(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, [])

    def tearDown(self):
        diag_log.configure(None)
        self.folder.cleanup()

    def test_scrub_replaces_any_uuid(self):
        text = "GET /update/latest-2.json?i=%s failed; id %s; upper %s" % (ID, ID, ID.upper())
        self.assertNotIn(ID, scrub(text, []).lower())
        self.assertIn("<ID>", scrub(text, []))

    def test_local_log_never_records_it(self):
        diag_log.warning("update", "check failed: i=%s" % ID)
        try:
            raise OSError("HTTP Error 500 for https://office.hasontech.vn/update/latest-2.json?i=" + ID)
        except OSError:
            diag_log.exception("update_job", print_too=False)
        with open(os.path.join(self.folder.name, diag_log.LOG_NAME), encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(ID, text)
        self.assertIn("check failed: i=<ID>", text)
        self.assertNotIn(ID, diag_log.recent(100, 10000))

    def test_failed_check_logs_without_it(self):
        def failing(info, proxy):
            raise fetch.FetchError("URLError: offline")
        with mock.patch.object(job, "fetch_channels", failing), mock.patch("builtins.print"):
            self.assertEqual(job._fetch_update({"release": "1.0.1", "channel": "stable", "install_id": ID}, None),
                             (None, True))
        with open(os.path.join(self.folder.name, diag_log.LOG_NAME), encoding="utf-8") as handle:
            self.assertNotIn(ID, handle.read())


if __name__ == "__main__":
    unittest.main()
