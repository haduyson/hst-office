# SPDX-License-Identifier: AGPL-3.0-only
"""W16: open .xlsx/.ods, .docx/.odt, .pptx/.odp the ways a person does in Explorer and time the document window.

Routes: double click, right click ▸ Open, right click ▸ Open with ▸ HST <app>, and ShellExecuteEx with the verb names
the MSI registers (default, "new"). States: a new profile (first start: welcome dialog), a warm profile with no office
running, an office already running with a document of the same app (document tabs park its window), and an office
whose last document was closed a moment before. The default profile is used, as Explorer's verbs use it.

A route passes when the document's window is shown, enabled (no modal dialog over it) and in front of Explorer within
its limit. The census lists top-level windows in z-order, so a window or a dialog hidden behind Explorer shows in the
data. Runs in the tooling Python; the office is driven only through the shell and real input."""
import json
from pathlib import Path
import re
import shutil
import time

from native import screenshot
from open_routes_fixtures import fixtures
from open_routes_system import default_profile, registration, scrub_recovery
import open_routes_watch as watching
from results import row

APPS = (("sheets", "Sheets", "xlsx", "ods"), ("writer", "Writer", "docx", "odt"), ("slides", "Slides", "pptx", "odp"))
LIMIT_FRESH, LIMIT_WARM = 90, 30
NEW_TITLE = re.compile(r"Untitled|Không tên")


class Routes:
    def __init__(self, install, out, work):
        self.install, self.out, self.work = Path(install), Path(out), Path(work)
        self.docs = self.work / "docs"
        self.docs.mkdir(parents=True, exist_ok=True)
        self.profile = default_profile(install)
        self.rows, self.count = [], 0

    # ---- office lifetime -------------------------------------------------------------------------------------
    def ours(self):
        from open_routes_windows import processes
        found = []
        for proc, info in processes(["name", "exe"]):
            exe = info["exe"] or ""
            if (info["name"] or "").lower() in ("soffice.bin", "soffice.exe") and \
                    exe.lower().startswith(str(self.install).lower()):
                found.append(proc)
        return found

    def close_office(self, limit=45):
        """Close every office window as a person does (WM_CLOSE, Escape on a dialog); kill only what is left."""
        import psutil
        from open_routes_windows import census, close_windows
        started, killed = time.monotonic(), []
        while self.ours() and time.monotonic() - started < limit:
            windows = [w for w in census()[0] if w["proc"] == "soffice.bin" and w["title"]]
            dialogs = [w for w in windows if w["enabled"] and w["owner"]]
            close_windows([w["hwnd"] for w in (dialogs or [w for w in windows if w["enabled"]])])
            time.sleep(2)
        left = self.ours()
        for proc in left:
            try:
                killed.append(dict(pid=proc.pid, name=proc.name(), status=proc.status()))
                proc.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(left, timeout=10)
        if killed:
            scrub_recovery(self.profile)
        return dict(exit_seconds=round(time.monotonic() - started, 1), killed=killed)

    def new_profile(self):
        closed = self.close_office()
        shutil.rmtree(self.profile, ignore_errors=True)
        return closed

    # ---- one route -------------------------------------------------------------------------------------------
    def copy(self, app, ext, tag):
        self.count += 1
        path = self.docs / ("%02d-%s-%s.%s" % (self.count, app, tag, ext))
        shutil.copyfile(self.work / "fixtures" / ("mau." + ext), path)
        return path

    def open_base(self, app, ext):
        from open_routes_explorer import shell_execute
        base = self.copy(app, ext, "base")
        shell_execute(base, None)
        waited = watching.watch(self.out, lambda t: base.name in t or base.stem in t, LIMIT_FRESH,
                                "%02d-base" % self.count)
        return base, waited["status"]

    def route(self, app, label, ext, how, state):
        from open_routes_explorer import Explorer, shell_execute
        from open_routes_windows import Launches, census, close_windows
        record = dict(app=app, ext=ext, route=how, state=state)
        try:
            if state == "fresh":
                record["before"] = self.new_profile()
            elif state == "cold":
                record["before"] = self.close_office()
            base = None
            if state in ("running", "closing"):
                base, record["base"] = self.open_base(app, ext if state == "closing" else
                                                      next(a[3] for a in APPS if a[0] == app))
            path = self.copy(app, ext, how)
            name = "%02d-%s-%s-%s" % (self.count, app, how, state)
            matches = (lambda t: bool(NEW_TITLE.search(t))) if how == "verb-new" else \
                (lambda t, p=path: p.name in t or p.stem in t)
            explorer = None
            if how in ("double-click", "open", "open-with"):
                explorer = Explorer(path).open()
                explorer.center()  # located before the clock starts
            if state == "closing":
                close_windows([w["hwnd"] for w in census()[0] if w["proc"] == "soffice.bin"
                               and base.stem in w["title"]])
                time.sleep(0.3)
            limit = LIMIT_FRESH if state == "fresh" else LIMIT_WARM
            launches = Launches().__enter__()
            started = time.monotonic()
            if how == "double-click":
                record["input"] = explorer.double_click()
                # The shell starting nothing at all means the double-click never reached Explorer as one: no HST
                # process ran, so the office cannot have failed. Seen in 2 of 30 closing routes with launch tracking
                # (r1-auto Windows runs 42947181746 at 100% and 42955213065 at 150%: the closing office exited by
                # 0.8 s as in every passing route, then no launcher for 25 s; in the 28 others a launcher started
                # right after the input). Double-click again and keep the lost input as evidence.
                if not launches.launched(5):
                    record["input_lost"] = record["input"]
                    record["input"] = explorer.double_click()
            elif how == "open":
                record["input"] = explorer.choose("Open")
            elif how == "open-with":
                record["input"] = explorer.open_with("HST " + label)
            else:
                record["input"] = shell_execute(path, None if how == "verb-default" else "new")
            record["input_seconds"] = round(time.monotonic() - started, 1)
            try:
                result = watching.watch(self.out, matches, limit, name)
            finally:
                launches.__exit__()
                record["launches"] = launches.report()
            record.update(result)
            if result["status"] != "OK":
                record["unblock"] = watching.unblock(self.out, matches, name)
            if explorer:
                explorer.close()
        except Exception as error:  # noqa: BLE001 - one broken route must not hide the others
            record.update(status="ERROR", error=f"{type(error).__name__}: {error}",
                          screenshots=[Path(screenshot(self.out / ("%02d-error.png" % self.count))).name])
        self.rows.append(record)
        (self.out / "open-routes.json").write_text(json.dumps(self.rows, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
        unblock = record.get("unblock") or {}
        print("%-7s %-5s %-12s %-8s %-9s %s window=%s dialogs=%s unblock=%s/%s/%s killed=%s" % (
            app, ext, how, state, record.get("status"), record.get("seconds"), record.get("window_seconds"),
            record.get("dialogs"), unblock.get("action"), unblock.get("status"), unblock.get("seconds"),
            (record.get("before") or {}).get("killed")), flush=True)
        return record

    def plan(self):
        """Fresh profile once per app (Sheets: the three Explorer routes), then warm cold starts, a running office
        and an office closing its last document."""
        steps = []
        for app, label, ooxml, odf in APPS:
            fresh = ("double-click", "open", "open-with") if app == "sheets" else \
                ({"writer": "open", "slides": "double-click"}[app],)
            steps += [(app, label, ooxml, how, "fresh") for how in fresh]
            steps += [(app, label, ooxml, how, "cold") for how in
                      ("double-click", "open", "open-with", "verb-default", "verb-new")]
            steps += [(app, label, odf, how, "cold") for how in ("double-click", "open-with")]
            steps += [(app, label, ooxml, how, "running") for how in ("double-click", "open", "open-with")]
            steps += [(app, label, odf, "open-with", "running"), (app, label, ooxml, "double-click", "closing")]
        return steps


def run(install, out, work):
    out, work = Path(out), Path(work)
    out.mkdir(parents=True, exist_ok=True)
    routes = Routes(install, out, work)
    report = dict(registration=registration(), profile=str(routes.profile))
    (out / "registration.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    fixtures(install, work)
    try:
        for step in routes.plan():
            routes.route(*step)
    finally:
        report["final_close"] = routes.close_office()
        (out / "registration.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = ["%s %s %s %s: %s" % (r["app"], r["ext"], r["route"], r["state"], r.get("status"))
              for r in routes.rows if r.get("status") != "OK"]
    shots = sorted(out.glob("*-end.png"))
    shot = shots[-1].relative_to(out.parent).as_posix() if shots else None
    table = ["%s %s %s %s %s %s" % (r["app"], r["ext"], r["route"], r["state"], r.get("status"), r.get("seconds"))
             for r in routes.rows]
    return row("W16", "FAIL" if failed or not shot else "PASS",
               dict(message="Mở tệp từ Explorer: " + ("đạt mọi đường" if not failed else "%d đường chưa đạt"
                                                       % len(failed)), failed=failed, routes=table,
                    evidence="W16/open-routes.json"), shot)
