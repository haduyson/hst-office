# SPDX-License-Identifier: AGPL-3.0-only
"""Live part of the ribbon scorecard: drive one app on an X display and record what its ribbon shows.

Usage (normally started by ribbon_scorecard.py, as the build user under dbus-run-session):
  python3 tests/runtime/ribbon_scorecard_live.py --app writer --mode light --instdir DIR --display :153 --out OBS.json
Writes one observation JSON: the tab strip, a width sweep of every always-visible tab (group captions and boxes,
chevron, collapsed-group buttons, banner box, ribbon height), and the painting and gallery probes. No score is computed
here; ribbon_scorecard.py scores the observations.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402
from ribbon_scorecard_walk import PARK, layout, load_config, stable_layout  # noqa: E402
from ribbon_scorecard_probes import gallery, probes  # noqa: E402


class Session:
    def __init__(self, args, config):
        self.args, self.config = args, config
        self.app_conf = config["apps"][args.app]
        self.office = self.wid = None
        self.shots = 0

    def start(self):
        dark = self.args.mode == "dark"
        conf = [("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"),
                ("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2" if dark else "1"),
                ("/org.openoffice.Office.Common/Misc", "SymbolStyle", "hst_dark" if dark else "hst")]
        subprocess_env = {"GTK_THEME": "Adwaita:dark" if dark else "Adwaita"}
        subprocess.run(["xprop", "-display", self.args.display, "-root", "-remove", "AT_SPI_BUS"], check=False,
                       stderr=subprocess.DEVNULL)
        self.office = hst_gui.Office(self.args.instdir, self.args.work, self.args.port, display=self.args.display,
                                     extra_args=[f"--{self.args.app}"], nodefault=False, config=conf, env=subprocess_env)
        self.office.start()
        deadline = time.time() + 60
        windows = []
        while not windows and time.time() < deadline:
            time.sleep(2)
            windows = [w for w, n in hst_gui.toplevels(self.args.display, self.office.pid) if self.app_conf["name"] in n]
        if not windows:
            raise RuntimeError(f"no {self.app_conf['name']} window")
        self.wid = windows[0]
        gui.xdo(self.args.display, "windowmove", self.wid, "0", "0")
        self.resize(self.config["probe_width"])
        gui.xdo(self.args.display, "mousemove", *map(str, PARK))

    def resize(self, width):
        gui.xdo(self.args.display, "windowsize", self.wid, str(width), str(self.config["height"]))
        time.sleep(2)
        return stable_layout()

    def shot(self, tag):
        from PIL import Image
        path = os.path.join(self.args.work, "shots", f"{self.args.app}-{self.args.mode}-{tag}.png")
        self.office.screenshot(path)
        with Image.open(path) as image:
            return image.convert("RGB")

    def open_tab(self, name):
        data = layout()
        tab = next((t for t in data["tabs"] if t["name"] == name), None)
        if tab is None:
            return False
        if not tab["selected"]:
            gui.click(self.args.display, tab["box"])
            gui.xdo(self.args.display, "mousemove", *map(str, PARK))
            time.sleep(1)
        return any(t["selected"] and t["name"] == name for t in layout()["tabs"])

    def dispatch(self, command):
        frame = self.office.desktop().getCurrentFrame() or self.office.desktop().getFrames().getByIndex(0)
        self.office.dispatch(frame, command)
        time.sleep(1)

    def stop(self):
        """Close without the save prompt: the probes change character attributes, and a modal "save changes?" dialog
        would block terminate() for good."""
        if self.office is None:
            return
        try:
            components = self.office.desktop().getComponents().createEnumeration()
            while components.hasMoreElements():
                component = components.nextElement()
                if hasattr(component, "setModified"):
                    component.setModified(False)
        except Exception:  # noqa: BLE001 - the office may already be gone
            pass
        self.office.stop()


def sweep(session):
    """Tab strip at the widest width, then every always-visible tab at every width, widest first."""
    widths = sorted(session.config["widths"], reverse=True)
    top = session.resize(widths[0])
    names = [t["name"] for t in top["tabs"]]
    result = {"tabs": names, "pages": {}}
    for name in names:
        if name in session.config["skip_tabs"]:
            continue
        session.resize(widths[0])
        if not session.open_tab(name):
            result["pages"][name] = {"error": "tab did not open"}
            continue
        page = {}
        for width in widths:
            data = session.resize(width)
            page[str(width)] = {"groups": [{"caption": g["caption"], "box": g["box"]} for g in data["groups"]],
                                "chevron": data["chevron"], "banner": data["banner"], "height": data["height"],
                                "group_buttons": [b["name"] for b in data["buttons"] if b["name"] and b["box"][3] >= 50]}
        result["pages"][name] = page
    session.resize(session.config["probe_width"])
    return result



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, choices=("writer", "calc", "impress"))
    parser.add_argument("--mode", default="light", choices=("light", "dark"))
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--port", type=int, default=7650)
    parser.add_argument("--out", required=True)
    parser.add_argument("--stages", default="sweep,probes,gallery", help="a subset, to debug one stage")
    args = parser.parse_args()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    config = load_config()
    session = Session(args, config)
    observation = {"app": args.app, "mode": args.mode, "errors": []}

    def save():
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(observation, handle, ensure_ascii=False, indent=1)

    home = "Trang đầu"
    stages = [("probes", lambda: probes(session, home))]
    if args.mode == "light":
        stages.insert(0, (None, lambda: sweep(session)))
        if args.app == "writer":  # last: the gallery's More button may open the Styles deck
            stages.append(("gallery", lambda: gallery(session, home)))
    stages = [(k, f) for k, f in stages if (k or "sweep") in args.stages.split(",")]
    try:
        session.start()
        for key, stage in stages:
            try:
                result = stage()
                if key is None:
                    observation.update(result)
                else:
                    observation[key] = result
            except Exception as error:  # noqa: BLE001 - recorded; the scorer counts missing parts as failed
                observation["errors"].append(f"{key or 'sweep'}: {error!r}")
            save()
    except Exception as error:  # noqa: BLE001
        observation["errors"].append(f"start: {error!r}")
    finally:
        session.stop()
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
