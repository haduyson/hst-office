# SPDX-License-Identifier: AGPL-3.0-only
"""M1/M2: quarantine, Finder-style DMG launch, actual move and relaunch."""
from pathlib import Path
import subprocess
import time
from mac_access import applications, close_owned, ended, confirm_download, press, texts
from native import screenshot
from results import row
from support import wait

DEFAULT_QUESTION = "Mở tài liệu văn phòng bằng HST Office"
WELCOME = ("Chào mừng bạn", "chào đón bạn")  # dialog heading and title; the Start Center says "Chào mừng đến"


def asks(seen):
    """The default-apps question: its text, or its window titled exactly "HST Office" (System Events reads VCL
    dialogs' titles only; the Start Center's window has no name), as check-windows-startup-prompts.py decides."""
    return any(DEFAULT_QUESTION in t or t == "WINDOW: HST Office" for t in seen)


def greets(seen):
    return any(w in t for t in seen for w in WELCOME)
QUIET = dict(check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)


def launch(out, name, *args):
    """`open` waits for the Gatekeeper answer; never block on it, the caller answers the prompt while polling."""
    log = (Path(out) / (name + "-open.log")).open("w", encoding="utf-8")
    return subprocess.Popen(["open", *args], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


def prepare(dmg, out, record):
    import ApplicationServices as ax
    if not ax.AXIsProcessTrusted():
        raise RuntimeError("Runner chưa cấp quyền Trợ năng cho Python; không quan sát được câu hỏi")
    out = Path(out)
    mount = out.parent / "r1-mounted"
    mount.mkdir()
    destination = Path("/Applications/HST Office.app")
    if destination.exists() or applications():
        raise RuntimeError("Runner phải sạch: đã có HST Office hoặc tiến trình đang chạy")
    # Do not seed/mask startup state. Inspect all HST profile locations in this real account.
    support = Path.home() / "Library/Application Support"
    existing = [p for p in support.glob("*") if p.name.lower().startswith("hst")]
    if existing:
        raise RuntimeError("Runner đã có profile HST; không phải lần mở đầu")
    subprocess.run(["defaults", "write", "NSGlobalDomain", "AppleLanguages", "-array", "vi", "en"], **QUIET)
    quarantine = f"0081;{int(time.time()):x};Safari;"
    subprocess.run(["xattr", "-w", "com.apple.quarantine", quarantine, str(dmg)], **QUIET)
    actual = subprocess.run(["xattr", "-p", "com.apple.quarantine", str(dmg)], text=True, **QUIET).stdout.strip()
    subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount), str(dmg)],
                   **QUIET)
    owned, first_ok, openers = set(), False, []
    try:
        source = mount / "HST Office.app"
        if not source.exists():
            raise RuntimeError("Không tìm thấy ứng dụng trong DMG")
        def observe(running):
            # A translocated soffice restarts itself while settling its profile, and macOS asks again.
            if confirm_download(out):
                confirmation.append("M1-download-confirmation.png")
            return texts(running)
        openers.append(launch(out, "M1", "-n", "-a", str(source)))
        confirmation = []
        def launched():
            app = next(iter(applications()), None)
            if app is None and confirm_download(out):
                confirmation.append("M1-download-confirmation.png")
            return app
        app = wait(launched, 300)  # "Verifying…" of a quarantined bundle can take minutes
        owned.add(app.processIdentifier())
        (out / "startup-pids.txt").write_text("\n".join(map(str, owned)))
        app.activateWithOptions_(2)
        seen = wait(lambda: observe(app), 60)
        end = time.monotonic() + 60
        while time.monotonic() < end and not any("Chuyển HST Office" in text for text in seen):
            if (asks(seen) or greets(seen)):
                break
            time.sleep(0.3)
            seen = observe(app)
        path = app.executableURL().path()
        shot = out / "M1-dmg.png"
        screenshot(shot)
        first_ok = ("/AppTranslocation/" in path and any("Chuyển HST Office" in text for text in seen)
                    and not (asks(seen) or greets(seen)))
        record(row("M1", "PASS" if first_ok else "FAIL", dict(message="Câu hỏi chuyển ứng dụng phải hiện đầu tiên",
                   quarantine=actual, executable=path, windows=seen, os_confirmation=confirmation), shot.name))
        if not first_ok:
            raise AssertionError("M1 không đạt; giữ quarantine và không bỏ qua cơ chế bảo vệ")
        press(app, {"Chuyển"})
        wait(destination.exists, 180)
        # The product's own copy (no ditto); it should quit and reopen from /Applications by itself. The owner's
        # step is "rồi mở lại từ Applications": when it does not within 90 s, record that and reopen like the owner.
        def moved():
            if confirm_download(out):
                confirmation.append("M1-download-confirmation.png")
            for candidate in applications():
                owned.add(candidate.processIdentifier())
                (out / "startup-pids.txt").write_text("\n".join(map(str, owned)))
                if candidate.executableURL().path().startswith(str(destination) + "/"):
                    return candidate
            return None
        try:
            moved_app, auto_reopen = wait(moved, 90), True
        except TimeoutError:
            auto_reopen = False
            screenshot(out / "M2-no-reopen.png")
            for left in applications():  # the translocated copy that did not quit
                left.terminate()
                try:
                    wait(lambda: ended(left), 20)
                except TimeoutError:
                    left.forceTerminate()
            openers.append(launch(out, "M2", "-a", str(destination)))
            moved_app = wait(moved, 180)
        moved_app.activateWithOptions_(2)
        # One modal question per start (startup_prompts.py): the welcome may take the first start from
        # /Applications; the default-apps question must then come on the next start, never later.
        seen, starts = wait(lambda: observe(moved_app), 60), 1
        end = time.monotonic() + 60
        while time.monotonic() < end and not asks(seen):
            if starts == 1 and greets(seen):
                moved_app.terminate()  # a modal welcome can refuse the quit event: force it after 20 s
                try:
                    wait(lambda: ended(moved_app), 20)
                except TimeoutError:
                    moved_app.forceTerminate()
                    wait(lambda: ended(moved_app), 20)
                openers.append(launch(out, "M2", "-a", str(destination)))
                moved_app, starts = wait(moved, 90), 2
                moved_app.activateWithOptions_(2)
                end = time.monotonic() + 60
            time.sleep(0.3)
            seen = observe(moved_app)
        shot = out / "M2-applications.png"
        screenshot(shot)
        ok = asks(seen)
        # The product must reopen itself from /Applications (update_launch.py); the owner-style reopen above is only
        # a fallback so M3 can still run, never a pass.
        message = ("Sau chuyển mới hỏi mở tài liệu văn phòng" if auto_reopen else
                   "Sau khi chuyển, HST Office không tự mở lại từ Applications (đã mở thay để chạy M3)")
        record(row("M2", "PASS" if ok and auto_reopen else "FAIL", dict(message=message,
                   executable=moved_app.executableURL().path(), starts=starts, windows=seen,
                   product_reopened_itself=auto_reopen,
                   os_confirmation=confirmation), shot.name))
        if not ok:
            raise AssertionError("M2 không có câu hỏi mặc định sau chuyển")
        press(moved_app, {"Đồng ý"})
        time.sleep(3)
        return destination
    finally:
        # The product's mover logs its copy and its reopen waiter here: evidence for M2 either way.
        log = Path.home() / "Library/Caches/HSTOffice/update/move.log"
        if log.exists():
            (out / "M2-move.log").write_text(log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        listing = subprocess.run(["ps", "-axo", "pid,ppid,etime,command"], capture_output=True, text=True, timeout=30)
        (out / "M2-ps.log").write_text("\n".join(line for line in listing.stdout.splitlines()
                                                 if "HST" in line or "reopen" in line), encoding="utf-8")
        owned.update(app.processIdentifier() for app in applications())
        close_owned(owned)
        for opener in openers:
            if opener.poll() is None:
                opener.kill()
        subprocess.run(["hdiutil", "detach", "-force", str(mount)], **QUIET)


if __name__ == "__main__":
    # Child mode (prepare.py owns the hard timeout): rows go to a JSON-lines file as soon as they are known, and a
    # stack of every thread is dumped each 60 s so a stuck step names itself.
    import faulthandler
    import json
    import sys
    dmg, out, records = sys.argv[1:4]
    stack = (Path(out) / "startup-stack.log").open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(60, repeat=True, file=stack)
    def record(value):
        with open(records, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
    try:
        print(json.dumps(dict(destination=str(prepare(dmg, out, record)))))
    except Exception as error:
        print(json.dumps(dict(error=f"{type(error).__name__}: {error}"), ensure_ascii=False))
        raise SystemExit(1)
