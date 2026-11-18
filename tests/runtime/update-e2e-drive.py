#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Drive "Cập nhật ngay" end to end in a real, installed HST Office (Linux and Windows; macOS: scripts/macos).

  <office python> update-e2e-drive.py --soffice <program/soffice[.exe]> --profile <dir> --out <report.json>
        [--document <file>] [--code <python dir>] [--pretend <release>] [--answer auto] [--watch S] [--relaunch-wait S]

Run with the installed office's own Python (it has the uno module). The office starts with a probe profile, a document
and a UNO socket; update_e2e_macro.py is placed in the profile and dispatches org.hst.office.update:Install on the
document, as the infobar button does. The signed manifest is the published one (read only); the installer must
already wait verified in the user's update cache, so nothing is downloaded. --pretend reports an older release to the
check, so that an up-to-date office is offered the published release; --installer skips the manifest and installs
that local file (any release, e.g. a test build) through the same helper; --code imports hst_office from this checkout
instead of the office's own extension. The report says whether the office quit, what the helper logged, and whether
an office process started again after it (the relaunch). Exit 0 when the office quit and an office came back.
"""
import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS = platform.system() == "Windows"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def office_pids():
    """PIDs of running soffice.bin processes of this user."""
    if WINDOWS:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq soffice.bin"],
                             capture_output=True, text=True).stdout
        return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"soffice.bin"')}
    out = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "soffice.bin"], capture_output=True, text=True).stdout
    return {int(pid) for pid in out.split()}


def alive(pid):
    return pid in office_pids()


def events_of(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def install_macro(profile, args):
    scripts = os.path.join(profile, "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    with open(os.path.join(HERE, "update_e2e_macro.py"), encoding="utf-8") as handle:
        text = handle.read()
    marker = "\nARGS = {}\n"
    if marker not in text:
        raise SystemExit("update_e2e_macro.py has no ARGS line")
    text = text.replace(marker, "\nARGS = json.loads(%r)\n" % json.dumps(args), 1)
    with open(os.path.join(scripts, "hst_update_e2e.py"), "w", encoding="utf-8") as handle:
        handle.write(text)


def office_env():
    """The environment of the user, without what the office's python wrapper exported for this driver: an office
    started with another copy's URE_BOOTSTRAP or PYTHONHOME (an AppImage, say) would not start."""
    drop = ("URE_BOOTSTRAP", "UNO_PATH", "PYTHONPATH", "PYTHONHOME")
    return {k: v for k, v in os.environ.items() if k not in drop}


def init_profile(soffice, url):
    """A fresh profile asks for one restart (exit 81) at its first start: repeat until it exits cleanly."""
    for _ in range(3):
        if subprocess.run([soffice, "--headless", "--norestore", "--terminate_after_init", "-env:UserInstallation=" + url],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
                          env=office_env()).returncode == 0:
            return


def quiet_start(profile, welcome):
    """No tip or default-app question (and no welcome unless asked): a modal dialog on a window made the quit of
    releases up to 1.0.2 fail at once; --keep-welcome checks that newer ones close it first."""
    path = os.path.join(profile, "user", "registrymodifications.xcu")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    item = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % entry for entry in (
        ("/org.hasontech.hstoffice.Welcome", "Shown", "false" if welcome else "true"),
        ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false")))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace("</oor:items>", item + "</oor:items>"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--soffice", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--document", default="")
    p.add_argument("--code", default="")
    p.add_argument("--pretend", default="")
    p.add_argument("--answer", default="auto", choices=("auto", "dialog"))
    p.add_argument("--keep-welcome", action="store_true", help="let the welcome dialog open at the start")
    p.add_argument("--close-welcome", action="store_true", help="close the welcome dialog before the update command")
    p.add_argument("--installer", default="", help="local installer instead of the published manifest's")
    p.add_argument("--to", default="9.9.9", help="release of --installer")
    p.add_argument("--watch", type=int, default=600, help="seconds for the office to quit")
    p.add_argument("--relaunch-wait", type=int, default=180, help="seconds after the quit for an office to come back")
    a = p.parse_args()
    import uno
    profile = os.path.abspath(a.profile)
    url = uno.systemPathToFileUrl(profile)
    init_profile(a.soffice, url)
    quiet_start(profile, a.keep_welcome)
    events = os.path.abspath(a.out) + ".events.jsonl"
    open(events, "w").close()
    install_macro(profile, {"events": events, "code": a.code, "pretend": a.pretend,
                            "answer": "auto" if a.answer == "auto" else "", "to": a.to, "close_welcome": a.close_welcome,
                            "installer": os.path.abspath(a.installer) if a.installer else "",
                            "sha256": sha256(a.installer) if a.installer else ""})
    port = free_port()
    before = office_pids()
    argv = [a.soffice, "-env:UserInstallation=" + url, "--norestore", "--nologo",
            "--accept=socket,host=127.0.0.1,port=%d;urp;" % port] + ([a.document] if a.document else [])
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=office_env(),
                     **({"creationflags": 0x08000000} if WINDOWS else {"start_new_session": True}))
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(240):
        try:
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
            break
        except Exception:  # noqa: BLE001 - not listening yet
            time.sleep(1)
    if ctx is None:
        raise SystemExit("the office did not open its UNO socket")
    time.sleep(20)  # the document window and the start-up jobs settle
    factory = ctx.ServiceManager.createInstanceWithContext("com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
    script = factory.createScriptProvider("").getScript("vnd.sun.star.script:hst_update_e2e.py$run?language=Python&location=user")
    report = {"soffice": a.soffice, "code": a.code or "installed", "pretend": a.pretend, "invoke": str(script.invoke((), (), ())[0])}
    pid = None
    for _ in range(30):
        pid = next((e["pid"] for e in events_of(events) if e["event"] == "loaded"), None)
        if pid:
            break
        time.sleep(1)
    report["office_pid"] = pid
    started, quit_after, relaunched = time.monotonic(), None, []
    while pid and time.monotonic() - started < a.watch:
        if not alive(pid):
            quit_after = round(time.monotonic() - started, 1)
            break
        if any(e["event"] in ("helper-cancelled", "dispatch-error") for e in events_of(events)):
            time.sleep(10)  # the office stays open: nothing more will happen
            break
        time.sleep(1)
    report["office_quit_after_s"] = quit_after
    if quit_after is not None:
        deadline = time.monotonic() + a.relaunch_wait
        while time.monotonic() < deadline and not relaunched:
            relaunched = sorted(office_pids() - before - {pid})
            time.sleep(2)
    report["relaunched_pids"] = relaunched
    report["events"] = events_of(events)
    with open(a.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if quit_after is not None and relaunched else 1


if __name__ == "__main__":
    sys.exit(main())
