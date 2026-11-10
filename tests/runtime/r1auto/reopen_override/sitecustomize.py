# SPDX-License-Identifier: AGPL-3.0-only
"""Throwaway probe: load the checkout's fixed hst_office modules into the shipped office (no change to the signed
bundle) and log the quit. Put on the office's PYTHONPATH with `open --env`."""
import importlib.abc
import importlib.util
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.expanduser("~/hst-reopen-probe.log")
FILES = {"hst_office.update_launch": "fixed_update_launch.py", "hst_office.mac_app_location": "fixed_mac_app_location.py"}


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write("%s pid=%d %s\n" % (time.strftime("%H:%M:%S"), os.getpid(), message))


class Override(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name in FILES:
            log("override " + name)
            return importlib.util.spec_from_file_location(name, os.path.join(HERE, FILES[name]))
        return None


import sys  # noqa: E402
sys.meta_path.insert(0, Override())
log("sitecustomize loaded")
