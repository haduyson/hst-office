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
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

from native import screenshot
from results import row

APPS = (("sheets", "Sheets", "xlsx", "ods"), ("writer", "Writer", "docx", "odt"), ("slides", "Slides", "pptx", "odp"))
LIMIT_FRESH, LIMIT_WARM = 90, 30
NEW_TITLE = re.compile(r"Untitled|Không tên")
NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"')
BODY = {"odt": ("application/vnd.oasis.opendocument.text", "<office:text><text:p>HST</text:p></office:text>"),
        "ods": ("application/vnd.oasis.opendocument.spreadsheet",
                '<office:spreadsheet><table:table table:name="Sheet1"><table:table-row><table:table-cell '
                'office:value-type="string"><text:p>HST</text:p></table:table-cell></table:table-row></table:table>'
                '</office:spreadsheet>'),
        "odp": ("application/vnd.oasis.opendocument.presentation",
                '<office:presentation><draw:page draw:name="p1"><draw:frame svg:x="2cm" svg:y="2cm" svg:width="12cm" '
                'svg:height="3cm"><draw:text-box><text:p>HST</text:p></draw:text-box></draw:frame></draw:page>'
                '</office:presentation>')}


def fixtures(install, work):
    """One small document per format: ODF written here, OOXML converted by the installed office on its own
    throw-away profile (the default profile stays new)."""
    out = Path(work) / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    soffice = Path(install) / "program" / "soffice.exe"
    for ext, (mime, body) in BODY.items():
        path = out / ("mau." + ext)
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), mime)
            z.writestr("META-INF/manifest.xml", '<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                       'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                       '<manifest:file-entry manifest:full-path="/" manifest:media-type="%s" manifest:version="1.3"/>'
                       '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                       '</manifest:manifest>' % mime, zipfile.ZIP_DEFLATED)
            z.writestr("content.xml", '<?xml version="1.0" encoding="UTF-8"?><office:document-content %s '
                       'office:version="1.3"><office:body>%s</office:body></office:document-content>' % (NS, body),
                       zipfile.ZIP_DEFLATED)
    profile = (Path(work) / "convert-profile").resolve().as_uri()
    for odf, ooxml in (("odt", "docx"), ("ods", "xlsx"), ("odp", "pptx")):
        subprocess.run([str(soffice), "--headless", "--norestore", "-env:UserInstallation=" + profile,
                        "--convert-to", ooxml, "--outdir", str(out), str(out / ("mau." + odf))],
                       check=True, capture_output=True, timeout=300, stdin=subprocess.DEVNULL)
        if not (out / ("mau." + ooxml)).is_file():
            raise RuntimeError("Không tạo được tệp mẫu ." + ooxml)
    return out


def painted(rect):
    """The document's content is drawn: a window still loading is one flat colour (the frame is shown before the
    import, loadenv.cxx), a loaded one has the ribbon, rulers or grid."""
    from PIL import ImageGrab
    left, top, right, bottom = rect
    if right - left < 300 or bottom - top < 200:
        return False
    image = ImageGrab.grab(bbox=(left + 8, top + 40, right - 8, bottom - 8), all_screens=True)
    return len(set(image.convert("RGB").resize((160, 90)).getdata())) > 40


def scrub_recovery(profile):
    """After a forced stop: drop the recovery list, so the next start is not a recovery start (that dialog would
    hide every later route's own result)."""
    xcu = Path(profile) / "user" / "registrymodifications.xcu"
    if xcu.is_file():
        lines = xcu.read_text(encoding="utf-8").splitlines(keepends=True)
        xcu.write_text("".join(l for l in lines if "org.openoffice.Office.Recovery" not in l), encoding="utf-8")
    shutil.rmtree(Path(profile) / "user" / "backup", ignore_errors=True)


def default_profile(install):
    """bootstrap.ini UserInstallation of the installed office ($SYSUSERCONFIG = %APPDATA%)."""
    import urllib.parse
    text = (Path(install) / "program" / "bootstrap.ini").read_text(encoding="utf-8", errors="replace")
    raw = re.search(r"^UserInstallation=(.*)$", text, re.M).group(1).strip()
    raw = raw.replace("$SYSUSERCONFIG", Path(os.environ["APPDATA"]).as_uri().removeprefix("file:///"))
    return Path(urllib.parse.unquote(raw.removeprefix("file:///")))


def registration():
    """What Explorer reads for each type: the default ProgID, Open-with ProgIDs, the user's choice and every verb."""
    import winreg
    def value(hive, key, name=""):
        try:
            with winreg.OpenKey(hive, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except OSError:
            return None
    def names(hive, key, values=False):
        try:
            with winreg.OpenKey(hive, key) as handle:
                enum = winreg.EnumValue if values else winreg.EnumKey
                found, i = [], 0
                while True:
                    try:
                        item = enum(handle, i)
                    except OSError:
                        return found
                    found.append(item[0] if values else item)
                    i += 1
        except OSError:
            return []
    out = {}
    for ext in ("xlsx", "ods", "docx", "odt", "pptx", "odp"):
        progids = names(winreg.HKEY_CLASSES_ROOT, "." + ext + r"\OpenWithProgids", values=True)
        default = value(winreg.HKEY_CLASSES_ROOT, "." + ext)
        verbs = {}
        for progid in {p for p in progids + [default] if p and p.lower().startswith("hst")}:
            for verb in names(winreg.HKEY_CLASSES_ROOT, progid + r"\shell"):
                verbs[progid + " " + verb] = value(winreg.HKEY_CLASSES_ROOT, progid + r"\shell\%s\command" % verb)
        out[ext] = dict(default=default, open_with=progids, verbs=verbs, user_choice=value(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.%s\UserChoice"
            % ext, "ProgId"))
    return out


class Routes:
    def __init__(self, install, out, work):
        self.install, self.out, self.work = Path(install), Path(out), Path(work)
        self.docs = self.work / "docs"
        self.docs.mkdir(parents=True, exist_ok=True)
        self.profile = default_profile(install)
        self.rows, self.count = [], 0

    # ---- office lifetime -------------------------------------------------------------------------------------
    def ours(self):
        import psutil
        found = []
        for proc in psutil.process_iter(["name", "exe"]):
            exe = proc.info["exe"] or ""
            if (proc.info["name"] or "").lower() in ("soffice.bin", "soffice.exe") and \
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

    # ---- measuring -------------------------------------------------------------------------------------------
    def watch(self, matches, limit, label):
        """Poll the census until the document window is shown, enabled and in front of Explorer, or the limit."""
        from open_routes_windows import census, office_processes, dismiss_system_notices
        start, timeline, last, shots, result, first_window = time.monotonic(), [], None, [], None, None
        marks = [2, 10, 25, 60]
        while True:
            now = round(time.monotonic() - start, 1)
            windows, fg = census()
            dismiss_system_notices()
            office = [w for w in windows if w["proc"] == "soffice.bin" and w["title"]]
            explorer_z = min([w["z"] for w in windows if w["cls"] == "CabinetWClass"] or [10 ** 6])
            doc = next((w for w in office if matches(w["title"]) and not w["owner"]), None)
            state = (tuple((w["title"], w["enabled"], w["z"] < explorer_z) for w in office), fg["title"])
            if state != last:
                timeline.append(dict(t=now, office=[dict(title=w["title"], cls=w["cls"], enabled=w["enabled"],
                                                         above_explorer=w["z"] < explorer_z, owner=bool(w["owner"]),
                                                         iconic=w["iconic"]) for w in office],
                                     foreground=fg, processes=office_processes()))
                last = state
            if marks and now >= marks[0]:
                marks.pop(0)
                shots.append(screenshot(self.out / ("%s-%02ds.png" % (label, int(now)))))
            if doc and first_window is None:
                first_window = now
            front = doc and not doc["iconic"] and (doc["z"] < explorer_z or fg["proc"] == "soffice.bin")
            if front and doc["enabled"] and painted(doc["rect"]):
                result = dict(status="OK", seconds=now, window_seconds=first_window, title=doc["title"],
                              foreground=fg["title"], doc_is_foreground=fg["hwnd"] == doc["hwnd"])
                break
            if now >= limit:
                dialogs = [w["title"] for w in office if not matches(w["title"])]
                status = ("BLOCKED" if doc and not doc["enabled"] else "BEHIND" if doc and not front else
                          "BLANK" if doc else "DIALOG" if dialogs else "NO WINDOW")
                result = dict(status=status, seconds=None, window_seconds=first_window,
                              office_windows=[w["title"] for w in office],
                              dialogs=dialogs, foreground=fg["title"], processes=office_processes())
                break
            time.sleep(0.4)
        shots.append(screenshot(self.out / ("%s-end.png" % label)))
        result["timeline"] = timeline
        result["screenshots"] = [Path(s).name for s in shots]
        return result

    def unblock(self, matches, label):
        """After a failed wait: bring the office's own dialog (or the document) forward, press Escape, wait again;
        tells whether a person who finds the dialog gets the document."""
        from open_routes_windows import census, bring_to_front, close_windows
        office = [w for w in census()[0] if w["proc"] == "soffice.bin" and w["title"]]
        target = next((w for w in office if w["enabled"] and not matches(w["title"])), None) or \
            next((w for w in office), None)
        if target is None:
            return dict(action="nothing to bring forward")
        if matches(target["title"]):
            bring_to_front(target["hwnd"])
            action = "front " + target["title"]
        else:
            close_windows([target["hwnd"]])  # the dialog's own close button, no focus needed
            action = "close " + target["title"]
        again = self.watch(matches, 45, label + "-after")
        return dict(action=action, status=again["status"], seconds=again["seconds"],
                    timeline=again["timeline"][-3:], screenshots=again["screenshots"])

    # ---- one route -------------------------------------------------------------------------------------------
    def copy(self, app, ext, tag):
        self.count += 1
        path = self.docs / ("%02d-%s-%s.%s" % (self.count, app, tag, ext))
        shutil.copyfile(self.work / "fixtures" / ("mau." + ext), path)
        return path

    def open_base(self, app, ext):
        from open_routes_windows import shell_execute
        base = self.copy(app, ext, "base")
        shell_execute(base, None)
        waited = self.watch(lambda t: base.name in t or base.stem in t, LIMIT_FRESH, "%02d-base" % self.count)
        return base, waited["status"]

    def route(self, app, label, ext, how, state):
        from open_routes_windows import Explorer, shell_execute, census, close_windows
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
            started = time.monotonic()
            if how == "double-click":
                record["input"] = explorer.double_click()
            elif how == "open":
                record["input"] = explorer.choose("Open")
            elif how == "open-with":
                record["input"] = explorer.open_with("HST " + label)
            else:
                record["input"] = shell_execute(path, None if how == "verb-default" else "new")
            record["input_seconds"] = round(time.monotonic() - started, 1)
            result = self.watch(matches, limit, name)
            record.update(result)
            if result["status"] != "OK":
                record["unblock"] = self.unblock(matches, name)
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
