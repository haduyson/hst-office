#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""macOS owner scenario (windows-smoke's ui-parity-old-profile): the PUBLISHED beta.5 dmg installed and started once
with the user's default profile, removed (the profile stays), then the build under test installed over that profile.
Its start-up questions must appear (M2 semantics: the welcome may take the first start, the default-apps question
must come on the next) and every Tùy chọn ▸ HST Office page must not be blank.
Usage: mac_old_profile.py --old <beta.5 dmg> --new <dmg under test> --out DIR. Exit 1 on any FAIL."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from mac_access import applications, close_owned, press, texts
from mac_startup import DEFAULT_QUESTION, QUIET, launch
from native import screenshot
from support import wait

APP = Path("/Applications/HST Office.app")
WELCOME = ("Chào mừng", "chào đón")
PIPE = "r1oldprofile"


class Scenario:
    def __init__(self, out):
        self.out, self.rows, self.owned = Path(out), [], set()
        self.out.mkdir(parents=True, exist_ok=True)

    def check(self, name, ok, detail="", shot=None):
        self.rows.append(dict(check=name, status="PASS" if ok else "FAIL", detail=detail, screenshot=shot))
        (self.out / "old-profile-results.json").write_text(json.dumps(self.rows, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
        print(("PASS" if ok else "FAIL") + "  " + name + "  " + str(detail)[:300], flush=True)

    def shot(self, label):
        path = self.out / (label + ".png")
        screenshot(path)
        return path.name

    def install(self, dmg, label):
        """Drag-install as a user does (Gatekeeper is M1's subject, so no quarantine here)."""
        mount = self.out / ("mnt-" + label)
        mount.mkdir()
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount),
                        str(dmg)], **QUIET)
        try:
            subprocess.run(["ditto", "--noqtn", str(mount / "HST Office.app"), str(APP)], **QUIET)
        finally:
            subprocess.run(["hdiutil", "detach", "-force", str(mount)], **QUIET)

    def start(self, label, *args):
        """One start from /Applications; returns (app, texts seen within 60 s once a window shows)."""
        launch(self.out, label, "-a", str(APP), *(("--args",) + args if args else ()))
        def running():
            found = [a for a in applications() if a.executableURL().path().startswith(str(APP) + "/")]
            self.owned.update(a.processIdentifier() for a in found)
            return found[0] if found else None
        app = wait(running, 180)
        app.activateWithOptions_(2)
        seen, end = [], time.monotonic() + 60
        while time.monotonic() < end:
            seen = texts(app)
            if any(DEFAULT_QUESTION in t or any(w in t for w in WELCOME) for t in seen):
                break
            time.sleep(0.5)
        return app, seen

    def answer(self, app, labels):
        try:
            press(app, labels)
            return True
        except RuntimeError:
            return False

    def quit(self, app):
        app.terminate()
        try:
            wait(lambda: app.isTerminated() or None, 30)
        except TimeoutError:
            app.forceTerminate()  # a modal dialog can refuse the quit event
            wait(lambda: app.isTerminated() or None, 20)
        close_owned(self.owned)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("old", "new", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    s = Scenario(args.out)
    if APP.exists() or applications():
        raise SystemExit("Runner phải sạch: đã có HST Office")
    subprocess.run(["defaults", "write", "NSGlobalDomain", "AppleLanguages", "-array", "vi", "en"], **QUIET)
    profile = Path.home() / "Library/Application Support/HSTOffice"
    try:
        s.install(args.old, "old")
        app, seen = s.start("beta5-start")
        s.check("beta.5 starts once with the default profile", bool(seen), seen, s.shot("beta5-start"))
        s.answer(app, {"Đóng", "Close", "Để sau", "Later"})
        s.quit(app)
        shutil.rmtree(APP)
        s.check("beta.5 removed, its profile stays", profile.is_dir() and not APP.exists(),
                sorted(p.name for p in profile.iterdir()) if profile.is_dir() else "no profile")
        s.install(args.new, "new")
        asked, welcomes = None, []
        for start in (1, 2):
            app, seen = s.start(f"new-start{start}")
            shot = s.shot(f"new-start{start}")
            if any(DEFAULT_QUESTION in t for t in seen):
                asked = start
                s.check(f"start {start}: the default-apps question appears", True, seen, shot)
                s.answer(app, {"Để sau", "Later"})
                s.quit(app)
                break
            welcome = any(w in t for t in seen for w in WELCOME)
            welcomes.append(start)
            s.check(f"start {start}: a start-up question appears", welcome and start == 1, seen, shot)
            s.answer(app, {"Đóng", "Close"})
            s.quit(app)
            if not welcome:
                break
        s.check("the default-apps question comes at the first start after the welcome",
                asked is not None and asked == len(welcomes) + 1, dict(asked=asked, welcomes=welcomes))
        app, seen = s.start("options", f"--accept=pipe,name={PIPE};urp;")
        if any(DEFAULT_QUESTION in t or any(w in t for w in WELCOME) for t in seen):
            # nothing is due at this start; a modal question would block the Options dialog
            s.check("no start-up dialog left at the options start", False, seen, s.shot("options-startup"))
            s.answer(app, {"Để sau", "Later", "Đóng", "Close"})
        from launch import interpreter
        python, env = interpreter(APP)
        log = (s.out / "pages.log").open("w", encoding="utf-8")
        try:
            done = subprocess.run([str(python), str(Path(__file__).with_name("mac_options_pages.py")), PIPE,
                                   str(s.out)], env=env, stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, timeout=600)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = "timeout 600 s"
        finally:
            log.close()
        pages = s.out / "pages.json"
        for row in json.loads(pages.read_text(encoding="utf-8")) if pages.exists() else []:
            s.check("options: " + row["check"], row["status"] == "PASS", row["detail"])
        s.check("options pages checked to the end", code == 0 and pages.exists(), dict(exit_code=code, log="pages.log"))
        s.quit(app)
    except Exception as error:
        s.check("scenario ran to the end", False, f"{type(error).__name__}: {error}", s.shot("scenario-failure"))
    finally:
        close_owned(s.owned)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Hồ sơ beta.5 cũ\n\n" + "".join(f"- {r['status']} {r['check']}\n" for r in s.rows))
    return int(not s.rows or any(r["status"] == "FAIL" for r in s.rows))


if __name__ == "__main__":
    raise SystemExit(main())
