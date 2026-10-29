# SPDX-License-Identifier: AGPL-3.0-only
"""Validate the authored JSON contract using only the standard library."""
import re
import unicodedata
from collections import Counter
from pathlib import Path
from .odf import BASE, EXT, read_json


def validate(value, schema, document, path="$"):
    if "$ref" in schema:
        schema = document["$defs"][schema["$ref"].split("/")[-1]]
    if "oneOf" in schema:
        matches = 0
        for choice in schema["oneOf"]:
            try:
                validate(value, choice, document, path)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            raise ValueError(f"{path}: must match exactly one template schema")
        return
    def require(condition, message):
        if not condition:
            raise ValueError(f"{path}: {message}")
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if "type" in schema:
        require(type(value) is types[schema["type"]], "wrong type")
    if "const" in schema:
        require(value == schema["const"], "unexpected constant")
    if "enum" in schema:
        require(value in schema["enum"], "unsupported value")
    if isinstance(value, str):
        require(unicodedata.normalize("NFC", value) == value, "text must be NFC")
        require("\ufffd" not in value, "replacement character in text")
        require(len(value) >= schema.get("minLength", 0), "text too short")
        require(len(value) <= schema.get("maxLength", len(value)), "text too long")
        require(re.search(schema.get("pattern", ""), value) is not None, "pattern mismatch")
    if isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)), "array length")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), document, f"{path}[{i}]")
    if isinstance(value, dict):
        require(set(schema.get("required", [])) <= value.keys(), "missing required property")
        for key, item in value.items():
            child = schema.get("properties", {}).get(key)
            if child is None:
                child = next((s for p, s in schema.get("patternProperties", {}).items() if re.search(p, key)), None)
            require(child is not None or schema.get("additionalProperties", True), "unknown property " + key)
            if child is not None:
                validate(item, child, document, path + "." + key)


def safe_formula(formula):
    expression = re.sub(r'"[^"]*"', '""', formula)
    address = r"\.\$?[A-L]\$?(?:[1-9][0-9]*|\{row\})"
    expression = re.sub(r"\[" + address + r"(?::" + address + r")?\]", "0", expression)
    expression = re.sub(r"\b(?:SUM|IF)\b", "", expression)
    if re.search(r'[^0-9\s.+*/();<>=,"-]', expression) or any(c in formula for c in ["http:", "https:", "file:", "|", "\\"]):
        raise ValueError("Unsupported or external formula: " + formula)


def load(path=BASE / "templates/catalog.json"):
    path = Path(path)
    catalog = read_json(path)
    schema = read_json(BASE / "templates/schema.json")
    validate(catalog, schema, schema)
    entries = catalog["templates"]
    if Counter(e["module"] for e in entries) != {"writer": 7, "sheets": 6, "slides": 5}:
        raise ValueError("Catalog must contain 7 Writer, 6 Sheets, 5 Slides templates")
    if len({e["id"] for e in entries}) != 18:
        raise ValueError("Template IDs must be unique")
    sources = {}
    for entry in entries:
        module, ident = entry["module"], entry["id"]
        expected = {"source": f"{module}/{ident}.json", "output": f"{module}/{ident}.{EXT[module]}",
                    "preview": f"previews/{ident}.svg"}
        if any(entry[k] != v for k, v in expected.items()):
            raise ValueError("Noncanonical catalog path: " + ident)
        source = read_json(path.parent / entry["source"])
        validate(source, schema, schema)
        if source["id"] != ident or source["module"] != module:
            raise ValueError("Source identity does not match catalog")
        if module == "writer" and source["documentType"] != ident:
            raise ValueError("Writer document type does not match ID")
        if module == "sheets":
            for formula in list(source["totals"].values()) + [c["formula"] for c in source["columns"] if "formula" in c]:
                safe_formula(formula)
        if module == "slides" and {s["layout"] for s in source["slides"]} != {"title", "content", "section", "table", "chart"}:
            raise ValueError("Slides must provide every reusable layout")
        sources[ident] = source
    return catalog, sources
