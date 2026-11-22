#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Print page of the File panel opened again and again (hst-backstage-print.patch) on gtk3, no keys. Each opening
must show one print panel: on gtk3 a panel left behind by the previous job stays in the page, so the settings and
preview were stacked once more per opening. Run like check-backstage-print-margins.py:
    dbus-run-session -- env NO_AT_BRIDGE=0 GTK_MODULES=gail:atk-bridge SAL_USE_VCLPLUGIN=gtk3 \
        <office python> check-backstage-print-repeat.py --soffice PATH --out DIR [--rounds N] [--shot CMD]
Run it under LANG=C.UTF-8 as well: gettext ignores the UI language in the C locale, so the panel came out in English
on gtk3 (hst-gtk-ui-translation-c-locale.patch).
Writer, Sheets, Slides and Draw: .uno:Print (Ctrl+P) opens the page, the panel closes (its job is cancelled), N times.
Each opening: exactly one panel, its labels in Vietnamese. After all: no job printed (the generic PDF printer of the
profile wrote nothing), the office's memory grew by less than MAX_GROWTH_KIB, and after WARM_UP openings of an
application each further opening adds less than MAX_GROWTH_PER_OPENING_KIB (median step). Exit 1 on a failure.
"""
import argparse, importlib.util, json, os, socket, subprocess, sys, tempfile, time  # noqa: E401

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_spec = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
check, failures = base.check, base.failures
ATSPI = os.path.join(HERE, "backstage_print_atspi.py")
APPS = ("swriter", "scalc", "simpress", "sdraw")
# a cancelled job and its panel are freed; what stays per opening (caches, the preview's bitmaps) is small
MAX_GROWTH_KIB = 150 * 1024
# once the first openings filled the caches an opening costs about nothing; each job's printer kept its own font
# list alive before (the font files mapped again, about 20 MB per opening)
WARM_UP, MAX_GROWTH_PER_OPENING_KIB = 2, 4 * 1024


def free_port():
    """A port no other office listens on: with the base check's fixed port a run could attach to another office."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def atspi(*args):
    """Run the AT-SPI helper in the system python (outside the office's python environment)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "URE_"))}
    run = subprocess.run(["/usr/bin/python3", ATSPI, *args], capture_output=True, text=True, timeout=120, env=env)
    return json.loads(run.stdout) if run.stdout.strip() else {"error": run.stderr[-300:]}


def office_rss_kib(profile_url):
    """Resident memory of the soffice.bin of this profile, in KiB (0 when not found)."""
    pids = subprocess.run(["pgrep", "-f", "soffice.bin.*" + profile_url], capture_output=True, text=True).stdout.split()
    for pid in pids:
        try:
            with open(f"/proc/{pid}/status", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1])
        except OSError:
            continue
    return 0


def make_doc(office, app):
    doc = office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, ())
    if app == "swriter":
        doc.Text.setString("HST print page " * 40)
    elif app == "scalc":
        doc.Sheets.getByIndex(0).getCellRangeByPosition(0, 0, 3, 19).setDataArray(
            tuple(tuple("R%dC%d" % (r, c) for c in range(4)) for r in range(20)))
    return doc


def open_page(office, frame, timeout=40):
    """.uno:Print, then the panels on the page once its preview counts the pages."""
    office.ui.executeCommandForProvider(".uno:Print", frame)
    found = {}
    for _ in range(timeout):
        found = atspi("panels")
        if found.get("panels"):
            break
        time.sleep(1)
    time.sleep(2)  # a panel left behind would be shown by now as well
    return atspi("panels") if found.get("panels") else found


def close_panel(office, frame):
    """Close the File panel (as Esc does): the page cancels its job."""
    office.ui.executeCommandForProvider(".uno:HSTBackstage", frame)
    for _ in range(20):
        if not atspi("panels").get("panels"):
            return True
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsrepeat-"))  # noqa
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--apps", default=",".join(APPS), help="comma separated, of " + ", ".join(APPS))
    parser.add_argument("--shot", help="screenshot command with {} for the file")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    printer_dir = os.path.join(out, "pdf")
    os.makedirs(printer_dir, exist_ok=True)
    shot = lambda name: args.shot and os.system(args.shot.format(os.path.join(out, name)))  # noqa: E731
    base.PORT = free_port()  # VisibleOffice reads the module's port
    office = base.VisibleOffice(args.soffice, out, printer_dir)
    profile_url = office.uno.systemPathToFileUrl(os.path.join(out, "profile"))
    try:
        office.close_welcome()
        memory = {}
        for app in args.apps.split(","):
            doc = make_doc(office, app)
            frame = doc.getCurrentController().getFrame()
            for round_ in range(1, args.rounds + 1):
                found = open_page(office, frame)
                check(found.get("panels") == 1, f"{app}: opening {round_} shows one print panel ({found})")
                check(not found.get("english"), f"{app}: opening {round_}: the panel is in Vietnamese ({found})")
                if round_ == args.rounds:
                    shot(f"{app}-print-{round_}.png")
                check(close_panel(office, frame), f"{app}: closing the File panel removes the print panel")
                time.sleep(1)
                memory.setdefault(app, []).append(office_rss_kib(profile_url))
            doc.setModified(False)
            doc.close(True)
        print("memory (KiB after each opening): " + json.dumps(memory), flush=True)
        first = next(iter(memory.values()))[0]
        last = list(memory.values())[-1][-1]
        check(first > 0 and last - first < MAX_GROWTH_KIB,
              f"memory grows by less than {MAX_GROWTH_KIB} KiB over all openings ({first} -> {last} KiB)")
        for app, values in memory.items():
            later = values[WARM_UP - 1:]
            steps = sorted(b - a for a, b in zip(later, later[1:]))
            if steps:  # the median step: one cache filled late is not a leak, a printer kept per job is in every step
                per_opening = steps[len(steps) // 2]
                check(per_opening < MAX_GROWTH_PER_OPENING_KIB,
                      f"{app}: after {WARM_UP} openings each opening adds less than {MAX_GROWTH_PER_OPENING_KIB} KiB "
                      f"(median {per_opening} KiB, steps {steps})")
        printed = os.listdir(printer_dir)
        check(not printed, f"no cancelled job printed ({printed})")
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
