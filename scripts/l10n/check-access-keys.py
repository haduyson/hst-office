#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check explicit Vietnamese menu/notebookbar mnemonics, with an offline CI snapshot.

Snapshot labels retain escaped PO msgid/msgstr, decoded msgctxt, and fallback
order. Only base PO translations/fuzzy flags are excluded from freshness checks.
Counts are duplicate-key groups, not pairs. Dynamic popup contents are outside
this static XML model; controls and contextual-only tab conflicts are warnings.
Exceptions match a problem's kind, container, uppercase key and exact label
multiset; kind defaults to collision. Stale exceptions fail --strict.
Snapshot v2 pools repeated label sources, with
one source/container per line to keep offline checks compact and reviewable.
"""
import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from po_io import parse_po  # noqa: E402

OOR = "{http://openoffice.org/2001/registry}"
MENU = "{http://openoffice.org/2001/menu}"
LANG = "{http://www.w3.org/XML/1998/namespace}lang"
UI_PO = "officecfg/registry/data/org/openoffice/Office/UI.po"
APPS = (
    ("Writer", "sw/uiconfig/swriter", "WriterCommands", "text.TextDocument"),
    ("Calc", "sc/uiconfig/scalc", "CalcCommands", "sheet.SpreadsheetDocument"),
    ("Impress", "sd/uiconfig/simpress", "DrawImpressCommands", "presentation.PresentationDocument"),
    ("Draw", "sd/uiconfig/sdraw", "DrawImpressCommands", "drawing.DrawingDocument"),
    ("Start Center", "framework/uiconfig/startmodule", "GenericCommands", "frame.StartModule"),
)


def unescape(value):
    return ast.literal_eval('"' + value + '"')


def escape(value):
    return json.dumps(value, ensure_ascii=False)[1:-1]


def mnemonic(label, markers="~"):
    index = 0
    while index + 1 < len(label):
        if label[index] in markers:
            if label[index + 1] != label[index]:
                return label[index + 1]
            index += 1
        index += 1
    return ""


def strip_mnemonics(label):
    # MnemonicGenerator::EraseAllMnemonicChars also removes CJK (~A) suffixes.
    return re.sub(r"\(~[A-Za-z]\)", "", label).replace("~", "")


def load_overrides(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[(row["file"], unescape(row["msgctxt"]),
                    row.get("msgid_new") or row["msgid"])] = row["msgstr"]
    return result


def label_text(source, overrides, english=False):
    if english:
        text = source["english"]
    else:
        key = (source["file"], source["msgctxt"], source["msgid"])
        vi = overrides.get(key, "" if source["fuzzy"] else source["vi"])
        text = unescape(vi) if vi else source["english"]
    text = text.replace("%PRODUCTNAME", "HST Office")
    return strip_mnemonics(text.rstrip(".")) if source.get("name") else text


def resolve(item, overrides, english=False):
    for source in item["labels"]:
        text = label_text(source, overrides, english)
        if text:
            return text, source["markers"]
    return "", "~"


class ModelBuilder:
    def __init__(self, tree):
        self.tree, self.po, self.commands, self.containers = Path(tree), {}, {}, []

    def label(self, english, file=None, context=None, vi="", markers="~", name=False):
        msgid = escape(english)
        if file and file not in self.po:
            path = self.tree / "translations/source/vi" / file
            self.po[file] = {(unescape(e["msgctxt"]), e["msgid"]): e
                             for e in parse_po(path)}
        entry = self.po.get(file, {}).get((context, msgid), {})
        return dict(file=file, msgctxt=context, msgid=msgid, english=english,
                    vi=entry.get("msgstr", escape(vi)), fuzzy=entry.get("fuzzy", False),
                    markers=markers, name=name)

    def command(self, module, command, mode="menu"):
        for config in dict.fromkeys((module, "GenericCommands")):
            if config not in self.commands:
                table = self.commands[config] = {}
                path = self.tree / "officecfg/registry/data/org/openoffice/Office/UI" / (config + ".xcu")
                if path.exists():
                    root = ET.parse(path).getroot()
                    # Commands win over Popups (emplace); module wins as a whole.
                    for section in ("Commands", "Popups"):
                        for node in root.findall(f"./node/node[@{OOR}name='{section}']/node"):
                            props = {}
                            for prop in node.findall("prop"):
                                value = prop.find(f"value[@{LANG}='en-US']")
                                if value is not None:
                                    kind = prop.get(OOR + "name")
                                    ctx = (f"{config}.xcu\n..{config}.UserInterface.{section}."
                                           f"{node.get(OOR + 'name')}\n{kind}\nvalue.text")
                                    props[kind] = self.label(value.text or "", UI_PO, ctx)
                            table.setdefault(node.get(OOR + "name"), props)
            if command in self.commands[config]:
                props = self.commands[config][command]
                order = {"menu": ("ContextLabel", "Label"),
                         "popup": ("PopupLabel", "ContextLabel", "Label"),
                         "name": ("Label",)}[mode]
                return [dict(props[p], name=mode == "name", markers="" if mode == "name" else "~")
                        for p in order if p in props]
        return []

    def container(self, path, kind, app):
        container = dict(path=path, type=kind, app=app, strict=kind != "controls", items=[])
        self.containers.append(container)
        return container

    @staticmethod
    def item(identifier, labels, command="", **extra):
        return dict(id=identifier, command=command, labels=labels, **extra)

    def menus(self, element, path, app, module, owner=""):
        container = self.container(path, "menus", app)
        container["owner"] = owner
        for node in element:
            if node.tag not in (MENU + "menu", MENU + "menuitem"):
                continue
            command = node.get(MENU + "id", "")
            explicit = node.get(MENU + "label", "")
            labels = ([self.label(explicit)] if explicit else []) + self.command(module, command)
            item = self.item(command, labels, command, auto=True)
            container["items"].append(item)
            popup = node.find(MENU + "menupopup")
            if popup is not None:
                title = strip_mnemonics(resolve(item, {}, True)[0]).rstrip(".…") or command
                self.menus(popup, path + " > " + title, app, module, command)
        return container

    def addons(self, root, app, module, bar, help_menu):
        def add(parent, container):
            for node in parent.findall("node"):
                def value(prop, lang=None):
                    suffix = f"[@{LANG}='{lang}']" if lang else ""
                    return node.findtext(f"prop[@{OOR}name='{prop}']/value{suffix}", "")
                context, command = value("Context"), value("URL")
                if (context and module not in context) or command == "private:separator":
                    continue
                title = value("Title", "en-US") or value("Title")
                labels = [self.label(title, vi=value("Title", "vi") or title)]
                item = self.item(node.get(OOR + "name"), labels, command, auto=True)
                submenu = node.find(f"node[@{OOR}name='Submenu']")
                if submenu is not None:
                    sub = self.container(container["path"] + " > " + strip_mnemonics(title), "menus", app)
                    add(submenu, sub)
                    if not sub["items"]:
                        self.containers.remove(sub)
                        continue
                container["items"].append(item)
        for section, container in (("OfficeMenuBar", bar), ("OfficeHelp", help_menu)):
            parent = root.find(f"./node[@{OOR}name='AddonUI']/node[@{OOR}name='{section}']")
            if parent is not None and container is not None:
                add(parent, container)

    def notebook(self, path, app, module, po):
        root = ET.parse(path).getroot()

        def ui_item(obj, tab=False, menu=False):
            props = {p.get("name"): p for p in obj.findall("property")}
            command = props["action-name"].text if "action-name" in props else ""
            prop = props.get("label")
            labels = []
            tool = obj.get("class", "") in ("GtkToolButton", "GtkMenuToolButton",
                                             "GtkToggleToolButton", "GtkRadioToolButton")
            if prop is not None:
                translatable = prop.get("translatable") == "yes"
                labels = [self.label(prop.text or "", po if translatable else None,
                                     prop.get("context"), markers="~" if tab or tool else "~_")]
            if tool:
                # ToolBox uses stripped Name first; HST's builder falls back to UI.
                labels = self.command(module, command, "name") + labels
            elif menu:
                labels += self.command(module, command, "popup")
            return self.item(obj.get("id", ""), labels, command or "", auto=menu)

        def controls(obj, container):
            if obj.get("class") == "GtkMenu":
                return  # Each GtkMenu gets its own container below.
            item = ui_item(obj)
            if item["labels"]:
                container["items"].append(item)
            for child in obj.findall("child/object"):
                controls(child, container)

        for notebook in root.iter("object"):
            tabs = notebook.findall("child[@type='tab']")
            if not tabs:
                continue
            bar = self.container(app + " > Tabs", "tab-bars", app)
            page = None
            for child in notebook.findall("child"):
                obj = child.find("object")
                if child.get("type") != "tab":
                    page = obj
                elif obj is not None and page is not None:
                    item = ui_item(obj, tab=True)
                    contexts = [s.get("name") for s in obj.findall("style/class")
                                if s.get("name", "").startswith("context-")]
                    item["contextual"] = bool(contexts) and "context-any" not in contexts
                    bar["items"].append(item)
                    title = strip_mnemonics(resolve(item, {}, True)[0]) or item["id"]
                    controls(page, self.container(app + " > Ribbon > " + title, "controls", app))
        for menu in root.findall(".//object[@class='GtkMenu']"):
            container = self.container(app + " > Ribbon > " + menu.get("id"), "controls", app)
            for obj in menu.findall("child/object"):
                if obj.get("class") in ("GtkMenuItem", "GtkCheckMenuItem", "GtkRadioMenuItem"):
                    container["items"].append(ui_item(obj, menu=True))


def build_model(tree):
    """Menus and notebookbars from the source tree (what the snapshot stores; no add-on menus)."""
    builder = ModelBuilder(tree)
    for app, prefix, module, service in APPS:
        path = Path(tree) / prefix / "menubar/menubar.xml"
        if not path.exists():
            continue  # Also permits small, partial source fixtures.
        builder.menus(ET.parse(path).getroot(), app, app, module)
        path = Path(tree) / prefix / "ui/notebookbar.ui"
        if app in ("Writer", "Calc", "Impress") and path.exists():
            builder.notebook(path, app, module, prefix.split("/")[0] + "/messages.po")
    if not builder.containers:
        raise ValueError("no menubars found in tree")
    return finish(builder.containers)


def finish(containers):
    for container in containers:
        container["items"].sort(key=lambda item: (item["id"], item["command"]))
    return dict(version=2, containers=sorted(containers, key=lambda c: (c["type"], c["path"])))


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


def load_exceptions(path):
    if not Path(path).exists():
        return []
    exceptions = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(exceptions, list):
        raise ValueError("access-key exceptions must be a list")
    seen = set()
    for entry in exceptions:
        kind = entry.get("kind", "collision") if isinstance(entry, dict) else None
        if (not isinstance(entry, dict) or set(entry) - {"kind"} != {"container", "key", "labels", "reason"}
                or kind not in ("collision", "non-ascii")
                or not all(isinstance(entry[k], str) and entry[k].strip()
                           for k in ("container", "key", "reason"))
                or entry["key"] != entry["key"].upper()
                or not isinstance(entry["labels"], list)
                or (len(entry["labels"]) != 1 if kind == "non-ascii" else len(entry["labels"]) < 2)
                or not all(isinstance(label, str) for label in entry["labels"])):
            raise ValueError("invalid access-key exception")
        identity = (kind, entry["container"], entry["key"], tuple(sorted(entry["labels"])))
        if identity in seen:
            raise ValueError("duplicate access-key exception")
        seen.add(identity)
    return exceptions


def check(model, overrides, exceptions=()):
    problems, info, summary = [], [], {}
    for container in model["containers"]:
        group = container["app"] + " menus" if container["type"] == "menus" else container["type"]
        counts = summary.setdefault(group, {"collisions": 0, "non-ascii": 0})
        keys = defaultdict(list)

        def report(kind, key, items, strict):
            problems.append(dict(container=container["path"], type=container["type"],
                                 kind=kind, key=key, items=items, strict=strict))
            counts["collisions" if kind == "collision" else kind] += 1

        for item in container["items"]:
            label, markers = resolve(item, overrides)
            char = mnemonic(label, markers)
            shown = dict(id=item["id"], command=item["command"], label=label,
                         contextual=item.get("contextual", False))
            if not char:
                info.append(dict(container=container["path"], kind="auto" if item.get("auto") else "none", **shown))
                continue
            keys[char.upper()].append(shown)
            if not (char.isascii() and char.isalnum()):
                report("non-ascii", char.upper(), [shown], container["strict"])
        for key, items in sorted(keys.items()):
            if len(items) > 1:
                strict = container["strict"] and not (container["type"] == "tab-bars"
                                                       and all(i["contextual"] for i in items))
                report("collision", key, items, strict)
    by_identity = {(p["kind"], p["container"], p["key"], tuple(sorted(i["label"] for i in p["items"]))): p
                   for p in problems}
    stale = []
    for entry in exceptions:
        identity = (entry.get("kind", "collision"), entry["container"], entry["key"], tuple(sorted(entry["labels"])))
        if identity in by_identity:
            by_identity[identity]["exception"] = entry["reason"]
        else:
            stale.append(entry)
    return dict(problems=problems, info=info, summary=summary, stale_exceptions=stale,
                strict_problems=sum(p["strict"] and "exception" not in p for p in problems) + len(stale))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", type=Path, default=ROOT / "upstream/libreoffice")
    parser.add_argument("--overrides", type=Path, default=ROOT / "l10n/vi-overrides.jsonl")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "l10n/access-keys-snapshot.json")
    parser.add_argument("--exceptions", type=Path, default=ROOT / "l10n/access-keys-exceptions.json")
    parser.add_argument("--addons", type=Path, default=ROOT / "extensions/hst-vietnamese-tools/Addons.xcu")
    parser.add_argument("--json", type=Path)
    for flag in ("strict", "write-snapshot", "verbose"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(argv)
    try:
        model = load_model(args.tree, args.snapshot, args.write_snapshot, args.addons)
        result = check(model, load_overrides(args.overrides), load_exceptions(args.exceptions))
        if args.json:
            write_json(args.json, result)
    except (OSError, ValueError, SyntaxError, KeyError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for problem in result["problems"]:
        labels = " | ".join(i["label"] for i in problem["items"])
        kind = "key" if problem["kind"] == "collision" else "non-ascii"
        severity = "strict" if problem["strict"] else "warning"
        if "exception" in problem:
            severity = "excepted: " + problem["exception"]
        print(f"{problem['container']}: {kind} {problem['key']}: {labels} [{severity}]")
    for entry in result["stale_exceptions"]:
        print(f"{entry['container']}: stale exception for key {entry['key']}: {entry['labels']} [strict]")
    if args.verbose:
        for item in result["info"]:
            print(f"{item['container']}: {item['kind']}: {item['label']} ({item['id']})")
    print(f"{'Container type':<24} {'Collisions':>10} {'Non-ASCII':>10}")
    for group, counts in sorted(result["summary"].items()):
        print(f"{group:<24} {counts['collisions']:>10} {counts['non-ascii']:>10}")
    print(f"Strict problems: {result['strict_problems']}; auto items: "
          f"{sum(i['kind'] == 'auto' for i in result['info'])} (details: --verbose/--json)")
    print(f"Excepted problems: {sum('exception' in p for p in result['problems'])}; "
          f"stale exceptions: {len(result['stale_exceptions'])}")
    return int(args.strict and result["strict_problems"] > 0)


if __name__ == "__main__":
    sys.exit(main())
