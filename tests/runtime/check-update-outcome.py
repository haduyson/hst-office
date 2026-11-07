#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the message after a failed "Cập nhật ngay" in a real HST Office (soffice runs as hstbuild).

Usage: python3 tests/runtime/check-update-outcome.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/update-outcome] [--shots tests/output/screenshots-update-outcome] [--display :87]
           [--uno-port N] [--http-port N]   (default: free ports; formerly 22095 and 22096)

  1. The real helper script runs with a stub pkexec that answers "not authorized" (127), writes update-result.json and
     relaunches the office; the relaunched office shows the message once, "Tải về" opens the browser (stub xdg-open),
     and the file is gone. The next start shows nothing.
  2. Cancel at the save prompt after "Cập nhật ngay": the office stays open, the helper stops without relaunching and
     without a record (dry-run helper, local manifest as in check-update-install.py).
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import hashlib
import http.server
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
_spec = importlib.util.spec_from_file_location("install", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-update-install.py"))
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)
notify = install.notify
check = install.check
sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
from hst_office import update_helper_cmd as cmd  # noqa: E402
from hst_office import update_launch as launch  # noqa: E402

UNO_PORT, HTTP_PORT = 0, 0  # set by main (also in check-update-install, whose manifest names the HTTP port)
TITLE = install.TITLE


def stub(path, body):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def installed_release(instdir):
    path = os.path.join(instdir, "share", "extensions", notify.EXT, "data", "release.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["release"]


def run_failed_install(instdir, args):
    work = os.path.join(args.out, "failed")
    shutil.rmtree(work, ignore_errors=True)
    bin_dir, cache = os.path.join(work, "bin"), os.path.join(work, "cache", "hst-office", "update")
    os.makedirs(bin_dir)
    os.makedirs(cache)
    browser_log = os.path.join(work, "xdg-open.log")
    stub(os.path.join(bin_dir, "pkexec"), "exit 127\n")
    stub(os.path.join(bin_dir, "apt-get"), "exit 0\n")
    stub(os.path.join(bin_dir, "xdg-open"), f'echo "$@" >> "{browser_log}"\n')
    env = {"XDG_CACHE_HOME": os.path.join(work, "cache"), "PATH": bin_dir + ":" + os.environ["PATH"]}
    office = hst_gui.Office(instdir, work, UNO_PORT, display=args.display, nodefault=False, env=env,
                            config=[("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")])
    office.start()
    time.sleep(3)
    office.stop()

    package = os.path.join(cache, "HSTOffice_9.9.9_Linux_x86-64.deb")
    with open(package, "wb") as handle:
        handle.write(b"dummy")
    # The relaunch of the real helper reopens this profile: a wrapper around the same soffice command line.
    wrapper = os.path.join(bin_dir, "soffice")
    profile = os.path.join(work, "profile")
    environment = " ".join(f"{k}='{v}'" for k, v in dict(office._env(), **env).items() if k.isidentifier() and "'" not in v)
    stub(wrapper, f"exec env {environment} '{os.path.join(office.program, 'soffice')}' '-env:UserInstallation=file://{profile}' "
                  f"--norestore --nologo '--accept=socket,host=127.0.0.1,port={UNO_PORT};urp;'\n")
    helper = cmd.build_helper("Linux", pid=2147483000, installer=package, soffice=wrapper, log=launch.log_path(cache),
                              sha256=hashlib.sha256(b"dummy").hexdigest(), release_from=installed_release(instdir), release_to="9.9.9")
    script = launch.write_helper(helper, cache)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, work], check=True)
    run = subprocess.run(["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "PATH=" + env["PATH"], "HOME=" + os.path.join(work, "home")]
                         + cmd.argv(helper, script), check=False, timeout=60)
    check("helper exits with pkexec's code", run.returncode == 127)
    state = os.path.join(cache, "update-result.json")
    try:
        check("relaunched office shows the message", notify.wait(lambda: install.dialogs(office, TITLE), 120))
        time.sleep(1.5)
        hst_gui.screenshot(os.path.join(args.shots, "01-failed-install-message.png"), args.display)
        check("the record is consumed before the message", not os.path.exists(state))
        check("the failed package stays for a later try", os.path.isfile(package))
        # message box: 300 x 88, first button "Tải về" at x 8..52, y 68..82
        install.click(office, TITLE, 30 / 300.0, 75 / 88.0)
        check("Tải về opens the browser", notify.wait(lambda: os.path.isfile(browser_log), 20))
        check("the message closes", notify.wait(lambda: not install.dialogs(office, TITLE), 10))
        office.ctx = office._connect()
    finally:
        office.stop()
    office.proc = None
    office.start(fresh=False)
    try:
        time.sleep(8)
        check("next start shows nothing", not install.dialogs(office, TITLE))
    finally:
        office.stop()


def run_cancel_at_save_prompt(instdir, srv, args):
    work = os.path.join(args.out, "cancel")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    env = {"HST_UPDATE_TEST_URL": "http://127.0.0.1:%d/latest.json" % HTTP_PORT, "HST_UPDATE_DRY_RUN": "1",
           "XDG_CACHE_HOME": os.path.join(work, "cache")}
    install.serve_manifest(srv)
    office = hst_gui.Office(instdir, work, UNO_PORT, display=args.display, nodefault=False, env=env)
    log = os.path.join(work, "cache", "hst-office", "update", "update.log")
    try:
        office.start()
        doc = office.load("private:factory/swriter")
        doc.getText().setString("chưa lưu")
        frame = doc.getCurrentController().getFrame()
        install.dispatch_async(office, frame, "org.hst.office.update:Install")
        check("question after download", notify.wait(lambda: install.dialogs(office, TITLE), 90))
        install.click(office, TITLE, 44.5 / 300.0, 51 / 64.0)  # "Cập nhật ngay"
        check("helper started", notify.wait(lambda: os.path.isfile(log), 20))
        time.sleep(3)
        hst_gui.screenshot(os.path.join(args.shots, "02-save-prompt.png"), args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=args.display), check=False, timeout=10)
        check("helper stopped", notify.wait(lambda: "Stopped before installing" in open(log, encoding="utf-8").read(), 30))
        text = open(log, encoding="utf-8").read()
        print(text, flush=True)
        check("office stays open", office.pid is not None)
        check("no relaunch", "relaunch" not in text.lower())
        check("no record", not os.path.exists(os.path.join(os.path.dirname(log), "update-result.json")))
        doc.setModified(False)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "update-outcome"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests", "output", "screenshots-update-outcome"))
    parser.add_argument("--display", default=":87")
    install.add_port_options(parser, 22095, 22096)
    args = parser.parse_args()
    global UNO_PORT, HTTP_PORT
    UNO_PORT, HTTP_PORT = install.ports(args)
    install.UNO_PORT, install.HTTP_PORT = UNO_PORT, HTTP_PORT
    args.out = os.path.abspath(args.out)
    os.makedirs(args.shots, exist_ok=True)
    srv = os.path.join(args.out, "srv")
    os.makedirs(srv, exist_ok=True)
    instdir = notify.prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), notify.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        run_failed_install(instdir, args)
        run_cancel_at_save_prompt(instdir, srv, args)
    finally:
        server.shutdown()
        server.server_close()
    failed = [label for label, ok in install.RESULTS if not ok]
    print("update outcome runtime: %d checks, %d failed%s" % (len(install.RESULTS), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
