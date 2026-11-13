# SPDX-License-Identifier: AGPL-3.0-only
"""Sending an error report through the real helper process to a local fake server (never the real endpoint):
201, 200 for a repeated reportId, 400, 413, 429, 5xx, redirect, timeout and no server; plus the crash prompt logic."""
import json
import socket
import sys
import time
import types
import unittest
import uuid

import _paths  # noqa: F401
from error_report_fake_server import FakeServer, invalid, report


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.task"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import error_report_crash as crash  # noqa: E402
from hst_office import error_report_payload as p  # noqa: E402
from hst_office import error_report_send as s  # noqa: E402

VERSION = "1.0.0-beta.5"


def body(**changes):
    return json.dumps(report(**changes), ensure_ascii=False).encode("utf-8")


class SendTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeServer(per_hour=3)
        self.environ = {s.TEST_URL_ENV: self.server.url}

    def tearDown(self):
        self.server.close()

    def send(self, data, timeout=10):
        return s.send(data, VERSION, proxy={}, test_mode=True, environ=self.environ, timeout=timeout)

    def test_201_then_200_for_the_same_report_id(self):
        data = body()
        first, again = self.send(data), self.send(data)
        self.assertEqual((first.kind, first.ticket, first.status), ("sent", "HSTO-000001", 201))
        self.assertEqual((again.kind, again.ticket, again.status), ("sent", "HSTO-000001", 200))
        sent = self.server.requests[0]
        self.assertEqual(sent["body"], data)  # byte for byte what the client encoded
        self.assertEqual(sent["headers"]["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(sent["headers"]["User-Agent"], "HSTOffice/" + VERSION)
        self.assertNotIn("Cookie", sent["headers"])

    def test_400_invalid(self):
        outcome = self.send(body(reportId="not-a-uuid"))
        self.assertEqual((outcome.kind, outcome.offers_email), ("invalid", False))
        self.assertEqual(self.send(body(contactEmail="a'b@congty.vn")).kind, "invalid")

    def test_413_too_large(self):
        oversize = body(diagnostics={"log": "x" * (p.MAX_BODY - 400)}) + b" " * 1000
        self.assertEqual(self.send(oversize).kind, "network")  # the helper never uploads more than 256 KiB
        self.assertEqual(self.server.requests, [])
        self.server.mode = None
        self.assertEqual(self.server.answer("/hst-office/api/error-reports", oversize, {"Content-Type": "application/json"})[0], 413)
        self.server.mode = 413  # what the client does if the server still answers 413
        outcome = self.send(body())
        self.assertEqual((outcome.kind, outcome.status, outcome.offers_email), ("too_large", 413, False))

    def test_429_after_the_hourly_limit_offers_email(self):
        for _ in range(3):
            self.assertEqual(self.send(body()).kind, "sent")
        outcome = self.send(body())
        self.assertEqual((outcome.kind, outcome.status, outcome.offers_email), ("rate_limited", 429, True))

    def test_5xx_and_unreadable_success_are_server_failures(self):
        for status in (500, 502, 503):
            self.server.mode = status
            outcome = self.send(body())
            self.assertEqual((outcome.kind, outcome.status, outcome.offers_email), ("server", status, True))
        self.assertEqual(s.classify(201, "{}").kind, "server")
        self.assertEqual(s.classify(201, "not json").kind, "server")
        self.assertEqual(s.classify(201, '{"ticket": "HSTO-000123"}').ticket, "HSTO-000123")
        self.assertEqual(s.classify(200, '{"ticket": "X-1"}').ticket, "X-1")  # shown as the server gives it
        for bad in ('{"ticket": ""}', '{"ticket": "%s"}' % ("A" * 33), '{"ticket": "HSTO\\n1"}', '{"ticket": 7}'):
            self.assertEqual(s.classify(201, bad).kind, "server", bad)

    def test_redirect_is_not_followed(self):
        self.server.mode = "redirect"
        self.assertEqual(self.send(body()).kind, "server")
        self.assertEqual([r["path"] for r in self.server.requests], [s.ENDPOINT[len("https://system.hasontech.vn"):]])

    def test_timeout_is_a_network_failure_within_the_deadline(self):
        self.server.mode = "slow"
        started = time.monotonic()
        outcome = self.send(body(), timeout=1)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual((outcome.kind, outcome.offers_email), ("network", True))

    def test_no_server_is_a_network_failure(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environ = {s.TEST_URL_ENV: "http://127.0.0.1:%d/hst-office/api/error-reports" % port}
        outcome = s.send(body(), VERSION, proxy={}, test_mode=True, environ=environ, timeout=5)
        self.assertEqual(outcome.kind, "network")

    def test_release_packages_ignore_the_test_url(self):
        calls = []
        s.send(body(), VERSION, test_mode=False, environ=self.environ, run=lambda *a: calls.append(a) or b"x")
        request = json.loads(calls[0][0])
        self.assertEqual((request["url"], request["allow_test"]), (p.ENDPOINT, False))
        self.assertEqual((calls[0][1], calls[0][2]), (15, "error_report_http.py"))
        self.assertEqual(s.endpoint(True, {s.TEST_URL_ENV: "http://evil.example/x"}), p.ENDPOINT)
        self.assertFalse(p.allowed_url(self.server.url, allow_test=False))
        self.assertFalse(p.allowed_url("https://system.hasontech.vn/other", allow_test=True))
        self.assertTrue(p.allowed_url(p.ENDPOINT))
        self.assertEqual(self.server.requests, [])

    def test_fake_server_reads_the_contract(self):
        self.assertEqual(invalid(report(contactEmail=None, diagnostics=None)), "")  # null is absent
        self.assertEqual(invalid(report(app=None)), "app")
        self.assertEqual(invalid(report(kind="crash", description=None)), "")
        self.assertEqual(invalid(report(product={"version": "1" * 81})), "product.version")
        self.assertEqual(invalid(report(reportId=str(uuid.uuid1()))), "reportId")
        self.assertEqual(invalid(report(diagnostics={"crash": "é" * 8193})), "diagnostics.crash")


class CrashPromptTests(unittest.TestCase):
    def state(self, crashed=False, session=False, modules=()):
        return {"crashed": crashed, "session": session, "modules": list(modules)}

    def test_abnormal_exit_is_the_office_recovery_test(self):
        self.assertTrue(crash.abnormal(self.state(crashed=True)))
        self.assertTrue(crash.abnormal(self.state(modules=["com.sun.star.text.TextDocument"])))
        self.assertFalse(crash.abnormal(self.state(session=True, modules=["com.sun.star.text.TextDocument"])))
        self.assertFalse(crash.abnormal(self.state()))

    def test_crash_facts_name_no_document(self):
        text, app = crash.crash_facts(self.state(True, False, ["com.sun.star.sheet.SpreadsheetDocument"] * 2))
        self.assertEqual(app, "calc")
        self.assertIn("Emergency save ran: yes", text)
        self.assertIn("Documents open at exit: 2 (HST Sheets)", text)
        _, app = crash.crash_facts(self.state(True, False, ["com.sun.star.sheet.SpreadsheetDocument",
                                                            "com.sun.star.text.TextDocument"]))
        self.assertEqual(app, "unknown")

    def test_answers(self):
        writes, opened = [], []
        crash._write = lambda ctx, path, name, value: writes.append((path, name, value))
        for answer, expect_writes, expect_open in (
                ("no", [(crash.RECOVERY + "/RecoveryInfo", "Crashed", False)], []),
                ("never", [(crash.RECOVERY + "/RecoveryInfo", "Crashed", False),
                           (crash.SETTINGS, "AskAfterCrash", False)], []),
                ("send", [(crash.RECOVERY + "/RecoveryInfo", "Crashed", False)], ["crash"])):
            writes.clear()
            opened.clear()
            crash.STATE["pending"] = self.state(crashed=True, modules=["com.sun.star.text.TextDocument"])
            got = crash.ask(None, frame=types.SimpleNamespace(getContainerWindow=lambda: None),
                            show=lambda ctx, peer, a=answer: a,
                            open_report=lambda ctx, frame, kind, text, app: opened.append(kind))
            self.assertEqual((got, writes, opened), (answer, expect_writes, expect_open))
            self.assertIsNone(crash.STATE["pending"])
            self.assertIsNone(crash.ask(None, show=lambda *a: self.fail("asked twice")))


if __name__ == "__main__":
    unittest.main()
