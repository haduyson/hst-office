# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from banner_fixtures import VERSION
from banner_https_fixtures import server, helper
from hst_office import banner_fetch
from hst_office.banner_feed import BannerFeed


class DeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.tmp.name)
        cls.httpd, cls.cert = server(cls.directory)
        cls.url = "https://localhost:" + str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def request(self, route, dns=False):
        script = helper(self.directory, self.cert, dns)
        processes = []
        original = subprocess.Popen
        def spawn(argv, **options):
            self.assertFalse(options["shell"])
            self.assertEqual(argv[1:3], ["-I", "-S"])
            proc = original(argv[:3] + [str(script)], **options)
            processes.append(proc)
            return proc
        started = time.monotonic()
        with patch.object(banner_fetch, "TIMEOUT", 1.0), patch.object(banner_fetch, "https_url", return_value=True), \
                patch.object(banner_fetch.subprocess, "Popen", side_effect=spawn):
            with self.assertRaises(TimeoutError):
                banner_fetch.fetch(self.url + route, 30, VERSION)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)
        return spawn

    def test_slow_body_deadline_kills_connection_and_next_request_recovers(self):
        spawn = self.request("/slow")
        with patch.object(banner_fetch, "https_url", return_value=True), \
                patch.object(banner_fetch.subprocess, "Popen", side_effect=spawn):
            self.assertEqual(banner_fetch.fetch(self.url + "/ok", 30, VERSION), b"ok")

    def test_redirect_chain_shares_total_deadline(self):
        self.request("/redirect0")

    def test_blocked_dns_is_killed_and_reaped(self):
        self.request("/ok", dns=True)

    def test_feed_worker_releases_refresh_lock_after_deadline(self):
        script = helper(self.directory, self.cert)
        original = subprocess.Popen
        def spawn(argv, **options):
            return original(argv[:3] + [str(script)], **options)
        with tempfile.TemporaryDirectory() as profile, patch.object(banner_fetch, "TIMEOUT", .5), \
                patch.object(banner_fetch, "https_url", return_value=True), \
                patch.object(banner_fetch.subprocess, "Popen", side_effect=spawn):
            from banner_fixtures import KEY
            feed = BannerFeed(profile, VERSION, public_key=KEY,
                              fetcher=lambda *args: banner_fetch.fetch(self.url + "/slow", 30, VERSION))
            worker = feed.refresh_async()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertTrue(feed._lock.acquire(blocking=False))
            feed._lock.release()
            self.assertEqual(len(feed.current()["items"]), 6)
