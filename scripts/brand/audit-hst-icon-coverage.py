#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Inventory static requests on installed surfaces; this is not a runtime trace.

Use the patch's HST -> Colibre (HST Dark -> Colibre Dark -> Colibre) chain.
Static keys are best-effort; this does not emulate command metadata/controllers.
Dynamic controllers, extension images and GTK/native stock icons remain separate.
"""
import argparse
import csv
import json
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET
import zipfile


def theme(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        links = dict(line.split() for line in z.read("links.txt").decode().splitlines()
                     if line.strip() and not line.startswith("#"))
    return names, links


def resolve(key, themes):
    for name, (files, links) in themes:
        stem = str(PurePosixPath(key).with_suffix(""))
        target = links.get(stem + ".png", links.get(stem + ".svg", key))
        for ext in (".png", ".svg"):
            candidate = str(PurePosixPath(target).with_suffix(ext))
            if candidate in files:
                return name, candidate
    return "dynamic-or-missing", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--themes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sources = {name: theme((args.themes if name.startswith("hst") else args.installed / "share/config") /
                           f"images_{name}.zip") for name in ("hst", "hst_dark", "colibre", "colibre_dark")}
    requests = set()
    base = args.installed / "share/config/soffice.cfg"
    for path in sorted(base.rglob("*")):
        if path.suffix not in (".ui", ".xml"):
            continue
        rel = path.relative_to(base).as_posix()
        if "notebookbar" in rel:
            surface = "ribbon"
        elif "sidebar" in rel:
            surface = "sidebar"
        elif "popupmenu" in rel:
            surface = "context-menu"
        elif "menubar" in rel:
            surface = "menu"
        elif "startcenter" in rel or "backing" in rel:
            surface = "start-center"
        elif path.suffix == ".ui":
            surface = "dialog-and-other-ui"
        else:
            continue
        root = ET.parse(path).getroot()
        for node in root.iter():
            values = []
            if node.tag == "property" and node.get("name") in ("icon-name", "action-name", "pixbuf") and node.text:
                values.append(node.text)
            values += [v for k, v in node.attrib.items() if k.endswith("}id") or k.endswith("}href")]
            for value in values:
                if value.startswith(".uno:"):
                    key = "cmd/sc_" + value[5:].lower() + ".png"
                elif re.search(r"\.(png|svg)$", value):
                    key = value
                else:
                    continue
                requests.add((surface, key, value, rel))
    args.out.mkdir(parents=True, exist_ok=True)
    rows, counts = [], {}
    for surface, key, value, path in sorted(requests):
        light, lp = resolve(key, [(n, sources[n]) for n in ("hst", "colibre")])
        dark, dp = resolve(key, [(n, sources[n]) for n in ("hst_dark", "colibre_dark", "colibre")])
        rows.append(dict(surface=surface, request=key, command_or_resource=value, ui=path,
                         light_theme=light, light_resource=lp, dark_theme=dark, dark_resource=dp))
        counts.setdefault(surface, {}).setdefault(light, set()).add(key)
    with (args.out / "static-coverage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {surface: {theme: len(keys) for theme, keys in themes.items()} for surface, themes in counts.items()}
    (args.out / "static-coverage.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
