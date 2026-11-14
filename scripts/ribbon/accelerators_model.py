# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard shortcuts as officecfg resolves them, for the shortcut parity check (scripts/check-keytips-parity.py).

Accelerators.xcu maps key codes ("S_MOD1") to commands per module (com.sun.star.text.TextDocument, ...) and globally;
a module binding wins over the global one, a later file (an extension's Accelerators.xcu) over an earlier one. A value
with install:module is kept only for its platform: Windows and Linux are "unxwnt". The Vietnamese UI uses the en-US
value unless a "vi" one exists.
"""
import re
import xml.etree.ElementTree as ET

OOR = "{http://openoffice.org/2001/registry}"
INSTALL = "{http://openoffice.org/2004/installation}"
LANG = "{http://www.w3.org/XML/1998/namespace}lang"
ACCELERATORS = "officecfg/registry/data/org/openoffice/Office/Accelerators.xcu"
EXTENSION = "extensions/hst-vietnamese-tools/Accelerators.xcu"
MODULES = {"writer": "com.sun.star.text.TextDocument", "calc": "com.sun.star.sheet.SpreadsheetDocument",
           "impress": "com.sun.star.presentation.PresentationDocument", "draw": "com.sun.star.drawing.DrawingDocument"}


def command_value(node, platform="unxwnt"):
    prop = node.find(f"prop[@{OOR}name='Command']")
    if prop is None:
        return None
    values = [v for v in prop.findall("value") if v.get(LANG) != "x-no-translate"]
    if any(v.get(INSTALL + "module") for v in values):
        values = [v for v in values if v.get(INSTALL + "module") == platform]
    for lang in ("vi", "en-US"):
        for value in values:
            if value.get(LANG) == lang:
                return (value.text or "").strip()
    return None


def load(paths, platform="unxwnt"):
    """{scope: {key code: command}}; scope is "Global" or a module name. Primary keys win over secondary ones."""
    found = {}
    for path in paths:
        root = ET.parse(path).getroot()
        for kind in ("PrimaryKeys", "SecondaryKeys"):
            keys = root.find(f"node[@{OOR}name='{kind}']")
            if keys is None:
                continue
            scopes = [("Global", keys.find(f"node[@{OOR}name='Global']"))]
            modules = keys.find(f"node[@{OOR}name='Modules']")
            if modules is not None:
                scopes += [(node.get(OOR + "name"), node) for node in modules.findall("node")]
            for scope, node in scopes:
                if node is None:
                    continue
                bound = found.setdefault(scope, {})
                names = [key.get(OOR + "name") for key in node.findall("node")]
                twice = sorted({n for n in names if names.count(n) > 1})
                if twice:  # officecfg refuses to build such a file ("Duplicate node/prop")
                    raise ValueError(f"{path}: {kind}/{scope} defines {', '.join(twice)} twice")
                for key in node.findall("node"):
                    value = command_value(key, platform)
                    if value is None:
                        continue
                    if kind == "PrimaryKeys" or key.get(OOR + "name") not in bound:
                        bound[key.get(OOR + "name")] = value
    return found


def effective(bindings, app, key):
    """Command (without .uno: and arguments) of a key in an HST app, or "" when the key is free."""
    command = bindings.get(MODULES[app], {}).get(key) or bindings.get("Global", {}).get(key) or ""
    return command.replace(".uno:", "").split("?", 1)[0]


def patch_bindings(text):
    """[(key code, command)] that a patch's new side binds: a `<node oor:name="KEY"` followed, within the node, by an
    en-US value, on context or added lines of a hunk."""
    found, key = [], None
    for line in text.splitlines():
        if line.startswith(("---", "+++", "-", "@@")) or not line:
            continue
        body = line[1:]
        start = re.search(r'<node oor:name="([A-Z0-9_]+)" oor:op="replace">', body)
        if start:
            key = start.group(1)
            continue
        value = re.search(r'<value xml:lang="en-US"(?: install:module="unxwnt")?>([^<]+)</value>', body)
        if key and value and line.startswith("+"):
            found.append((key, value.group(1).replace(".uno:", "").split("?", 1)[0]))
        if "</node>" in body:
            key = None
    return found
