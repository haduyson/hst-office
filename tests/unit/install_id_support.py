# SPDX-License-Identifier: AGPL-3.0-only
"""Shared fixtures of the install-ID tests: UNO stubs (set before any hst_office import) and a settings double."""
import os
import sys
import types
from unittest import mock

import _paths


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.document",
              "com.sun.star.frame", "com.sun.star.lang", "com.sun.star.task"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import update_config as cfg  # noqa: E402

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR = "{http://openoffice.org/2001/registry}"
DLG = "{http://openoffice.org/2000/dialog}"
ID = "3f2b8c1e-9a4d-4e6f-8b7a-0c1d2e3f4a5b"


class FakeConfig:
    """update_config.settings/save over a dict, with optional locks and a failing write."""

    def __init__(self, locked=(), writable=True, **values):
        self.values, self.locked, self.writable, self.saves = dict(cfg.DEFAULTS, **values), set(locked), writable, []

    def settings(self, ctx):
        return dict(self.values)

    def load(self, ctx):
        return dict(self.values), set(self.locked)

    def save(self, ctx, name, value):
        if name in self.locked or not self.writable:
            return False
        self.saves.append((name, value))
        self.values[name] = value
        return True

    def patch(self, test):
        for name in ("settings", "load", "save"):
            p = mock.patch.object(cfg, name, getattr(self, name))
            p.start()
            test.addCleanup(p.stop)
        return self
