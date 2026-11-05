# SPDX-License-Identifier: AGPL-3.0-only
"""Bundled banner and menu contracts."""
import ast
import json
import os
import sys
from extension_content import ROOT, parse_xml


def check_banners(zf, names, errors):
    """Bundle contract: exact shared manifest, all scale images present, digest/size/magic verified."""
    sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
    from hst_office.banner_schema import parse_manifest
    from hst_office.banner_snapshot import encoded_items
    from hst_office.banner_verify import verify_image, valid_key
    from hst_office.update_logic import PUBLIC_KEY as UPDATE_KEY
    try:
        data = zf.read("data/banners.json")
        if data != open(os.path.join(ROOT, "data", "hst", "banners.json"), "rb").read():
            errors.append("stale bundled banners manifest")
        doc = parse_manifest(data, bundled=True)
        solutions = json.loads(zf.read("data/solutions.json"))["solutions"]
        company = json.loads(zf.read("banners/brands.json"))["hasontech"]
        solutions.append(dict(id="hasontech", **{k: company[k] for k in ("name", "tagline")}))
        if {i["id"]: i["tagline"] for i in doc["items"]} != {i["id"]: i["tagline"] for i in solutions}:
            errors.append("banner taglines differ from solutions/company artwork")
        key = banner_key(zf)
        if key and (not valid_key(key) or key == UPDATE_KEY):
            errors.append("invalid or non-separate configured banner public key")
        for item in doc["items"]:
            for scale, spec in item["image"].items():
                verify_image(zf.read(spec["url"]), spec, scale)
        images = {i["id"]: {s: zf.read(v["url"]) for s, v in i["image"].items()} for i in doc["items"]}
        encoded = encoded_items(doc, images, json.loads(zf.read("data/solutions.json"))["utm"])
        if json.loads(zf.read("data/banner-snapshots.json")) != encoded:
            errors.append("stale bundled banner snapshots")
        if "banners/fonts/OFL.txt" not in names:
            errors.append("missing bundled banner font license")
    except (KeyError, ValueError, OSError) as exc:
        errors.append("invalid bundled banners: %s" % exc)


def check_labels(zf, names, errors):
    """Menu labels in Addons.xcu must equal locales/{en,vi}.json menu strings."""
    if "Addons.xcu" not in names:
        errors.append("missing Addons.xcu")
        return
    dom = parse_xml(zf.read("Addons.xcu"), errors, "Addons.xcu")
    if not dom:
        return
    labels = {"en-US": set(), "vi": set()}
    for value in dom.getElementsByTagName("value"):
        lang = value.getAttribute("xml:lang")
        if lang in labels and value.firstChild:
            labels[lang].add(value.firstChild.data)
    for lang, code in (("en-US", "en"), ("vi", "vi")):
        menu = json.loads(zf.read("locales/%s.json" % code).decode("utf-8"))["menu"]
        missing = set(menu.values()) - labels[lang]
        if missing:
            errors.append("Addons.xcu lacks %s labels from locales/%s.json: %s" % (lang, code, sorted(missing)))




def banner_key(zf):
    source = ast.parse(zf.read("python/hst_office/banner_verify.py"))
    values = [n.value for n in source.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "PUBLIC_KEY" for t in n.targets)]
    if len(values) != 1:
        raise ValueError("missing or ambiguous banner key")
    value = values[0]
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name) and value.func.value.id == "bytes"
            and value.func.attr == "fromhex" and len(value.args) == 1 and not value.keywords):
        return bytes.fromhex(ast.literal_eval(value.args[0]))
    key = ast.literal_eval(value)
    if not isinstance(key, bytes):
        raise ValueError("banner key must be bytes")
    return key
