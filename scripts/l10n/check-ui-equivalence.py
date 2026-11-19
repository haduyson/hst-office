#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Compare dialog and .hrc gettext resources in two Linux installations.

dump reads installed .ui/.mo plus the matching, fully patched LibreOffice source.
Use --hst on the separated build to check its composed domains in vi and en_US.
The output records catalog hits (including translations identical to English),
source fallback and untranslated literal UI properties separately. Plural strings
are checked at n=1 and n=2, covering the English and Vietnamese plural forms.
Text is compared before runtime substitutions (e.g. %PRODUCTNAME).

compare writes all changed/added/removed strings, both builds' vi fallbacks,
and a summary. Exit 1 means differences or Vietnamese source fallback in the
candidate, exit 2 means missing/malformed inputs. A base dump can be retained
before the candidate is built. Use installations and sources from pinned jobs.
"""
import argparse
import ast
from collections import Counter, defaultdict
import gettext
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

LANGUAGES = {"en": ("en_US", "en"), "vi": ("vi_VN", "vi")}
TARGET = re.compile(r"\bgb_AllLangMoTarget_AllLangMoTarget\s*,\s*([\w-]+)\s*\)")
STRING = r'"(?:\\.|[^"\\])*"'
COMMENTS = re.compile(STRING + r"|//[^\n]*|/\*[\s\S]*?\*/")
STRINGS = r"(?:(?:u8)?" + STRING + r"\s*)+"
CALL = re.compile(r"\b(NC_|NNC_|TranslateId|TranslateNId)\s*([({])")
ARGS = re.compile(r"\s*(" + STRINGS + r"),\s*(" + STRINGS + r")(?:,\s*(" + STRINGS + r"))?([)}])")
LITERAL_PROPERTIES = {
    "label", "text", "title", "subtitle", "tooltip-text", "tooltip-markup", "placeholder-text",
    "primary-text", "secondary-text", "message", "comments", "copyright", "license",
    "AtkObject::accessible-name", "AtkObject::accessible-description",
}


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def module_domains(source):
    domains = {}
    for path in sorted(source.glob("*/AllLangMoTarget_*.mk")):
        names = TARGET.findall(path.read_text(encoding="utf-8"))
        for name in names:
            if name.startswith("hst-"):
                continue
            module = path.parent.name
            if module in domains and domains[module] != name:
                raise ValueError(f"ambiguous .hrc domain for {module}: {name}, {domains[module]}")
            domains[module] = name
    if not domains:
        raise ValueError(f"{source}: no AllLangMoTarget declarations")
    return domains


def hrc_resources(path):
    body = path.read_text(encoding="utf-8").replace("\\\n", "")
    body = COMMENTS.sub(lambda m: " " if m[0].startswith("/") else m[0], body)
    body = re.sub(r"(?m)^\s*#\s*define\s+(?:NC_|NNC_)\([^\n]*", "", body)
    body = re.sub(r"(?m)^def NC_\([^\n]*", "", body)
    for match in CALL.finditer(body):
        args = ARGS.match(body, match.end())
        plural = match[1] in ("NNC_", "TranslateNId")
        if not args or bool(args[3]) != plural or (match[2], args[4]) not in (("(", ")"), ("{", "}")):
            raise ValueError(f"{path}: unsupported translation expression: {body[match.start():match.end()+90]}")
        context, singular, *plurals = (
            "".join(ast.literal_eval(s) for s in re.findall(STRING, value))
            for value in args.groups()[:3] if value is not None
        )
        prefix = body[body.rfind("\n", 0, match.start()) + 1:match.start()]
        symbol = re.search(r"(?:#\s*define\s+|\b(?:TranslateN?Id|TabData)\s+)(\w+)", prefix)
        yield (symbol[1] if symbol else context), context, singular, plurals


def headers(source):
    for root, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in
                         {"instdir", "workdir", "workdir_for_build", "external", "translations"})
        for name in sorted(files):
            if name.endswith(".hrc"):
                yield Path(root) / name


def ui_resources(root, owner=""):
    # The nearest widget owns its properties and list entries. Repeated items
    # within an object are distinguished by their order, including reused stock keys.
    if root.tag in ("object", "template"):
        owner = root.get("id") or root.get("class") or owner
    prop = root.get("name", "").replace("_", "-")
    translated = root.get("translatable") in ("yes", "true", "1")
    if translated or root.tag in ("item", "col") or (root.tag == "property" and prop in LITERAL_PROPERTIES):
        text = "".join(root.itertext())
        if text:
            yield (owner, root.tag, prop or root.get("id", "")), root.get("context", ""), text, translated
    for child in root:
        yield from ui_resources(child, owner)


def wizard_domain(path):
    variables = {}
    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    variables[target.id] = statement.value.value
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "textdomain":
                arg = call.args[0]
                return variables[arg.id] if isinstance(arg, ast.Name) else ast.literal_eval(arg)
    raise ValueError(f"{path}: cannot determine installed wizard gettext domain")


class Catalogs:
    def __init__(self, root):
        self.messages = defaultdict(list)
        self.digests = {}
        for lang, locales in LANGUAGES.items():
            for locale in locales:
                for path in sorted((root / locale / "LC_MESSAGES").glob("*.mo")):
                    with path.open("rb") as stream:
                        catalog = gettext.GNUTranslations(stream)
                    self.messages[lang, path.stem].append((str(path.relative_to(root)), catalog))
                    self.digests[str(path.relative_to(root))] = file_digest(path)
        if not any(lang == "vi" for lang, _ in self.messages):
            raise ValueError(f"{root}: no installed Vietnamese catalogs")

    def resolve(self, lang, domain, context, singular, plural, number):
        key = context + "\x04" + singular if context else singular
        for path, messages in self.messages.get((lang, domain), ()):
            # gettext's public API returns msgid for both a miss and a legitimate
            # identity translation. Record membership separately to prove coverage.
            if plural is None:
                forms = (key, (key, messages.plural(1)))
            else:
                forms = ((key, messages.plural(number)),)
            for form in forms:
                value = messages._catalog.get(form)
                if value:
                    return [value, path]
        return [plural if plural is not None and number != 1 else singular, "source"]


def dump(source, install, hst):
    domains = module_domains(source)
    configured = set(domains.values())
    catalogs = Catalogs(install / "program/resource")
    if hst:
        header = source / "hst/l10n/domains.hxx"
        routed = set()
        for line in header.read_text(encoding="ascii").splitlines():
            match = re.fullmatch(r"HST_CATALOG\(([\w-]+),[\w/.-]+\)", line)
            if not match:
                raise ValueError(f"{header}: unexpected domain declaration {line!r}")
            routed.add(match[1])
        if routed != configured:
            raise ValueError(f"{header}: routes differ from module targets: {sorted(routed ^ configured)}")
        for domain in sorted(configured):
            for lang in LANGUAGES:
                if not catalogs.messages.get((lang, "hst-" + domain)):
                    raise ValueError(f"missing installed {lang}/hst-{domain}.mo")
    # embeddedobj calls Translate::Create("emo") despite having no MO target.
    domains.setdefault("embeddedobj", "emo")
    rows, inputs = {}, {}
    occurrences = Counter()

    def record(key, domain, context, singular, plural=None, translated=True):
        occurrences[key] += 1
        for number in ([1, 2] if plural is not None else [1]):
            identifier = json.dumps([*key, occurrences[key], number], ensure_ascii=False)
            rows[identifier] = {
                "domain": domain, "context": context, "msgid": singular, "msgid_plural": plural,
                **{lang: catalogs.resolve(lang, domain, context, singular, plural, number)
                   if translated else [singular, "literal"] for lang in LANGUAGES},
            }

    ui_files = sorted((install / "share").rglob("*.ui"))
    hrc_count = 0
    for path in ui_files:
        root = ET.parse(path).getroot()
        rel = path.relative_to(install).as_posix()
        inputs["install/" + rel] = file_digest(path)
        domain = root.get("domain", "")
        for key, context, singular, translated in ui_resources(root):
            if translated and not domain:
                raise ValueError(f"{path}: no translation domain")
            if hst and translated and domain in configured:
                raise ValueError(f"{path}: still requests {domain}, expected hst-{domain}")
            record(("ui", rel, *key), domain, context, singular, translated=translated)
    for path in headers(source):
        rel = path.relative_to(source)
        module = rel.parts[1] if rel.parts[0] == "include" else rel.parts[0]
        if rel.as_posix() == "hst/ribbon/lo/ribbon-custom-strings.hrc":
            module = "sfx2"  # SfxResId in the ribbon dialog and controller
        inputs["source/" + rel.as_posix()] = file_digest(path)
        python_domain = None
        if rel.as_posix() == "wizards/com/sun/star/wizards/common/strings.hrc":
            # Python's gettext calls never go through Translate::Create.
            path = install / "program/wizards/common/strings.hrc"
            inputs["install/program/wizards/common/strings.hrc"] = file_digest(path)
            python_domain = wizard_domain(path)
        for symbol, context, singular, plurals in hrc_resources(path):
            hrc_count += 1
            if module not in domains:
                raise ValueError(f"{rel}: unknown .hrc resource domain")
            domain = domains[module]
            if python_domain:
                domain = python_domain
            elif hst and domain in configured:
                domain = "hst-" + domain
            record(("hrc", rel.as_posix(), symbol), domain, context, singular, *plurals)
    if not hrc_count or not any(key[0] == "ui" for key in occurrences):
        raise ValueError("missing installed .ui or matching source .hrc resources")
    return {"schema": 1, "hst": hst, "inputs": inputs, "catalogs": catalogs.digests,
            "ui_files": len(ui_files), "hrc_messages": hrc_count, "rows": rows}


def write_json(path, data):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def compare(base, candidate, output):
    if base.get("schema") != 1 or candidate.get("schema") != 1 or base["hst"] or not candidate["hst"]:
        raise ValueError("expected a base dump and a separated (--hst) candidate dump")
    for capture in (base, candidate):
        if not all(capture.get(k) for k in ("ui_files", "hrc_messages", "rows", "inputs", "catalogs")):
            raise ValueError("incomplete resource dump")
    old, new = base["rows"], candidate["rows"]
    output.mkdir(exist_ok=True, parents=True)
    differences, fallbacks, untranslated = [], [], []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        for lang in LANGUAGES:
            av, bv = a[lang][0] if a else None, b[lang][0] if b else None
            if av != bv:
                differences.append({"key": json.loads(key), "language": lang, "base": av, "candidate": bv})
        af, bf = bool(a and a["vi"][1] == "source"), bool(b and b["vi"][1] == "source")
        if a and b and a["vi"][1] != "literal" and b["vi"][1] == "literal":
            untranslated.append(json.loads(key))
        if af or bf:
            fallbacks.append({"key": json.loads(key), "base": a["vi"][0] if af else None,
                              "candidate": b["vi"][0] if bf else None})
    # An empty resource file disappearing also signals a packaging mismatch.
    missing = sorted(base["inputs"].keys() - candidate["inputs"].keys())
    added = sorted(candidate["inputs"].keys() - base["inputs"].keys())
    summary = {"base_rows": len(old), "candidate_rows": len(new), "text_differences": len(differences),
               "base_vi_fallbacks": sum(row["base"] is not None for row in fallbacks),
               "candidate_vi_fallbacks": sum(row["candidate"] is not None for row in fallbacks),
               "lost_translation_flags": len(untranslated),
               "added_resources": added, "removed_resources": missing}
    write_json(output / "differences.json", differences)
    write_json(output / "lost-translation-flags.json", untranslated)
    write_json(output / "vi-fallbacks.json", fallbacks)
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return int(bool(differences or summary["candidate_vi_fallbacks"] or untranslated or missing or added))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("dump")
    capture.add_argument("--install", type=Path, required=True, help="Linux installation root containing program/ and share/")
    capture.add_argument("--source", type=Path, required=True, help="matching patched LibreOffice source tree")
    capture.add_argument("--hst", action="store_true", help="require separated domains on the candidate")
    capture.add_argument("--output", type=Path, required=True)
    diff = sub.add_parser("compare")
    diff.add_argument("--base", type=Path, required=True)
    diff.add_argument("--candidate", type=Path, required=True)
    diff.add_argument("--output", type=Path, required=True, help="directory for reports")
    args = parser.parse_args()
    if args.command == "dump":
        data = dump(args.source, args.install, args.hst)
        write_json(args.output, data)
        misses = sum(row["vi"][1] == "source" for row in data["rows"].values())
        print(f"{data['ui_files']} UI files, {data['hrc_messages']} HRC messages, "
              f"{len(data['rows'])} rows, {misses} Vietnamese source fallbacks")
        return 0
    return compare(json.loads(args.base.read_text(encoding="utf-8")),
                   json.loads(args.candidate.read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, OSError, ValueError, ET.ParseError) as error:
        print(f"check-ui-equivalence: {error}", file=sys.stderr)
        sys.exit(2)
