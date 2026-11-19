#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Inventory HST localization resources against an unpacked upstream release.

Provide the applied tree including its *effective* vi POs after all baseline
overlays. Use --patches and --overrides from the same revision as that tree.
Compare source keys by location, so a key copied into an HST dialog
is listed even when it already exists upstream. JSONL values contain decoded
text, not PO escapes. Source defaults are templates before runtime substitution.
"""
import argparse
import ast
import collections
import functools
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from po_io import parse_po

ROOT = Path(__file__).resolve().parents[2]
CXX = {".hrc", ".cxx", ".hxx", ".c", ".h", ".mm"}
UI_TEXT = {"label", "title", "tooltip-text", "text", "placeholder-text", "subtitle",
           "secondary-text", "AtkObject::accessible-name", "AtkObject::accessible-description"}
QUOTE = r'"(?:\\.|[^"\\])*"'
LITERAL = rf'(?:(?:u8|u|L)?{QUOTE}\s*)+'
CPP_COMMENTS = re.compile(QUOTE + r"""|'(?:\\.|[^'\\\n])*'|//[^\n]*|/\*[\s\S]*?\*/""")
ID_CALL = re.compile(rf'\b(?:NC_|TranslateId)\s*\(\s*(nullptr|{QUOTE})\s*,\s*({LITERAL})\)')
PLURAL_CALL = re.compile(rf'\bNNC_\s*\(\s*({QUOTE})\s*,\s*({LITERAL})\s*,\s*({LITERAL})\)')
BILINGUAL = re.compile(rf'(?:\bbVi(?:etnamese)?|isVietnameseUi\(\)|getLanguage\(\)\s*==\s*"vi")\s*\?\s*'
                       rf'({LITERAL})(?:_ustr)?\s*:\s*({LITERAL})(?:_ustr)?')
OOR = "{http://openoffice.org/2001/registry}"
LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def decoded(value):
    """Decode one PO-escaped field without changing raw UTF-8 characters."""
    return ast.literal_eval('"' + value + '"') if '\\' in value else value


def cpp_text(tokens):
    return "".join(ast.literal_eval(item) for item in re.findall(QUOTE, tokens))


def touched_paths(patches):
    """Final source files in the series, including HST files with an a/ header."""
    exists = {}
    for line in (patches / "series").read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if not name:
            continue
        patch = (patches / name).read_bytes()
        for match in re.finditer(rb"(?m)^--- (a/[^\s]+|/dev/null)[^\n]*\n\+\+\+ (b/[^\s]+|/dev/null)", patch):
            old, new = (field.decode() for field in match.groups())
            path = old[2:] if new == "/dev/null" else new[2:]
            exists[Path(path)] = new != "/dev/null"
    return sorted(path for path in exists if exists[path])


def module_of(path):
    if path.parts[:2] == ("hst", "ribbon"):
        return "sfx2"
    return path.parts[1] if path.parts[0] == "include" else path.parts[0]


def resource(kind, location, ctx, msgid, po=None, vi=None, plural=None):
    return kind, location, ctx, msgid, po, vi, plural


def cpp_resources(path, content):
    if "qa" in path.parts or "test" in path.parts or "tests" in path.parts:
        return
    content = content.replace("\\\n", "")
    content = CPP_COMMENTS.sub(lambda m: " " if m[0].startswith("/") else m[0], content)
    module = module_of(path)
    po = module + "/messages.po"
    for match in (*ID_CALL.finditer(content), *PLURAL_CALL.finditer(content)):
        ctx = "" if match[1] == "nullptr" else cpp_text(match[1])
        text = cpp_text(match[2])
        prefix = content[content.rfind("\n", 0, match.start()) + 1:match.start()]
        symbol = re.search(r"(?:#define\s+|TranslateId\s+)(\w+)(?:\s*=)?\s*$", prefix)
        # Inline references in these dialogs intentionally reuse an upstream domain.
        ribbon_spacing = (path.name == "ribbon-customize-dialog.cxx"
                          and ctx.startswith(("paralrspacing|", "paraulspacing|")))
        catalog = "svx/messages.po" if ribbon_spacing else po
        plural = cpp_text(match[3]) if match.re is PLURAL_CALL else None
        yield resource("hrc" if path.suffix == ".hrc" else "cpp-id",
                       symbol[1] if symbol else ctx, ctx, text, catalog, plural=plural)
    for array in re.finditer(r"\bTranslateId\s+(\w+)\[\]\s*=\s*\{(.*?)\};", content, re.S):
        for match in re.finditer(rf'\{{\s*({QUOTE})\s*,\s*({LITERAL})\}}', array[2]):
            yield resource("cpp-id", array[1], cpp_text(match[1]), cpp_text(match[2]), po)
    for match in BILINGUAL.finditer(content):
        en, vi = cpp_text(match[2]), cpp_text(match[1])
        if path.name == "about.cxx":
            # lcl_GetMiscString(true) for every About dialog, false for every copy action.
            yield resource("cpp-literal", "About/Sheets", "", vi)
            yield resource("cpp-literal", "Copy version info/Sheets", "", en)
        else:
            yield resource("cpp-inline", en, "", en, vi=vi)
    for match in re.finditer(rf'\b(set_label|set_title|set_tooltip_text|set_accessible_name|'
                             rf'set_accessible_description|SetText)\s*\(\s*({LITERAL})(?:_ustr)?\s*\)', content):
        if cpp_text(match[2]):
            yield resource("cpp-literal", match[1], "", cpp_text(match[2]))
    pair = rf'\{{\s*u({QUOTE})\s*,\s*u({QUOTE})\s*\}}'
    if path.name in {"elementtemplates.cxx", "hstpageartsets.cxx", "ThemeColorsPaneBase.cxx"}:
        for match in re.finditer(pair, content):
            key, value = (cpp_text(field) for field in match.groups())
            if path.name == "ThemeColorsPaneBase.cxx":
                yield resource("cpp-inline", key, "", key, vi=value)
            else:
                yield resource("cpp-literal", key, "", value)
    if path.name in {"backingwindow.cxx", "hststartcenterwindow.cxx"}:
        for match in re.finditer(rf'\{{\s*u({QUOTE})_ustr,\s*u({QUOTE})_ustr,\s*u"https?://', content):
            name, tagline = (cpp_text(field) for field in match.groups())
            yield resource("cpp-literal", name + "/name", "", name)
            yield resource("cpp-literal", name + "/tagline", "", tagline)
    # These controls concatenate static copy with runtime vendor/product names
    # or document data. Preserve the literal fragments, including whitespace.
    fragments = {
        "about.cxx": ("sVendorTextStr", "aCopyrightString"),
        "recentdocsview.cxx": ("maWelcomeLine1", "maWelcomeLine2"),
        "spsuppHelper.cxx": ("sErrorMsg",),
        "hstbackstagewindow.cxx": ("aLine1", "aLine2"),
    }
    for symbol in fragments.get(path.name, ()):
        pattern = rf'\b{symbol}\s*(?:\(|\+=|=)\s*(u{QUOTE}.*?)' + (
            r'\)\s*\n' if symbol.startswith("maWelcomeLine") else r';\s*\n')
        for init in re.finditer(pattern, content, re.S):
            for match in re.finditer(LITERAL, init[1]):
                value = cpp_text(match[0])
                if value:
                    yield resource("cpp-fragment", symbol, "", value)
    if path.name == "dp_gui_dialog2.cxx":
        for match in re.finditer(rf'bVietnamese\s*\?\s*xInfoBox->get_primary_text\(\)\s*:\s*({LITERAL})', content):
            yield resource("cpp-context", "extension-warning", "RID_STR_WARNING_INSTALL_EXTENSION",
                           cpp_text(match[1]), po)
        button = rf'bVietnamese\s*\?\s*({LITERAL})_ustr\s*:\s*GetStandardText\(StandardButtonType::(\w+)\)'
        for match in re.finditer(button, content):
            for platform, mnemonic in (("Windows", ""), ("Unix", "~")):
                yield resource("cpp-inline", "extension/" + match[2] + "/" + platform, "",
                               mnemonic + match[2], vi=cpp_text(match[1]))


def packaging_resources(path, content):
    if path.name == "control":
        for key, text in re.findall(r"(?m)^(Description|Maintainer): (.*)$", content):
            yield resource("packaging", key, "", text)
        return
    if path.suffix == ".scp":
        for section, block in re.findall(r"(?ms)^FolderItem (\w+)\s*\n(.*?)^End$", content):
            for key, text in re.findall(r'(?m)^\s*(Name|Tooltip) = "(.*?)";', block):
                yield resource("packaging", section + "/" + key, "", text)
        return
    if path.suffix == ".rc":
        for key, value in re.findall(r'(?m)^\s*VALUE "(ProductName|LegalCopyright)",\s*(' + QUOTE + ')', content):
            yield resource("packaging", key, "", cpp_text(value).rstrip("\0"))
        return
    for block in re.findall(r"(?ms)^Start\n(.*?)^End$", content):
        fields = dict(re.findall(r'(?m)^(module|description|vendor|copyright) = "(.*)"$', block))
        for key in ("description", "vendor", "copyright"):
            if key in fields:
                yield resource("packaging", fields["module"] + "/" + key, "", fields[key])


def xml_resources(path, content, aliases):
    if path.suffix == ".xml" and not re.search(r'(?:menu:label|toolbar:text)="', content):
        return
    if path.suffix in {".xcu", ".xcs"} and 'xml:lang="en-US"' not in content:
        return
    if path.parts[:4] == ("filter", "source", "config", "fragments"):
        content = '<fragment xmlns:oor="http://openoffice.org/2001/registry">' + content + "</fragment>"
    root = ET.fromstring(content)
    module = module_of(path)
    domain = root.get("domain", module)
    po = aliases.get(domain, domain) + "/messages.po"
    def walk(elem, widget="", parents=()):
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "object":
            widget = elem.get("id", widget)
        if path.suffix == ".ui":
            name = elem.get("name", tag)
            translatable = elem.get("translatable", "").lower() in {"true", "yes", "1"}
            if translatable or (tag == "property" and name in UI_TEXT) or tag in {"item", "col"}:
                value = "".join(elem.itertext())
                if value:
                    location = "/".join(filter(None, (widget, name, elem.get("id"))))
                    yield resource("ui" if translatable else "ui-literal", location,
                                   elem.get("context", ""), value, po if translatable else None)
        elif path.suffix == ".xml":
            attributes = {k.rsplit("}", 1)[-1]: v for k, v in elem.attrib.items()}
            value = attributes.get("label") or attributes.get("text")
            if value:
                yield resource("xml-literal", attributes.get("id", attributes.get("href", tag)), "", value)
        elif tag == "prop":
            name = elem.get(OOR + "name")
            texts = {item.get(LANG): (item.text or "") for item in elem if item.tag == "value"}
            value = texts.get("en-US")
            if value and name and not (name == "Command" or path.name == "Accelerators.xcu"):
                access = ".".join(parents)
                ctx = "\n".join([path.name, access, name, "value.text"])
                yield resource("xcu", access + "/" + name, ctx, value, str(path.parent) + ".po", texts.get("vi"))
        if tag == "component-data":
            parents = (".." + elem.get(OOR + "name"),)
        elif tag == "node":
            parents = (*parents, elem.get(OOR + "name", ""))
        for child in elem:
            yield from walk(child, widget, parents)
    yield from walk(root)


def ini_resources(path, content):
    section = ""
    fields = collections.defaultdict(dict)
    for line in content.splitlines():
        header = re.fullmatch(r"\[([^\]]+)\]", line.strip())
        if header:
            section = header[1]
        elif "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            fields[section][key.strip()] = value.strip()
    for section, values in fields.items():
        if path.suffix == ".ulf" and "en-US" in values:
            ctx = "\n".join([path.name, section, "LngText.text"])
            yield resource("ulf", section, ctx, values["en-US"].strip('"'),
                           str(path.parent) + ".po", values.get("vi", "").strip('"') or None)
        elif path.suffix == ".desktop":
            for key in ("Name", "Comment", "GenericName", "Keywords", "UnityQuickList"):
                if key in values:
                    ctx = "\n".join(["launcher.ulf", path.stem + "_" + key, "LngText.text"])
                    yield resource("desktop", section + "/" + key, ctx, values[key],
                                   "sysui/desktop/share.po", values.get(key + "[vi]"))


def resources(path, tree, aliases):
    filename = tree / path
    if not filename.is_file():
        return set()
    if path.suffix in CXX:
        extractor = cpp_resources
    elif path.suffix in {".ui", ".xcu", ".xcs", ".xml"}:
        extractor = functools.partial(xml_resources, aliases=aliases)
    elif path.suffix in {".ulf", ".desktop"}:
        extractor = ini_resources
    elif (path.parts[:3] == ("setup_native", "source", "packinfo")
          or path.name.startswith("folderitem_") and path.suffix == ".scp"
          or str(path) in {"sysui/desktop/debian/control", "include/default.rc"}):
        extractor = packaging_resources
    else:
        return set()
    try:
        return set(extractor(path, filename.read_text(encoding="utf-8")))
    except (ValueError, SyntaxError, ET.ParseError) as exc:
        raise ValueError(f"{filename}: {exc}") from exc


@functools.lru_cache(maxsize=None)
def catalog(root, po):
    if not po:
        return {}, {}
    path = root / po
    if not path.exists():
        return {}, {}
    pairs = {}
    contexts = {}
    for entry in parse_po(path):
        if not entry["msgid"]:
            continue
        ctx, msgid, vi = (decoded(entry[k]) for k in ("msgctxt", "msgid", "msgstr"))
        vi = "" if entry["fuzzy"] else vi
        pairs[ctx, msgid] = vi
        contexts[ctx] = vi
    return pairs, contexts


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as out:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False), file=out)


def add_provenance(rows, overrides, args):
    """Record the authoring layers in addition to the effective PO lookup."""
    keys = {(row["file"], row["msgctxt"], row["msgid"]) for row in rows}
    layers = collections.defaultdict(list)
    # merge-vi fills empty/fuzzy entries only. Older translated rows are not
    # evidence that a matching overlay row actually supplied the translation.
    if args.patch_vi:
        premerge = args.patch_vi
        for path in sorted((args.overrides.parent / "vi").glob("*.jsonl")):
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                term = json.loads(line)
                key = term["file"], decoded(term["msgctxt"]), decoded(term["msgid"])
                if key in keys and not catalog(premerge, key[0])[0].get(key[1:]):
                    layers[key].append("l10n/vi/" + path.name)
    for row in overrides:
        key = row["file"], row["msgctxt"], row["en"]
        if key in keys:
            layers[key].append("l10n/" + args.overrides.name)
    for row in rows:
        key = row["file"], row["msgctxt"], row["msgid"]
        if row["file"] and row["vi_source"] == row["file"]:
            sources = list(layers[key])
            if not sources:
                sources = ["translations/source/vi/" + row["file"]]
            row["vi_inputs"] = sources
        else:
            row["vi_inputs"] = [row["vi_source"]]


def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    baseline = args.tree / "translations/source/vi"
    for path in (args.upstream_vi, baseline):
        if not (path / "sc/messages.po").is_file():
            raise ValueError(f"missing Vietnamese release catalogs in {path}")
    owned = []
    seen = set()
    aliases = {}
    for makefile in args.pristine.glob("*/AllLangMoTarget_*.mk"):
        for name, location in re.findall(r"gb_AllLangMoTarget_set_polocation,([\w-]+),([\w/-]+)\)",
                                         makefile.read_text(encoding="utf-8")):
            aliases[name] = location
    touched = touched_paths(args.patches)
    for path in touched:
        if not (args.tree / path).is_file():
            raise ValueError(f"missing series target {path} in {args.tree}")
        added = resources(path, args.tree, aliases) - resources(path, args.pristine, aliases)
        for kind, loc, ctx, msgid, po, inline_vi, plural in sorted(added, key=repr):
            entries, by_context = catalog(baseline, po)
            upstream, _ = catalog(args.upstream_vi, po)
            key = (ctx, msgid)
            # cfgex and ulfex locate translations by resource identifiers, even
            # when the English copy changed without a corresponding PO rename.
            text = by_context.get(ctx) if kind in {"xcu", "ulf", "desktop", "cpp-context"} else entries.get(key)
            source = po if text else None
            if inline_vi and not text:
                text, source = inline_vi, str(path)
            if not text:
                text, source = msgid, "source-default" if po else str(path)
            # The Windows association notice explicitly forces vi in every UI locale.
            en = text if str(path) == "cui/source/dialogs/fileextcheckdlg.cxx" and kind == "cpp-id" else msgid
            owned.append(dict(kind=kind, module=module_of(path), source=str(path), location=loc,
                              file=po, msgctxt=ctx, msgid=msgid, en=en, vi=text,
                              vi_source=source, in_upstream_catalog=key in upstream))
            if plural:
                owned[-1].update(msgid_plural=plural, en_plural=plural,
                                 vi_plural=text if source != "source-default" else plural)
            seen.add((po, *key))
    overrides = []
    for line in args.overrides.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        po = row["file"]
        ctx, old, new = (decoded(row[k]) for k in ("msgctxt", "msgid", "msgid_new" if row.get("msgid_new") else "msgid"))
        upstream, _ = catalog(args.upstream_vi, po)
        effective, _ = catalog(baseline, po)
        overrides.append(dict(file=po, module=po.split("/")[0], msgctxt=ctx, msgid=old, en=new,
                              requested_vi=decoded(row["msgstr"]), vi=effective.get((ctx, new)) or new,
                              reason=row["reason"], in_upstream_catalog=(ctx, old) in upstream,
                              matches_added_source=(po, ctx, new) in seen))
    # Cross-check the other direction. Include orphaned PO entries and new keys
    # whose source representation is outside the supported extractors.
    extra = []
    patch_overrides = []
    po_files = {str(Path(*path.parts[3:])) for path in touched
                if path.parts[:3] == ("translations", "source", "vi") and path.suffix == ".po"}
    po_files.update(row["file"] for row in overrides if row["en"] != row["msgid"])
    for po in sorted(po_files):
        upstream, _ = catalog(args.upstream_vi, po)
        effective, _ = catalog(baseline, po)
        if args.patch_vi:
            patched, _ = catalog(args.patch_vi, po)
            for key in sorted(upstream.keys() & patched.keys()):
                if patched[key] == upstream[key]:
                    continue
                ctx, msgid = key
                patch_overrides.append(dict(file=po, module=po.split("/")[0], msgctxt=ctx, msgid=msgid,
                                            upstream_vi=upstream[key], patch_vi=patched[key],
                                            effective_vi=effective.get(key), en=msgid))
        for ctx, msgid in sorted(effective.keys() - upstream.keys()):
            if (po, ctx, msgid) not in seen:
                extra.append(dict(kind="catalog-only", module=po.split("/")[0], file=po,
                                  msgctxt=ctx, msgid=msgid, en=msgid, vi=effective[ctx, msgid] or msgid,
                                  vi_source=po if effective[ctx, msgid] else "source-default"))
    add_provenance(owned + extra, overrides, args)
    write_jsonl(args.out / "owned.jsonl", owned)
    write_jsonl(args.out / "overrides.jsonl", overrides)
    write_jsonl(args.out / "catalog-only.jsonl", extra)
    if args.patch_vi:
        write_jsonl(args.out / "patch-overrides.jsonl", patch_overrides)
    print(f"{len(owned)} added source records, {len(overrides)} overrides, {len(extra)} additional PO keys")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pristine", "tree", "upstream-vi", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--patches", type=Path, default=ROOT / "patches/libreoffice")
    parser.add_argument("--overrides", type=Path, default=ROOT / "l10n/vi-overrides.jsonl")
    parser.add_argument("--patch-vi", type=Path,
                        help="baseline vi PO directory after patches, before merge-vi and overrides")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
