# SPDX-License-Identifier: AGPL-3.0-only
"""The offline snapshot of check-access-keys.py (l10n/access-keys-snapshot.json) and the live HST menu."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from access_keys_model import APPS, ModelBuilder, build_model, finish

ROOT = Path(__file__).resolve().parents[2]


def merge_addons(model, addons):
    """Add the HST menu (Addons.xcu, a repository file) to the model. It is read live in every
    mode and never stored in the snapshot, so editing the HST menu cannot make the snapshot stale."""
    if not Path(addons).exists():
        return model
    builder = ModelBuilder(".")
    builder.containers = model["containers"]
    root = ET.parse(addons).getroot()
    for app, _prefix, _module, service in APPS:
        bar = next((c for c in builder.containers if c["type"] == "menus" and c["path"] == app), None)
        help_menu = next((c for c in builder.containers if c["app"] == app
                          and c.get("owner") == ".uno:HelpMenu"), None)
        if bar is not None:
            builder.addons(root, app, "com.sun.star." + service, bar, help_menu)
    return finish(builder.containers)


def structure(value):
    if isinstance(value, list):
        return [structure(v) for v in value]
    if isinstance(value, dict):
        return {k: structure(v) for k, v in value.items()
                if not (value.get("file") and k in ("vi", "fuzzy"))}
    return value


REGENERATE = ("regenerate it with `python3 scripts/l10n/check-access-keys.py --write-snapshot` "
              "(needs the patched upstream/libreoffice tree), rerun with --strict, and commit "
              "l10n/access-keys-snapshot.json together with any vi-overrides.jsonl fixes")


def stale_containers(model, snapshot):
    """Names of containers whose structure differs between the tree model and the snapshot."""
    new = {c["path"]: structure(c) for c in model["containers"]}
    old = {c["path"]: structure(c) for c in snapshot["containers"]}
    changed = sorted(k for k in new.keys() | old.keys() if new.get(k) != old.get(k))
    if not changed and structure(model) != structure(snapshot):
        changed = ["(snapshot metadata)"]
    return changed


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def write_snapshot(path, model):
    def compact(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    labels = sorted({compact(source) for c in model["containers"]
                     for item in c["items"] for source in item["labels"]})
    indices = {source: index for index, source in enumerate(labels)}
    containers = [dict(c, items=[dict(item, labels=[indices[compact(s)] for s in item["labels"]])
                                for item in c["items"]]) for c in model["containers"]]
    Path(path).write_text('{"version":2,"labels":[\n' + ",\n".join(labels)
                         + '\n],"containers":[\n' + ",\n".join(map(compact, containers))
                         + "\n]}\n", encoding="utf-8")


def read_snapshot(path):
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    if snapshot.get("version") != 2 or not snapshot.get("containers") or "labels" not in snapshot:
        raise ValueError("invalid access-keys snapshot, rerun --write-snapshot")
    labels = snapshot.pop("labels")
    for container in snapshot["containers"]:
        for item in container["items"]:
            item["labels"] = [labels[index] for index in item["labels"]]
    return snapshot


def load_model(tree, snapshot, write=False, addons=ROOT / "extensions/hst-vietnamese-tools/Addons.xcu"):
    model = load_tree_model(tree, snapshot, write)
    return merge_addons(model, addons)


def load_tree_model(tree, snapshot, write=False):
    if Path(tree).exists():
        model = build_model(tree)
        if write:
            write_snapshot(snapshot, model)
        elif not Path(snapshot).exists():
            raise ValueError(f"snapshot {snapshot} missing; {REGENERATE}")
        else:
            changed = stale_containers(model, read_snapshot(snapshot))
            if changed:
                raise ValueError("snapshot stale (menus/ribbon/labels in the tree changed: "
                                 + ", ".join(changed[:5]) + (", ..." if len(changed) > 5 else "")
                                 + f"); {REGENERATE}")
    elif write:
        raise ValueError("--write-snapshot requires an upstream tree")
    else:
        model = read_snapshot(snapshot)
    return model
