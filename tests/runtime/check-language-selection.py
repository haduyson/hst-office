# SPDX-License-Identifier: AGPL-3.0-only
"""Check UI language selection: resolution, missing translations, admin lock, restart keeping documents.

Usage: python3 tests/runtime/check-language-selection.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/language-selection] [--display :97] [--port 23950]
           [--phases resolution,partial,lock,restart,shortcut]

Phases (each starts soffice as the build user with fresh profiles on an existing X display):
  resolution  the stored UILocale (Tools > Options > Languages and Locales > General > User
              interface) is never erased: en, en-GB, EN-us resolve to the installed en-US, vi-VN to
              vi, an uninstalled language (de) falls back like "Default"; Default follows the OS
              (vi_VN -> vi, en_US and fr_FR -> en-US).
  partial     on a hard-linked copy of the installation without program/resource/vi the UI falls
              back to English for the session (no half-translated UI) and keeps the choice "vi";
              without any Vietnamese registration either, the choice "vi" is still kept.
  lock        a finalized UILocale (administrator policy layer) wins over the user's value and
              rejects writes; the HST shortcut entries are disabled.
  restart     AutoRecovery "doSessionRestart" (what Options and the HST shortcut use after a
              language change): a modified saved document, a modified untitled document, an
              untitled empty one and an unmodified saved one are all reopened after the restart,
              the changed ones still modified with their changes, the files on disk untouched;
              the new UI language is active.
  shortcut    HST > Ngôn ngữ giao diện: the current choice is checked; "English" answered "No"
              writes en-US without restarting; "Tiếng Việt" asks with Vietnamese buttons
              ("Khởi động lại ngay" / "Để sau", focus on "Để sau") in the English UI and restarts with
              the open documents and a Vietnamese UI.
Evidence (JSON, screenshots) goes to --out. Exit 1 when a check fails.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
GENERAL = "/org.openoffice.Office.Linguistic/General"
LOCK_XCD = """<?xml version="1.0" encoding="UTF-8"?>
<oor:data xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:oor="http://openoffice.org/2001/registry">
<dependency file="main"/>
<oor:component-data oor:name="Linguistic" oor:package="org.openoffice.Office"><node oor:name="General">
<prop oor:name="UILocale" oor:finalized="true"><value>en-US</value></prop></node></oor:component-data>
</oor:data>
"""
SHORTCUT = "org.hst.office.vi:UILanguage"


class Office(hst_gui.Office):
    """hst_gui.Office with any OS locale (compiled into LOCPATH when the host lacks it)."""

    def _env(self):
        env = super()._env()
        env.pop("LANGUAGE", None)
        base = self.lang.split(".")[0]
        if not base.startswith(("vi_", "en_US")):
            env["LOCPATH"] = hst_gui.ensure_locale(self.workdir, base)
        return env

    def read_config(self, node, name):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", node
        provider = self.service("com.sun.star.configuration.ConfigurationProvider")
        return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,)).getPropertyValue(name)

    def ui_state(self):
        """(stored UILocale, UI language in use, title of a new Writer document)."""
        doc = self.load("private:factory/swriter", hidden=True)
        try:
            title = doc.getTitle()
        finally:
            doc.close(True)
        return self.read_config(GENERAL, "UILocale"), self.read_config("/org.openoffice.Setup/L10N", "ooLocale"), title

    def wait_restarted(self, old_pid, timeout=180):
        """Wait for the restarted soffice.bin (new pid) and reconnect UNO."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = self.pid
            if pid is not None and pid != old_pid:
                self.ctx = self._connect()
                return True
            time.sleep(1)
        return False


def documents(office):
    """Open document models, keyed by title."""
    result = {}
    components = office.desktop().getComponents().createEnumeration()
    while components.hasMoreElements():
        model = components.nextElement()
        if hasattr(model, "getTitle") and hasattr(model, "isModified"):
            result[model.getTitle()] = model
    return result


def discard_all(office):
    """Close every document without saving, so the final termination asks nothing."""
    for model in documents(office).values():
        try:
            model.setModified(False)
            model.close(True)
        except Exception:  # noqa: BLE001 - best effort before stop()
            pass


def wait_for(predicate, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001 - office still starting
            pass
        time.sleep(1)
    return False


def untitled(locale):
    return "Không tên" if locale.startswith("vi") else "Untitled"


def phase_resolution(args, check):
    cases = (  # (OS locale, stored UILocale or None for Default, expected UI language)
        ("en_US.UTF-8", None, "en-US"), ("vi_VN.UTF-8", None, "vi"), ("fr_FR.UTF-8", None, "en-US"),
        ("vi_VN.UTF-8", "en-US", "en-US"), ("en_US.UTF-8", "vi", "vi"),
        ("vi_VN.UTF-8", "en-GB", "en-US"), ("vi_VN.UTF-8", "EN-us", "en-US"), ("en_US.UTF-8", "en", "en-US"),
        ("en_US.UTF-8", "vi-VN", "vi"), ("vi_VN.UTF-8", "de", "vi"), ("en_US.UTF-8", "de", "en-US"))
    for index, (lang, stored, expected) in enumerate(cases):
        tag = f"{lang[:5]} {stored or 'Default'}"
        config = [(GENERAL, "UILocale", stored)] if stored is not None else []
        office = Office(args.instdir, os.path.join(args.out, "resolution", str(index)), args.port, display=args.display,
                        lang=lang, config=config)
        try:
            office.start()
            raw, used, title = office.ui_state()
            check(f"[{tag}] UI language {expected}", used == expected and title.startswith(untitled(used)), f"{used}, {title!r}")
            check(f"[{tag}] stored choice kept", raw == (stored or ""), repr(raw))
        except Exception as error:  # noqa: BLE001
            check(f"[{tag}] office starts", False, repr(error))
        finally:
            office.stop()


def linked_copy(instdir, target, remove=(), add=None):
    """Hard-linked copy of the installation with files removed/added (the original is untouched)."""
    shutil.rmtree(target, ignore_errors=True)
    subprocess.run(["cp", "-al", instdir, target], check=True)
    for rel in remove:
        path = os.path.join(target, rel)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    if add:
        rel, text = add
        with open(os.path.join(target, rel), "w", encoding="utf-8") as handle:
            handle.write(text)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, target], check=True)
    return target


def phase_partial(args, check):
    base = os.path.join(args.out, "partial")
    os.makedirs(base, exist_ok=True)
    no_mo = linked_copy(args.instdir, os.path.join(base, "instdir-no-mo"), remove=("program/resource/vi",))
    no_vi = linked_copy(args.instdir, os.path.join(base, "instdir-no-vi"), remove=(
        "program/resource/vi", "share/registry/Langpack-vi.xcd", "share/registry/res/registry_vi.xcd",
        "share/registry/res/fcfg_langpack_vi.xcd"))
    cases = ((no_mo, "no-mo", "vi_VN.UTF-8", None), (no_mo, "no-mo", "en_US.UTF-8", "vi"),
             (no_vi, "no-vi", "en_US.UTF-8", "vi"))
    try:
        for index, (instdir, name, lang, stored) in enumerate(cases):
            tag = f"{name} {lang[:5]} {stored or 'Default'}"
            config = [(GENERAL, "UILocale", stored)] if stored is not None else []
            office = Office(instdir, os.path.join(base, str(index)), args.port, display=args.display, lang=lang, config=config)
            try:
                office.start()
                raw, used, title = office.ui_state()
                check(f"[{tag}] falls back to English for the session", used == "en-US" and title.startswith("Untitled"),
                      f"{used}, {title!r}")
                check(f"[{tag}] stored choice kept", raw == (stored or ""), repr(raw))
            except Exception as error:  # noqa: BLE001
                check(f"[{tag}] office starts", False, repr(error))
            finally:
                office.stop()
    finally:
        shutil.rmtree(no_mo, ignore_errors=True)
        shutil.rmtree(no_vi, ignore_errors=True)


class StatusListener:
    """XStatusListener collecting the state of one HST shortcut entry."""

    def __new__(cls):
        import unohelper
        from com.sun.star.frame import XStatusListener

        class Listener(unohelper.Base, XStatusListener):
            def __init__(self):
                self.events = []

            def statusChanged(self, event):
                self.events.append((bool(event.IsEnabled), event.State))

            def disposing(self, source):
                pass
        return Listener()


def shortcut_state(office, frame, command):
    """(enabled, checked) of HST > Ngôn ngữ giao diện > command as the menu sees it."""
    url = office.service("com.sun.star.util.URLTransformer")
    import uno
    target = uno.createUnoStruct("com.sun.star.util.URL")
    target.Complete = SHORTCUT + command
    _ok, target = url.parseStrict(target)
    dispatch = frame.queryDispatch(target, "", 0)
    if dispatch is None:
        return None
    listener = StatusListener()
    dispatch.addStatusListener(listener, target)
    dispatch.removeStatusListener(listener, target)
    return listener.events[-1] if listener.events else None


def phase_lock(args, check):
    base = os.path.join(args.out, "lock")
    os.makedirs(base, exist_ok=True)
    locked = linked_copy(args.instdir, os.path.join(base, "instdir-locked"),
                         add=("share/registry/zz-language-lock.xcd", LOCK_XCD))
    office = Office(locked, os.path.join(base, "profile"), args.port, display=args.display, lang="vi_VN.UTF-8",
                    config=[(GENERAL, "UILocale", "vi")])
    try:
        office.start()
        raw, used, _title = office.ui_state()
        check("[lock] administrator value wins over the user's vi", raw == "en-US" and used == "en-US", f"{raw}, {used}")
        try:
            office.set_config(GENERAL, "UILocale", "vi")
            check("[lock] writing UILocale is rejected", False, "write accepted")
        except Exception as error:  # noqa: BLE001
            check("[lock] writing UILocale is rejected", True, type(error).__name__)
        frame = office.desktop().getCurrentFrame() or office.load("private:factory/swriter").getCurrentController().getFrame()
        for command in ("Vi", "En", "System"):
            state = shortcut_state(office, frame, command)
            check(f"[lock] HST shortcut {command} disabled", state is not None and state[0] is False, repr(state))
        # Tools > Options > Languages and Locales > General (the user interface list is greyed out)
        office.close_welcome()
        worker = threading.Thread(target=office.dispatch, args=(frame, ".uno:OptionsTreeDialog"), daemon=True)
        worker.start()
        env = dict(os.environ, DISPLAY=office.display)

        def options():
            return [(w, n) for w, n in hst_gui.toplevels(office.display, office.pid) if n.startswith(("Options", "Tùy chọn"))]
        if wait_for(lambda: bool(options()), 60):
            time.sleep(2)
            subprocess.run(["xdotool", "windowfocus", options()[0][0]], env=env, check=False, timeout=10)
            time.sleep(1)
            # the tree's search box: "Languages" filters to Languages and Locales, then its General page
            subprocess.run(["xdotool", "type", "Languages"], env=env, check=False, timeout=10)
            time.sleep(1)
            subprocess.run(["xdotool", "key", "Return", "Right", "Down"], env=env, check=False, timeout=10)
            time.sleep(3)
        page = [n for _w, n in options()]
        office.screenshot(os.path.join(args.out, "lock-options-languages.png"))
        check("[lock] Options language page opens (screenshot: user interface list disabled)",
              any("General" in n for n in page), repr(page))
        if options():
            answer(office, options()[0][1], "Escape", 5)
        worker.join(20)
    except Exception as error:  # noqa: BLE001
        check("[lock] office starts", False, repr(error))
    finally:
        office.stop()
        shutil.rmtree(locked, ignore_errors=True)


def open_documents(office, folder):
    """Two saved files and two untitled documents; returns {key: (title, expected text, modified)}."""
    from com.sun.star.beans import PropertyValue

    def store(doc, path, filter_name):
        prop = PropertyValue()
        prop.Name, prop.Value = "FilterName", filter_name
        doc.storeAsURL("file://" + path, (prop,))

    os.makedirs(folder, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", hst_gui.BUILD_USER, folder], check=True)
    saved_odt, saved_ods = os.path.join(folder, "saved-modified.odt"), os.path.join(folder, "saved-clean.ods")
    doc = office.load("private:factory/swriter")
    doc.getText().setString("Bản đã lưu")
    store(doc, saved_odt, "writer8")
    doc.getText().getEnd().setString(" + thay đổi chưa lưu")
    sheet = office.load("private:factory/scalc")
    sheet.getSheets().getByIndex(0).getCellByPosition(0, 0).setString("Bảng đã lưu")
    store(sheet, saved_ods, "calc8")
    sheet.setModified(False)
    new_text = office.load("private:factory/swriter")
    new_text.getText().setString("Văn bản chưa đặt tên")
    office.load("private:factory/scalc")  # untitled, untouched
    with open(saved_odt, "rb") as handle:
        on_disk = handle.read()
    return saved_odt, on_disk


def check_reopened(office, check, tag, saved_odt, on_disk):
    docs = {}

    def all_back():
        docs.clear()
        docs.update(documents(office))
        return len(docs) >= 4
    wait_for(all_back, 90)
    titles = sorted(docs)
    check(f"[{tag}] all 4 documents reopened", len(docs) == 4, repr(titles))
    texts = {t: (d.getText().getString() if hasattr(d, "getText") else d.getSheets().getByIndex(0).getCellByPosition(0, 0).getString(), d.isModified())
             for t, d in docs.items()}
    saved = [v for t, v in texts.items() if t.startswith("saved-modified")]
    check(f"[{tag}] modified saved document keeps its unsaved changes, still modified",
          saved == [("Bản đã lưu + thay đổi chưa lưu", True)], repr(saved))
    clean = [v for t, v in texts.items() if t.startswith("saved-clean")]
    check(f"[{tag}] unmodified saved document reopened unmodified", clean == [("Bảng đã lưu", False)], repr(clean))
    new = [v for t, v in texts.items() if v[0] == "Văn bản chưa đặt tên"]
    check(f"[{tag}] untitled document keeps its text, still modified", new == [("Văn bản chưa đặt tên", True)], repr(texts))
    with open(saved_odt, "rb") as handle:
        check(f"[{tag}] file on disk not overwritten", handle.read() == on_disk)


def phase_restart(args, check):
    base = os.path.join(args.out, "restart")
    office = Office(args.instdir, os.path.join(base, "office"), args.port, display=args.display, lang="en_US.UTF-8",
                    restore=True)
    try:
        office.start()
        saved_odt, on_disk = open_documents(office, os.path.join(base, "files"))
        office.set_config(GENERAL, "UILocale", "vi")  # as Options does before its restart prompt
        old_pid = office.pid
        url = office.service("com.sun.star.util.URLTransformer")
        import uno
        from com.sun.star.beans import PropertyValue
        target = uno.createUnoStruct("com.sun.star.util.URL")
        target.Complete = "vnd.sun.star.autorecovery:/doSessionRestart"
        _ok, target = url.parseStrict(target)
        arg = PropertyValue()
        arg.Name, arg.Value = "DispatchAsynchron", True
        recovery = office.ctx.getValueByName("/singletons/com.sun.star.frame.theAutoRecovery")
        recovery.dispatch(target, (arg,))
        check("[restart] office restarted", office.wait_restarted(old_pid), f"old pid {old_pid}, new {office.pid}")
        check_reopened(office, check, "restart", saved_odt, on_disk)
        check("[restart] new UI language active", office.read_config("/org.openoffice.Setup/L10N", "ooLocale") == "vi")
        office.screenshot(os.path.join(args.out, "restart-after.png"))
    except Exception as error:  # noqa: BLE001
        check("[restart] completed", False, repr(error))
    finally:
        discard_all(office)
        office.stop()


def dialog_buttons(office):
    """[(label, focused, peer)] of the buttons of the active top window (our HST dialog)."""
    window = office.service("com.sun.star.awt.Toolkit").getActiveTopWindow()
    found = []
    for child in (window.getWindows() if window is not None and hasattr(window, "getWindows") else ()):
        if not hasattr(child, "setActionCommand"):  # XButton: push buttons only
            continue
        try:
            label = child.getProperty("Label")
        except Exception:  # noqa: BLE001 - not a button
            continue
        if isinstance(label, str) and label:
            found.append((label.replace("~", ""), bool(child.hasFocus()), child))  # without access-key marks
    return found


def answer(office, title, key, timeout=30):
    """Wait for our dialog `title` and press `key` in it (Escape/Return), or the button labelled `key`."""
    env = dict(os.environ, DISPLAY=office.display)

    def find():
        return [w for w, n in hst_gui.toplevels(office.display, office.pid) if n == title]
    if not wait_for(lambda: bool(find()), timeout):
        return False
    time.sleep(1)
    wid = find()[0]
    if key not in ("Escape", "Return"):  # a button label: press that button
        for name, _focused, peer in dialog_buttons(office):
            if name == key:
                peer.setFocus()
                time.sleep(0.5)
                subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
                subprocess.run(["xdotool", "key", "space"], env=env, check=False, timeout=10)
                return True
        return False
    subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
    time.sleep(0.5)
    subprocess.run(["xdotool", "key", key], env=env, check=False, timeout=10)
    return True


def phase_shortcut(args, check):
    base = os.path.join(args.out, "shortcut")
    office = Office(args.instdir, os.path.join(base, "office"), args.port, display=args.display, lang="en_US.UTF-8",
                    restore=True)
    try:
        office.start()
        saved_odt, on_disk = open_documents(office, os.path.join(base, "files"))
        frame = office.desktop().getCurrentFrame()
        states = {c: shortcut_state(office, frame, c) for c in ("Vi", "En", "System")}
        check("[shortcut] Default is the checked entry", states == {"Vi": (True, False), "En": (True, False),
                                                                     "System": (True, True)}, repr(states))
        old_pid = office.pid
        worker = threading.Thread(target=office.dispatch, args=(frame, SHORTCUT + "En"), daemon=True)
        worker.start()
        check("[shortcut] English asks to restart", answer(office, "Ngôn ngữ giao diện", "Escape"))
        worker.join(30)
        check("[shortcut] English written, no restart on No",
              office.read_config(GENERAL, "UILocale") == "en-US" and office.pid == old_pid)
        check("[shortcut] English is now checked", shortcut_state(office, frame, "En") == (True, True))
        office.screenshot(os.path.join(args.out, "shortcut-before-restart.png"))
        worker = threading.Thread(target=office.dispatch, args=(frame, SHORTCUT + "Vi"), daemon=True)
        worker.start()
        check("[shortcut] Vietnamese asks to restart", wait_for(lambda: len(dialog_buttons(office)) == 2, 30))
        buttons = [(name, focused) for name, focused, _c in dialog_buttons(office)]
        check("[shortcut] restart question has Vietnamese buttons in the English UI, focus on Để sau",
              sorted(buttons) == [("Khởi động lại ngay", False), ("Để sau", True)], repr(buttons))
        office.screenshot(os.path.join(args.out, "shortcut-restart-question.png"))
        check("[shortcut] Khởi động lại ngay pressed", answer(office, "Ngôn ngữ giao diện", "Khởi động lại ngay"))
        check("[shortcut] office restarted on Yes", office.wait_restarted(old_pid))
        check_reopened(office, check, "shortcut", saved_odt, on_disk)
        check("[shortcut] Vietnamese UI after restart", office.read_config("/org.openoffice.Setup/L10N", "ooLocale") == "vi")
        office.screenshot(os.path.join(args.out, "shortcut-after-restart.png"))
    except Exception as error:  # noqa: BLE001
        check("[shortcut] completed", False, repr(error))
    finally:
        discard_all(office)
        office.stop()


PHASES = {"resolution": phase_resolution, "partial": phase_partial, "lock": phase_lock,
          "restart": phase_restart, "shortcut": phase_shortcut}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/language-selection"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=23950)
    parser.add_argument("--phases", default=",".join(PHASES))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    os.chdir(args.out)  # soffice runs as the build user, which must be able to enter the working directory
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
        write_evidence()

    def write_evidence():  # after every check: a hung phase still leaves its results
        failed = sum(r["status"] == "FAIL" for r in results)
        with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
            json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
        return failed

    for name in args.phases.split(","):
        PHASES[name](args, check)
    failed = write_evidence()
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
