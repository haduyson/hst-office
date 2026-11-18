# SPDX-License-Identifier: AGPL-3.0-only
"""Banner/citation/error-report helpers: the office's bundled Python first (no system Python needed), one helper
process at a time, and the feed worker does nothing before the office's start-up work is over."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import uno_stubs  # noqa: F401  (before any hst_office module that imports uno)
from banner_fixtures import KEY, VERSION
from hst_office import banner_fetch, ui_idle
from hst_office.banner_feed import BannerFeed


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


class BundledInterpreter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.program = Path(self.tmp.name) / "program"
        self.prefix = self.program / "python-core-3.13.18"
        (self.prefix / "lib").mkdir(parents=True)
        banner_fetch._command = None

    def tearDown(self):
        banner_fetch._command = None
        self.tmp.cleanup()

    def test_linux_layout_runs_python_bin_with_its_home(self):
        touch(self.program / "python.bin")
        [(argv, extra)] = banner_fetch._bundled(self.prefix)
        self.assertEqual(argv, [str(self.program / "python.bin")] + banner_fetch.ISOLATED_WITH_HOME)
        self.assertNotIn("-I", argv)  # -I would hide PYTHONHOME and the interpreter would not start
        self.assertEqual(extra["PYTHONHOME"], str(self.prefix))
        self.assertEqual(extra["PYTHONPATH"].split(os.pathsep), [str(self.prefix / "lib"), str(self.prefix / "lib" / "lib-dynload")])

    def test_windows_layout_finds_its_dll_in_program(self):
        touch(self.prefix / "bin" / "python.exe")
        [(argv, extra)] = banner_fetch._bundled(self.prefix)
        self.assertEqual(argv, [str(self.prefix / "bin" / "python.exe"), "-I", "-S"])
        self.assertEqual(extra, {"PATH": str(self.program)})

    def test_environment_drops_python_variables_and_keeps_proxy(self):
        with patch.dict(os.environ, {"PYTHONSTARTUP": "/x", "PYTHONPATH": "/evil", "https_proxy": "http://p:3128",
                                     "PATH": "/usr/bin"}, clear=True):
            env = banner_fetch._environment({"PYTHONHOME": "/home", "PATH": "/office/program"})
        self.assertEqual(env, {"https_proxy": "http://p:3128", "PYTHONHOME": "/home",
                               "PATH": "/office/program" + os.pathsep + "/usr/bin"})

    def test_bundled_python_is_chosen_before_the_running_interpreter(self):
        touch(self.program / "python.bin")
        with patch.object(sys, "base_prefix", str(self.prefix)), \
                patch.object(banner_fetch, "_works", return_value=True) as works:
            argv, env = banner_fetch.helper_command()
        self.assertEqual(argv[0], str(self.program / "python.bin"))
        self.assertEqual(env["PYTHONHOME"], str(self.prefix))
        self.assertEqual(works.call_count, 1)
        with patch.object(banner_fetch, "_works") as again:
            banner_fetch.helper_command()  # probed once per process
        again.assert_not_called()

    def test_no_system_python_needed(self):
        touch(self.program / "python.bin")
        with patch.object(sys, "base_prefix", str(self.prefix)), patch.object(banner_fetch, "_fallbacks", return_value=[]), \
                patch.object(banner_fetch, "_works", return_value=True):
            self.assertEqual(banner_fetch.helper_command()[0][0], str(self.program / "python.bin"))

    def test_falls_back_when_the_bundled_python_does_not_start(self):
        touch(self.program / "python.bin")
        with patch.object(sys, "base_prefix", str(self.prefix)), \
                patch.object(banner_fetch, "_works", side_effect=lambda argv, env: "python.bin" not in argv[0]):
            argv, _ = banner_fetch.helper_command()
        self.assertNotEqual(argv[0], str(self.program / "python.bin"))
        self.assertEqual(argv[1:], banner_fetch.ISOLATED)

    def test_installed_office_python_starts_without_system_python(self):
        """HST_INSTDIR=<office dir>: the real bundled interpreter, with PATH emptied, runs a TLS import."""
        instdir = os.environ.get("HST_INSTDIR")
        if not instdir:
            self.skipTest("HST_INSTDIR not set")
        cores = sorted((Path(instdir) / "program").glob("python-core-*"))
        found = banner_fetch._bundled(cores[-1]) if cores else []
        self.assertTrue(found, "no bundled Python in " + instdir)
        argv, extra = found[0]
        with patch.dict(os.environ, {"PATH": "/nonexistent"}, clear=True):
            self.assertTrue(banner_fetch._works(argv, banner_fetch._environment(extra)))


class OneHelperAtATime(unittest.TestCase):
    def test_concurrent_requests_queue(self):
        running, peak, lock = [0], [0], threading.Lock()

        class Proc:
            returncode = 0

            def __init__(self, argv, **options):
                pass

            def __enter__(self):
                with lock:
                    running[0] += 1
                    peak[0] = max(peak[0], running[0])
                return self

            def __exit__(self, *exc):
                with lock:
                    running[0] -= 1

            def communicate(self, payload, timeout=None):
                time.sleep(0.2)
                return b"ok", b""

        banner_fetch._command = (["python3", "-I", "-S"], {})
        try:
            with patch.object(banner_fetch.subprocess, "Popen", Proc):
                threads = [threading.Thread(target=banner_fetch._run, args=(b"{}", 5)) for _ in range(3)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(5)
        finally:
            banner_fetch._command = None
        self.assertEqual(peak[0], 1)


class FeedWaitsForStartup(unittest.TestCase):
    def test_no_fetch_before_ready_returns(self):
        released, fetched = threading.Event(), []
        with tempfile.TemporaryDirectory() as profile:
            feed = BannerFeed(profile, VERSION, public_key=KEY, ready=released.wait,
                              fetcher=lambda *args, **kw: fetched.append(args) or b"")
            worker = feed.refresh_async()
            time.sleep(0.3)
            self.assertEqual(fetched, [])
            self.assertTrue(worker.is_alive())
            released.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(fetched)


class UiIdle(unittest.TestCase):
    class Callback:
        def __init__(self, delays):
            self.delays = list(delays)

        def addCallback(self, ping, data):
            delay = self.delays.pop(0) if self.delays else 0.0
            threading.Timer(delay, ping.notify, (data,)).start()

    def ctx(self, callback):
        smgr = type("Smgr", (), {"createInstanceWithContext": lambda self, name, ctx: callback})()
        return type("Ctx", (), {"ServiceManager": smgr})()

    def test_waits_through_a_busy_ui_thread(self):
        busy = [0.3] * 5  # answers delayed by start-up work
        started = time.monotonic()
        with patch.object(ui_idle, "QUIET", 0.3), patch.object(ui_idle, "PING_GAP", 0.02):
            self.assertTrue(ui_idle.wait(self.ctx(self.Callback(busy))))
        self.assertGreater(time.monotonic() - started, 1.5 + 0.3)

    def test_gives_up_after_the_limit(self):
        with patch.object(ui_idle, "LIMIT", 0.5), patch.object(ui_idle, "PING_GAP", 0.02):
            self.assertFalse(ui_idle.wait(self.ctx(self.Callback([0.2] * 100))))

    def test_without_toolkit_returns_at_once(self):
        self.assertFalse(ui_idle.wait(self.ctx(None)))


if __name__ == "__main__":
    unittest.main()
