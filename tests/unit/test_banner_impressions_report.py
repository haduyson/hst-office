# SPDX-License-Identifier: AGPL-3.0-only
"""Daily display report: body schema and size, send decision, response handling, the feed attempt and the widget's
Shown call. Every transport is stubbed: no network."""
import json
import os
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from banner_fixtures import KEY, NOW, VERSION, Remote
from banner_payload_fixtures import service_module
from hst_office import banner_impressions as imp, banner_impressions_report as rep
from hst_office.banner_feed import BannerFeed
from hst_office.banner_urls import IMPRESSIONS_URL

URL = "https://system.hasontech.vn/hst-office/impressions"
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


class Post:
    def __init__(self, status=204):
        self.status, self.calls = status, []

    def __call__(self, url, data, release, proxy):
        self.calls.append((url, data, release, proxy))
        if isinstance(self.status, Exception):
            raise self.status
        return self.status


class BodyTest(unittest.TestCase):
    def test_schema_v1(self):
        data, sent = rep.body({"2026-11-12": {"hst-post": 12, "aios": 34}, "2026-11-11": {"aios": 1}}, "1.0.2")
        doc = json.loads(data)
        self.assertEqual(doc, {"schemaVersion": 1, "release": "1.0.2", "days": [
            {"day": "2026-11-11", "counts": {"aios": 1}}, {"day": "2026-11-12", "counts": {"aios": 34, "hst-post": 12}}]})
        self.assertEqual(sorted(doc), ["days", "release", "schemaVersion"])  # no machine ID, OS or document detail
        self.assertEqual(sent, {"2026-11-11": {"aios": 1}, "2026-11-12": {"aios": 34, "hst-post": 12}})
        data.decode("ascii")

    def test_contract_bounds_hold_for_any_pruned_store(self):
        today = imp.local_day(NOW)
        days = {(today - imp.datetime.timedelta(days=n)).isoformat(): {"id-%02d" % i: 5000 for i in range(30)}
                for n in range(9)}
        data, sent = rep.body(imp.prune(days, today), VERSION)
        doc = json.loads(data)
        self.assertLessEqual(len(data), rep.MAX_BODY)
        self.assertLessEqual(len(doc["days"]), 7)
        for entry in doc["days"]:
            self.assertLessEqual(len(entry["counts"]), 24)
            self.assertTrue(all(ID.match(i) and 1 <= n <= 5000 for i, n in entry["counts"].items()))
        self.assertEqual(sorted(sent), [entry["day"] for entry in doc["days"]])

    def test_oldest_days_are_left_out_until_the_body_fits_8_kib(self):
        long_ids = {"x" * 60 + "%02d" % i: 5000 for i in range(24)}
        days = {"2026-11-%02d" % d: dict(long_ids) for d in range(6, 13)}
        data, sent = rep.body(days, "1.0.2")
        self.assertLessEqual(len(data), 8192)
        self.assertEqual(max(sent), "2026-11-12")
        self.assertLess(len(sent), 7)
        self.assertEqual(sorted(sent), sorted(days)[-len(sent):])

    def test_nothing_to_send(self):
        self.assertEqual(rep.body({}, "1.0.2"), (None, {}))


class DecisionTest(unittest.TestCase):
    DAYS = {"2026-11-12": {"aios": 1}}

    def test_sends_on_a_valid_key_and_counts(self):
        self.assertTrue(rep.should_send(KEY, True, self.DAYS))

    def test_empty_placeholder_key_is_the_bundled_only_path(self):
        self.assertFalse(rep.should_send(b"", True, self.DAYS))
        self.assertFalse(rep.should_send(bytes(32), True, self.DAYS))

    def test_nothing_to_send(self):
        self.assertFalse(rep.should_send(KEY, True, {}))

    def test_test_packages_and_testing_origins_never_send(self):
        self.assertFalse(rep.should_send(KEY, False, self.DAYS))


class ResponseTest(unittest.TestCase):
    STORED = {"2026-11-11": {"aios": 3}, "2026-11-12": {"aios": 5, "hst-post": 1}}
    SENT = {"2026-11-11": {"aios": 3}, "2026-11-12": {"aios": 4, "hst-post": 1}}  # one aios counted meanwhile

    def test_received_or_refused_schema_removes_what_was_sent(self):
        for status in (200, 204, 400):
            self.assertEqual(rep.after_response(self.STORED, self.SENT, status), {"2026-11-12": {"aios": 1}}, status)

    def test_no_answer_rate_limit_and_server_errors_keep_everything(self):
        for status in (None, 429, 500, 502, 503, 404, 301):
            self.assertEqual(rep.after_response(self.STORED, self.SENT, status), self.STORED, status)

    def test_too_large_drops_the_oldest_sent_day(self):
        self.assertEqual(rep.after_response(self.STORED, self.SENT, 413),
                         {"2026-11-12": {"aios": 5, "hst-post": 1}})


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.counter = imp.Counter(self.tmp.name, lambda: NOW)
        self.today = imp.local_day(NOW).isoformat()

    def report(self, post, key=KEY, production=True):
        return rep.report(self.counter, VERSION, {"https": "proxy:8080"}, key, production, post)

    def test_pending_counts_are_flushed_sent_and_cleared(self):
        self.counter.record("aios")
        post = Post(204)
        self.assertEqual(self.report(post), 204)
        url, data, release, proxy = post.calls[0]
        self.assertEqual((url, release, proxy), (URL, VERSION, {"https": "proxy:8080"}))
        self.assertEqual(IMPRESSIONS_URL, URL)
        self.assertEqual(json.loads(data)["days"], [{"day": self.today, "counts": {"aios": 1}}])
        self.assertEqual(imp.load(self.counter.root, imp.local_day(NOW)), {})
        self.assertIsNone(self.report(post))  # nothing left to send
        self.assertEqual(len(post.calls), 1)

    def test_network_error_keeps_counts_for_the_next_day(self):
        self.counter.record("aios")
        self.assertIsNone(self.report(Post(TimeoutError("deadline"))))
        self.assertEqual(imp.load(self.counter.root, imp.local_day(NOW)), {self.today: {"aios": 1}})

    def test_not_allowed_reads_writes_and_sends_nothing(self):
        self.counter.record("aios")
        for kwargs in ({"key": b""}, {"production": False}):
            post = Post()
            self.assertIsNone(self.report(post, **kwargs))
            self.assertEqual(post.calls, [])
        self.assertEqual(list(self.counter.root.glob("*")), [])


class FeedAttemptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.post = Post(204)

    def feed(self, **kwargs):
        return BannerFeed(self.tmp.name, VERSION, public_key=KEY, fetcher=Remote(), clock=lambda: NOW,
                          poster=self.post, **kwargs)

    def refresh(self, feed):
        thread = feed.refresh_async()
        if thread:
            thread.join(10)

    def test_report_rides_on_the_claimed_daily_attempt_only(self):
        feed = self.feed()
        feed.shown("aios")
        self.refresh(feed)
        self.assertEqual(len(self.post.calls), 1)
        feed.shown("aios")
        feed._next_check = 0  # a second process sharing the profile: the stamp refuses the attempt
        self.refresh(feed)
        self.assertEqual(len(self.post.calls), 1)

    def test_counting_does_not_depend_on_send_install_id(self):
        """Display counting always runs: the anonymous install ID box neither stops counting nor reporting."""
        feed = self.feed()
        feed.shown("aios")
        self.refresh(feed)
        self.assertEqual(len(self.post.calls), 1)
        self.assertNotIn(b"install", self.post.calls[0][1].lower())
        source = open(os.path.join(os.path.dirname(rep.__file__), "banner_uno.py"), encoding="utf-8").read()
        self.assertNotIn("SendInstallId", source)
        self.assertNotIn("update_install_id", source)

    def test_testing_origin_does_not_report_to_production(self):
        feed = self.feed(override="https://staging.example.test/banners.json")
        feed.shown("aios")
        self.refresh(feed)
        self.assertEqual(self.post.calls, [])

    def test_widget_shown_argument_counts_without_a_slot_answer(self):
        feed = self.feed()
        service = service_module()
        with mock.patch.object(service, "feed_for_context", return_value=feed):
            answer = service.BannerService(None).execute((SimpleNamespace(Name="Shown", Value="aios"),))
        self.assertEqual(answer, "")
        feed.impressions.flush()
        self.assertEqual(imp.load(feed.root, imp.local_day(NOW)), {imp.local_day(NOW).isoformat(): {"aios": 1}})


if __name__ == "__main__":
    unittest.main()
