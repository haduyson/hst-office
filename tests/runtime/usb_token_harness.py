# SPDX-License-Identifier: AGPL-3.0-only
"""Shared UI/PKI helpers for USB token setup; test credentials stay in the harness."""
import importlib.util
import os
from pathlib import Path
import threading
import time
import zipfile

import hst_gui
import signature_pki


def signing_helpers():
    spec = importlib.util.spec_from_file_location("signature_check", Path(__file__).with_name("check-digital-signature.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install(office, oxt):
    # User installation of the same-version OXT conflicts with the bundled UNO
    # implementations. Redirect only the bundled-extension bootstrap directory;
    # use the real /opt/hst executable and keep its install completely read-only.
    bundled = Path(office.workdir) / "bundled"
    bundled.mkdir(parents=True)
    for entry in (Path(office.program).parent / "share/extensions").iterdir():
        if entry.name != "hst-vietnamese-tools":
            (bundled / entry.name).symlink_to(entry, target_is_directory=True)
    with zipfile.ZipFile(oxt) as archive:
        archive.extractall(bundled / "hst-vietnamese-tools")
    os.environ["BUNDLED_EXTENSIONS"] = bundled.as_uri()
    office.extra_args.append("-env:BUNDLED_EXTENSIONS=" + bundled.as_uri())
    office.start()
    # Set after extension schema registration: first-run bootstrap can discard
    # seeded values for a schema it has not seen yet.
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    flag = PropertyValue(Name="nodepath", Value="/org.hasontech.hstoffice.Welcome")
    node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (flag,))
    node.setPropertyValue("Shown", True)
    node.commitChanges()


def setup_dialog(office, frame, signing):
    errors = []

    def dispatch():
        try:
            office.dispatch(frame, "org.hst.office.vi:SetupUsbToken")
        except Exception as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=dispatch, daemon=True)
    worker.start()
    ui = office.service("org.libreoffice.uitest.UITest")
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        window = ui.getTopFocusWindow()
        state = {p.Name: p.Value for p in window.getState()}
        if state.get("Text") == "Thiết lập USB Token" and state.get("Modal") == "true":
            # UNO-created controls have no UITest child IDs; XFixedText and
            # XVclContainer let us inspect the real result without instrumentation.
            toolkit = office.service("com.sun.star.awt.Toolkit")
            peers = [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]
            peer = next(p for p in peers if hasattr(p, "getTitle") and p.getTitle() == state["Text"])
            def contents(parent):
                values = [parent.getText()] if hasattr(parent, "getText") else []
                if hasattr(parent, "getWindows"):
                    for child in parent.getWindows():
                        values.extend(contents(child))
                return values
            text = "\n".join(contents(peer))
            if not text:
                time.sleep(0.2)
                continue
            shots = Path(office.workdir) / "setup-shots"
            shots.mkdir(exist_ok=True)
            office.screenshot(str(shots / (str(len(list(shots.iterdir()))) + ".png")))
            # This is an informational result, so XDialog.endExecute closes it
            # without depending on a window manager or pointer focus in Xvfb.
            peer.endExecute()
            worker.join(timeout=10)
            assert not worker.is_alive() and not errors, errors
            return text
        if errors:
            raise AssertionError(errors)
        time.sleep(0.2)
    raise TimeoutError("Setup result dialog missing: " + str(window.getChildren()))


def certificate_with_pin(office, signing, shots):
    result, errors = [], []

    def get_cert():
        try:
            result.append(signing.token_certificate(office))
        except Exception as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=get_cert, daemon=True)
    worker.start()
    dialogs = signing.Dialogs(office, str(shots), [signature_pki.USER_PIN])
    deadline = time.monotonic() + 40
    while worker.is_alive() and time.monotonic() < deadline:
        window, kids = dialogs.top()
        if "newpassEntry" in kids:
            dialogs._answer_pin(window)
        time.sleep(0.2)
    worker.join(timeout=1)
    assert not worker.is_alive() and not errors, errors
    assert result and result[0] is not None, "Token certificate missing from XSecurityEnvironment"
    return result[0].SubjectName, len(dialogs.prompts)
