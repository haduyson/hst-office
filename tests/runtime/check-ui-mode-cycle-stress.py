# SPDX-License-Identifier: AGPL-3.0-only
"""Stress: cycling the user interface modes with two documents of each module open never crashes the office
(Linux, GUI build, existing X display).

Scenario and verdict: ui_mode_cycle_stress.py (PASS, FAIL only on a crash, INCONCLUSIVE on a hang). Before
hst-toolbox-control-disposed-state.patch the office died with SIGSEGV within a few rounds: a toolbar's delayed
controller update (ToolBarManager::AsyncUpdateControllersHdl) bound the paste control, whose first state asks the
system clipboard and so runs a nested main loop with the SolarMutex released; the mode switch on the UNO request
thread destroyed that toolbar meanwhile, and the paste control then laid out its disposed ToolBox
(ToolBox::GetItemRect -> ImplFormat); with that fixed alone, the update loop then read the controller map the
dispose had cleared (ToolBarManager::UpdateControllers). Usage: python3 tests/runtime/check-ui-mode-cycle-stress.py
[--instdir upstream/libreoffice/instdir] [--out tests/output/ui-mode-cycle-stress] [--display :97] [--rounds 20] [--port 21986].
Exit 1 only when the office crashed.

Hangs: an office driven over UNO used to hang here for good (gtk3: a Paste state built on the request thread called
gtk_clipboard_wait_for_targets there, which took the glib main context from the main thread). Fixed by
hst-gtk-clipboard-main-thread.patch; a hang is INCONCLUSIVE and writes hang-stacks.txt (gdb) to --out.
"""
import argparse
import importlib.util
import os
import shutil
import signal
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ui_mode_cycle_stress as stress  # noqa: E402

PORT = 21986  # deterministic per check (see hst_gui); 21994 is check-vi-intro.py's


def load_adapter():
    """The Adapter of check-ui-mode-tabs.py (hst_gui.Office with the interface the scenario helpers expect)."""
    spec = importlib.util.spec_from_file_location("check_ui_mode_tabs", os.path.join(HERE, "check-ui-mode-tabs.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ui-mode-cycle-stress"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=PORT, help="UNO port (another one to run two builds side by side)")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    os.makedirs(os.path.join(args.out, "docs"), exist_ok=True)
    if os.geteuid() == 0:
        os.chmod(os.path.join(args.out, "docs"), 0o777)
    office = hst_gui.Office(args.instdir, args.out, args.port, display=args.display, nodefault=True)

    def on_hang():
        hst_gui.screenshot(os.path.join(args.out, "hang.png"), args.display)
        pid = office.pid
        if pid and shutil.which("gdb"):  # where it hangs, for the report
            with open(os.path.join(args.out, "hang-stacks.txt"), "w", encoding="utf-8") as stacks:
                subprocess.run(["gdb", "-p", str(pid), "-batch", "-ex", "set pagination off",
                                "-ex", "info sharedlibrary", "-ex", "thread apply all bt 50"],
                               stdout=stacks, stderr=subprocess.STDOUT, timeout=180, check=False)
        if pid:  # never leave the hung office behind
            os.kill(pid, signal.SIGKILL)

    def is_crash(error):
        return office.pid is None or "disposed" in str(error)

    office.start()
    try:
        return stress.run(load_adapter()(office), args.rounds, args.out, on_hang, is_crash)
    finally:
        office.stop()


if __name__ == "__main__":
    raise SystemExit(main())
