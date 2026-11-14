# SPDX-License-Identifier: AGPL-3.0-only
"""The GUI harness drives only its own office. When another office already holds a check's UNO port (the same check
running in parallel with its deterministic port), this office's acceptor cannot bind and every UNO call would go to
the other office: its documents, its frames, and finally its termination."""
import os
from urllib.parse import unquote


class ForeignOfficeError(RuntimeError):
    """The UNO port answers, but for another office's profile."""


def ensure_own_office(ctx, workdir, port):
    """Raise ForeignOfficeError unless the office behind ctx runs on the profile under workdir."""
    user = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    theirs = unquote(user.getSubstituteVariableValue("$(user)")).rstrip("/")
    ours = "file://" + os.path.join(workdir, "profile", "user")
    if theirs != ours:
        raise ForeignOfficeError(f"port {port} belongs to another office ({theirs}), not to {ours}: "
                                 "give each parallel run its own port")
