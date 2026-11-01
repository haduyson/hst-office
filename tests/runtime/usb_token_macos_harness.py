# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS profile, menu and Aqua dialog helpers for the USB Token probe."""
from pathlib import Path
import shutil
import subprocess
import threading
import time

TITLE = "Thiết lập USB Token"


def _peers(office):
    """Top-level window peers from the toolkit; a closing window raises DisposedException, never
    crashes (unlike a UITest object whose window died between two calls)."""
    toolkit = office.service("com.sun.star.awt.Toolkit")
    peers = []
    for index in range(toolkit.getTopWindowCount()):
        try:
            peers.append(toolkit.getTopWindow(index))
        except Exception:  # noqa: BLE001 - window went away meanwhile
            pass
    return peers


def _title(peer):
    try:
        return peer.getTitle() if hasattr(peer, "getTitle") else None
    except Exception:  # noqa: BLE001
        return None


def modal_dialog_open(office):
    """True while a visible dialog (XDialog peer) exists: only then is UITest polled at all."""
    for peer in _peers(office):
        try:
            if hasattr(peer, "endExecute") and peer.isVisible():
                return True
        except Exception:  # noqa: BLE001
            pass
    return False


def setup_dialog(office, frame, signing, timeout=90):
    """Dispatch HST ▸ Thiết lập USB Token…, read the result dialog through the toolkit and close it.

    Same contract as usb_token_harness.setup_dialog, without UITest: polling UITest's focus window
    while windows open and close crashed soffice in WindowUIObject::get_state on macOS."""
    errors = []

    def dispatch():
        try:
            office.dispatch(frame, "org.hst.office.vi:SetupUsbToken")
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    def contents(parent):
        values = [parent.getText()] if hasattr(parent, "getText") else []
        if hasattr(parent, "getWindows"):
            for child in parent.getWindows():
                values.extend(contents(child))
        return values

    worker = threading.Thread(target=dispatch, daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if office.crashed() is not None:
            raise RuntimeError("soffice exited (%s) during the setup command" % office.crashed())
        for peer in _peers(office):
            if _title(peer) != TITLE:
                continue
            try:
                text = "\n".join(contents(peer))
            except Exception:  # noqa: BLE001 - still being built
                text = ""
            if not text:
                continue
            shots = Path(office.workdir) / "setup-shots"
            shots.mkdir(exist_ok=True)
            office.screenshot(str(shots / (str(len(list(shots.iterdir()))) + ".png")))
            peer.endExecute()
            worker.join(timeout=20)
            assert not worker.is_alive() and not errors, errors or "setup command did not return"
            return text
        if errors:
            raise AssertionError(errors)
        time.sleep(0.3)
    office.screenshot(str(Path(office.workdir) / "setup-shots" / "timeout.png"))
    raise TimeoutError("Setup result dialog missing after %d s" % timeout)


def other_vendor_module():
    """OpenSC's PKCS#11 module from Homebrew: a real non-roots vendor module that loads without a
    reader (absolute install names, so a copy outside Homebrew still loads)."""
    prefix = subprocess.run(["brew", "--prefix", "opensc"], capture_output=True, text=True, check=True).stdout.strip()
    return Path(prefix) / "lib/opensc-pkcs11.so"


def firefox_profile(home, app):
    from usb_token_private_harness import snapshot
    root = home / "Library/Application Support/Firefox"
    source = root / "Profiles/hst.default-release"
    source.mkdir(parents=True)
    (root / "profiles.ini").write_text("[Profile0]\nName=default-release\nIsRelative=1\n"
                                       "Path=Profiles/hst.default-release\nDefault=1\n\n[General]\nStartWithLastProfile=1\n")
    vendor = home / "another-vendor.so"
    shutil.copyfile(other_vendor_module(), vendor)
    subprocess.run(["certutil", "-N", "-d", "sql:" + str(source), "--empty-password"], check=True, capture_output=True)
    # Builtin Roots: the app's own libnssckbi, as a profile used with this NSS would have it.
    roots = Path(app) / "Contents/Frameworks/libnssckbi.dylib"
    for name, library in (("Builtin Roots", roots), ("Another vendor", vendor)):
        subprocess.run(["modutil", "-add", name, "-libfile", str(library), "-dbdir", "sql:" + str(source), "-force"],
                       check=True, capture_output=True)
    return source, snapshot(source)


def mac_dialogs(signing):
    """signing.Dialogs whose PIN answers also wake the Aqua event loop.

    A UITest click ends the modal PIN dialog from a UNO thread; on macOS the main thread can stay
    asleep in its modal loop until some native event arrives. AsyncCallback posts a VCL user event,
    which wakes it, as a real key press would. Prompts and their labels are kept for the report."""
    import unohelper
    from com.sun.star.awt import XCallback

    class Wake(unohelper.Base, XCallback):
        def notify(self, _data):
            pass

    class Dialogs(signing.Dialogs):
        log = []

        def nudge(self, front=True):
            self.office.service("com.sun.star.awt.AsyncCallback").addCallback(Wake(), None)
            if front:
                self.office.front()
            if shutil.which("cliclick"):
                subprocess.run(["cliclick", "m:+1,+0", "m:-1,+0"], check=False, capture_output=True, timeout=10)

        def top(self):
            # An ended but not yet returned PIN dialog stays the executing dialog while hidden:
            # it is not a new prompt. Wake the loop instead of answering it again.
            # Every poll also wakes the main loop: after a PIN answer the token login and certificate
            # listing continue there and otherwise may wait for the next native event.
            self.nudge(front=False)
            if not modal_dialog_open(self.office):
                return None, set()
            win, kids = super().top()
            if "newpassEntry" in kids and {p.Name: p.Value for p in win.getState()}.get("Visible") == "false":
                self.nudge()
                time.sleep(0.5)
                return None, set()
            return win, kids

        def _answer_pin(self, win):
            if not self.pins:
                return super()._answer_pin(win)
            label = {p.Name: p.Value for p in win.getChild("openPasswordLabel").getState()}.get("Text", "")
            answer = self.pins.pop(0)
            entry = win.getChild("newpassEntry")
            # SET needs no keyboard focus (a system alert may hold it); fall back to typing.
            try:
                entry.executeAction("SET", signing.props(TEXT=answer))
            except Exception:  # noqa: BLE001
                entry.executeAction("TYPE", signing.props(TEXT=answer))
            filled = len({p.Name: p.Value for p in entry.getState()}.get("Text", ""))
            self.prompts.append({"label": label, "answer": "pin(%d digits)" % len(answer), "entry_length": filled})
            self.shot("pin-prompt-%d" % len(self.prompts))
            self.later(win.getChild("ok"))
            time.sleep(1)
            self.nudge()
            time.sleep(1)

    class Logged(Dialogs):
        log = []

        def _answer_pin(self, win):
            super()._answer_pin(win)
            Logged.log.append(self.prompts[-1])

    return Logged


def changed(path, before):
    from usb_token_private_harness import snapshot
    after = snapshot(path)
    return sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))


def addon_urls(office):
    """Every URL of the HST add-on menus as merged into the configuration."""
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                  (PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Addons/AddonUI"),))
    urls = []

    def walk(node):
        for name in node.getElementNames():
            child = node.getByName(name)
            if name == "URL" and isinstance(child, str):
                urls.append(child)
            elif hasattr(child, "getElementNames"):
                walk(child)
    walk(access)
    return urls
