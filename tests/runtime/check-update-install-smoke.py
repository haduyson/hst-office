#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke test of "Cập nhật ngay" without an office, for any OS (used by the Windows smoke workflow).

Serves a manifest signed with a throw-away test key and a dummy installer from 127.0.0.1, downloads it through
update_prepare.prepare (signature, size and SHA256 checks), then builds the helper for this operating system and runs it
in dry-run mode: the log must show the exact installer command line (msiexec /i ... /passive on Windows) and the relaunch,
and nothing is installed. Run with plain `python -I tests/runtime/check-update-install-smoke.py`. Exit 1 on any failure.
"""
import hashlib
import os
import platform
import subprocess
import sys
import tempfile
import time
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
sys.path.insert(0, os.path.join(ROOT, "tests", "unit"))
import test_update_prepare as fixtures  # noqa: E402
from hst_office import ed25519  # noqa: E402
from hst_office import update_helper_cmd as cmd  # noqa: E402
from hst_office import update_launch as launch  # noqa: E402
from hst_office import update_logic as logic  # noqa: E402
from hst_office import update_prepare as prep  # noqa: E402

SYSTEM = platform.system()
SUFFIX = {"Windows": ".msi", "Darwin": ".dmg"}.get(SYSTEM, ".deb")
FAILED = []


def check(label, ok, detail=""):
    print("%s  %s %s" % ("PASS" if ok else "FAIL", label, detail), flush=True)
    if not ok:
        FAILED.append(label)


def main():
    key = logic.platform_key(SYSTEM, platform.machine())
    name = "HSTOffice_9.9.9_smoke" + SUFFIX
    body = b"dummy installer " * 5000
    server = fixtures.Server()
    server.files["/files/" + name] = body
    entry = {key: {"url": server.base + "/files/" + name, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}}
    server.publish(entry)
    cache = tempfile.mkdtemp()
    env = {"HST_UPDATE_TEST_URL": server.base + "/latest.json", "XDG_CACHE_HOME": cache, "LOCALAPPDATA": cache, "HOME": cache}
    info = {"release": "1.0.0-beta.3", "channel": "beta", "test_mode": True}
    try:
        with mock.patch.object(logic, "PUBLIC_KEY", ed25519.secret_to_public(fixtures.SEED)):
            result = prep.prepare(info, environ=env, system=SYSTEM, machine=platform.machine())
        check("download, signature, size and SHA256 verified", os.path.isfile(result["path"]), result["path"])
        log = launch.log_path(os.path.dirname(result["path"]))
        soffice = os.path.join(cache, "soffice.exe" if SYSTEM == "Windows" else "soffice")
        helper = cmd.build_helper(SYSTEM, pid=2147483000, installer=result["path"], sha256=result["entry"]["sha256"], soffice=soffice,
                                  log=log, dry_run=True, app_dest=os.path.join(cache, "HST Office.app"))
        script = launch.write_helper(helper, cache)
        argv = cmd.argv(helper, script)
        print("helper argv:", argv, flush=True)
        done = subprocess.run(argv, timeout=120, stdin=subprocess.DEVNULL)
        text = open(log, encoding="utf-8-sig", errors="replace").read() if os.path.isfile(log) else ""
        print(text, flush=True)
        check("helper dry run exits 0", done.returncode == 0, "exit %d" % done.returncode)
        expected = {"Windows": "msiexec.exe /i", "Darwin": "--swap", "Linux": "install"}[SYSTEM]
        check("helper logged the installer command", "DRYRUN install:" in text and expected in text)
        check("helper logged the relaunch", "DRYRUN relaunch" in text)
        check("dry run installed nothing and kept the file", os.path.isfile(result["path"]))
        with mock.patch.object(logic, "PUBLIC_KEY", ed25519.secret_to_public(fixtures.SEED)):
            server.publish({key: dict(entry[key], sha256="0" * 64)})
            try:
                prep.prepare(info, environ=env, system=SYSTEM, machine=platform.machine())
                check("wrong SHA256 is refused", False)
            except prep.PrepareError as exc:
                check("wrong SHA256 is refused", exc.code == "err_verify")
    finally:
        server.httpd.shutdown()
        server.httpd.server_close()
    print("update install smoke: %d failed" % len(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
