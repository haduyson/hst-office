# SPDX-License-Identifier: AGPL-3.0-only
"""Stand-in uno/unohelper/com.sun.star modules so extension modules import outside the office (import this first).

setdefault keeps the real modules when the office python is on the path."""
import sys
import types


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.task",
              "com.sun.star.awt"):
    sys.modules.setdefault(_name, _StubModule(_name))
