#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The welcome dialog stays closed after "Không hiển thị lại" even when a start loses the extension's settings.

Usage: python3 tests/runtime/check-startup-choices-survive.py --instdir <instdir> [--out tests/output/startup-choices]
           [--display :97]

configmgr skips the user values of a bundled extension's schema when it reads registrymodifications.xcu before the
profile's extension registration cache lists that schema, and the next settings write drops them. A start whose
cache is gone (removed, or left without the HST schemas by a start ended while the extensions were registered again
after an update) is such a start. The check: a fresh profile shows the welcome dialog, it is closed with the tick
left on, the office quits; user/extensions is removed; the next two starts must not show the dialog again. Exit 1
when a check fails. The X display must already run; the office runs as the build user when started as root.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
from hst_gui_profile import BUILD_USER, _as_user_prefix  # noqa: E402
from hst_gui_x11 import send_close_request, toplevels, window_pid  # noqa: E402
from recovery_runtime import record, summary  # noqa: E402

WELCOME = re.compile(r"Chào mừng|chào đón bạn|Welcome to")


class Starts:
    """Starts of one profile, each ended by closing its windows as the title-bar X does."""

    def __init__(self, instdir, out, display):
        self.soffice = os.path.join(os.path.abspath(instdir), "program", "soffice")
        self.profile = os.path.join(out, "profile")
        self.home = os.path.join(out, "home")
        self.display = display

    def user(self, *parts):
        return os.path.join(self.profile, "user", *parts)

    def pids(self):
        out = subprocess.run(["pgrep", "-f", "soffice.bin.*UserInstallation=file://" + self.profile],
                             capture_output=True, text=True).stdout.split()
        return [int(pid) for pid in out]

    def windows(self):
        mine = set(self.pids())
        return [(wid, name) for wid, name in toplevels(self.display) if window_pid(wid, self.display) in mine]

    def wait_welcome(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            found = [wid for wid, name in self.windows() if WELCOME.search(name)]
            if found:
                return found[0]
            time.sleep(0.5)
        return None

    def run(self, close_welcome, timeout):
        """One start; returns whether the welcome dialog appeared (it is closed with its Close button)."""
        os.makedirs(self.home, exist_ok=True)
        if os.geteuid() == 0:
            subprocess.run(["chown", "-R", BUILD_USER, os.path.dirname(self.profile)], check=True)
        env = dict(os.environ, DISPLAY=self.display, HOME=self.home, SAL_USE_VCLPLUGIN="gtk3")
        proc = subprocess.Popen(_as_user_prefix() + [self.soffice, "--nologo", "--norestore",
                                "-env:UserInstallation=file://" + self.profile], env=env)
        wid = self.wait_welcome(timeout)
        if wid and close_welcome:
            time.sleep(1)
            self.click_close(wid)
        time.sleep(3)
        end = time.time() + 60
        while self.pids() and time.time() < end:
            for window, _name in self.windows():
                send_close_request(window, self.display)
            time.sleep(2)
        for pid in self.pids():
            subprocess.run(["kill", "-9", str(pid)], check=False)
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
        return wid is not None

    def click_close(self, wid):
        info = subprocess.run(["xwininfo", "-display", self.display, "-id", wid], capture_output=True, text=True).stdout
        width = int(re.search(r"Width: (\d+)", info).group(1))
        height = int(re.search(r"Height: (\d+)", info).group(1))
        subprocess.run(["xdotool", "mousemove", "--window", wid, str(width - 70), str(height - 34), "click", "1"],
                       env=dict(os.environ, DISPLAY=self.display), check=False, timeout=10)

    def choices(self):
        try:
            with open(self.user("hst-office", "startup-choices.json"), encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def configured_shown(self):
        try:
            with open(self.user("registrymodifications.xcu"), encoding="utf-8") as handle:
                return "org.hasontech.hstoffice.Welcome" in handle.read()
        except OSError:
            return False

    def session_starts(self):
        try:
            with open(self.user("hst-office", "hst-office.log"), encoding="utf-8") as handle:
                return handle.read().count("session: start")
        except OSError:
            return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "tests", "output",
                                                  "startup-choices"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(args.out)
    office = Starts(args.instdir, os.path.abspath(args.out), args.display)
    record("a fresh profile shows the welcome dialog", office.run(True, 180))
    record("closing it with the tick on stores the answer in the profile file",
           office.choices().get("welcome_shown") is True, office.choices())
    record("the next start does not show it", not office.run(True, 40))
    shutil.rmtree(office.user("extensions"))  # the start below reads the settings without the HST schemas
    before = office.session_starts()
    shown = office.run(True, 60)
    record("the extension ran in the start without the registration cache", office.session_starts() > before)
    # the case under test happened: the value is gone from registrymodifications.xcu (an unfixed office shows the
    # dialog again instead, which writes it back)
    record("that start lost the configuration value", shown or not office.configured_shown())
    record("the welcome dialog stays closed after the configuration value was lost", not shown)
    record("and at the start after", not office.run(True, 40))
    return summary("startup choices runtime")


if __name__ == "__main__":
    sys.exit(main())
