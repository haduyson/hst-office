# SPDX-License-Identifier: AGPL-3.0-only
"""Structural check of VBA UserForms in a saved file, against MS-CFB, MS-OVBA and MS-OFORMS (no Office needed).

Usage: python3 tests/runtime/vba_form_structure.py FILE.xlsm|.docm|vbaProject.bin [...]
Exit 1 when a rule fails. Standard library only: the Windows probe runs it too. Checked against an
Excel-made file; it validates structure only and does not prove that Microsoft Office accepts a file.
"""
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from vba_cfb import Cfb, decompress  # noqa: E402,E702

FORM_CLSID = "00000000-0000-0000-0000-000000000000"  # what Excel writes
FRAME_CLSID = "6e182020-f460-11ce-9bcd-00aa00608e01"


def record_size(data, offset, version, name, problems):
    """Checks an MS-OFORMS record header at offset; returns the offset after the record."""
    got, size = struct.unpack_from("<HH", data, offset)
    if got != version:
        problems.append("%s: version 0x%04x, expected 0x%04x" % (name, got, version))
    end = offset + 4 + size
    if end > len(data):
        problems.append("%s: record runs past the stream" % name)
    return end


def parse_site(data, offset, problems):
    start = offset
    end = record_size(data, offset, 0x0000, "site", problems)
    mask = struct.unpack_from("<I", data, offset + 4)[0]
    pos = 8

    aligned = lambda position, width: position + (width - (position % width)) % width  # noqa: E731
    # fields in SitePropMask order: Name, Tag, ID, HelpContextID, BitFlags, ObjectStreamSize, TabIndex, ClsidCacheIndex
    fields = [("name", 4), ("tag", 4), ("id", 4), ("help", 4), ("flags", 4), ("stream", 4), ("tab", 2), ("class", 2),
              ("position", 0), ("group", 2), ("padding", 0), ("tooltip", 4), ("license", 4), ("source", 4), ("rows", 4)]
    values = {}
    for bit, (key, width) in enumerate(fields):
        if mask >> bit & 1 and width:
            pos = aligned(pos, width)
            values[key] = struct.unpack_from("<I" if width == 4 else "<H", data, start + pos)[0]
            pos += width
    name_size = values.get("name", 0)
    pos = aligned(pos, 4)
    name = data[start + pos:start + pos + (name_size & 0x7FFFFFFF)]
    name = name.decode("cp1252" if name_size & 0x80000000 else "utf-16-le", "replace")
    return end, dict(name=name, id=values.get("id"), flags=values.get("flags", 0x33),
                     stream=values.get("stream", 0), cls=values.get("class"))


def check_container(cfb, entry, name, problems, expected_clsid):
    items = cfb.children(entry)
    if entry["clsid"] != expected_clsid:
        problems.append("%s: storage CLSID %s" % (name, entry["clsid"]))
    if "\x01CompObj" not in items:
        problems.append("%s: no \\001CompObj" % name)
    if "f" not in items:
        problems.append("%s: no f stream" % name)
        return []
    data = cfb.read(items["f"])
    offset = record_size(data, 0, 0x0400, name + " f", problems)
    mask = struct.unpack_from("<I", data, 4)[0]
    if not mask >> 27 & 1:
        problems.append("%s: f without DrawBuffer" % name)
    count = struct.unpack_from("<H", data, offset)[0]  # class table: Office lists non-standard controls
    offset += 2
    for _ in range(count):
        offset += 4 + struct.unpack_from("<H", data, offset + 2)[0]
    sites, size = struct.unpack_from("<II", data, offset)
    offset += 8
    if offset + size != len(data):
        problems.append("%s: f site data size %d, %d bytes left" % (name, size, len(data) - offset))
    anchor = offset
    # SiteDepthsAndTypes: depth, then a type, or a count (high bit) and a type, for a run of sites
    seen = 0
    while seen < sites:
        offset += 1
        run = data[offset]
        offset += 1
        if run & 0x80:
            offset += 1
            seen += run & 0x7F
        else:
            seen += 1
    # padded to 4 bytes, counted from the site count field
    offset = anchor - 8 + ((offset - (anchor - 8) + 3) // 4 * 4)
    controls = []
    for _ in range(sites):
        offset, site = parse_site(data, offset, problems)
        controls.append(site)
    streamed = [c for c in controls if c["flags"] & 0x10]
    total = sum(c["stream"] for c in streamed)
    o_data = cfb.read(items["o"]) if "o" in items else b""
    if len(o_data) != total:
        problems.append("%s: o stream %d bytes, sites say %d" % (name, len(o_data), total))
    pos = 0
    for control in streamed:
        if o_data[pos:pos + 2] not in (b"\x00\x02",):
            problems.append("%s.%s: model version %s" % (name, control["name"], o_data[pos:pos + 2].hex()))
        pos += control["stream"]
    for control in controls:
        if control["flags"] & 0x10:
            continue
        sub = "i%02d" % control["id"]
        if sub not in items:
            problems.append("%s: no %s storage for %s" % (name, sub, control["name"]))
        else:
            controls += check_container(cfb, items[sub], name + "/" + control["name"], problems, FRAME_CLSID)
    return controls


def open_project(path):
    """The compound file and the storage entry of the VBA project in a saved file."""
    if path.lower().endswith(".bin") or not zipfile.is_zipfile(path):
        with open(path, "rb") as handle:
            raw = handle.read()
    else:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(next(n for n in archive.namelist() if n.endswith("vbaProject.bin")))
    cfb = Cfb(raw)
    root = cfb.entries[0]
    for storage in ("_VBA_PROJECT_CUR", "Macros"):
        if storage in cfb.children(root):
            root = cfb.children(root)[storage]
    return cfb, root


def module_sources(path):
    """{module stream: decompressed source bytes}, read from MODULEOFFSET in the dir stream."""
    cfb, root = open_project(path)
    vba = cfb.children(cfb.children(root)["VBA"])
    directory = decompress(cfb.read(vba["dir"]))
    sources, pos, stream = {}, 0, None
    while pos + 6 <= len(directory):
        record, size = struct.unpack_from("<HI", directory, pos)
        if record == 0x0009:  # PROJECTVERSION: its Size field holds 4 but 6 bytes follow
            size = 6
        body = directory[pos + 6:pos + 6 + size]
        if record == 0x001A:  # MODULESTREAMNAME
            stream = body.decode("cp1252", "replace")
        elif record == 0x0031 and stream in vba:  # MODULEOFFSET
            sources[stream] = decompress(cfb.read(vba[stream])[struct.unpack("<I", body)[0]:])
        pos += 6 + size
    return sources


def check_file(path):
    """Returns (problems, {form: [control names]})."""
    cfb, root = open_project(path)
    top = cfb.children(root)
    problems = []
    for needed in ("PROJECT", "PROJECTwm", "VBA"):
        if needed not in top:
            problems.append("no %s in the project" % needed)
    project = cfb.read(top["PROJECT"]).decode("cp1252", "replace") if "PROJECT" in top else ""
    forms = re.findall(r"^BaseClass=(.+?)\r?$", project, re.M)
    if forms and "Package={AC9F2F90-E877-11CE-9F68-00AA00574A4F}" not in project:
        problems.append("PROJECT: no MS Forms Package line")
    vba = cfb.children(top["VBA"]) if "VBA" in top else {}
    if "dir" in vba:
        directory = decompress(cfb.read(vba["dir"]))
        if forms and b"{0D452EE1-E08F-101A-852E-02608C4D0BB4}" not in directory:
            problems.append("dir: no MS Forms reference")
    result = {}
    for form in forms:
        if form not in vba:
            problems.append("%s: no module stream" % form)
        if form not in top:
            problems.append("%s: no designer storage" % form)
            continue
        items = cfb.children(top[form])
        if "\x03VBFrame" not in items:
            problems.append("%s: no \\003VBFrame" % form)
        else:
            frame = cfb.read(items["\x03VBFrame"]).decode("cp1258", "replace")
            if not re.search(r"Begin \{C62A69F0-16DC-11CE-9E98-00AA00574A4F\} %s\b" % re.escape(form), frame):
                problems.append("%s: \\003VBFrame without the form Begin line" % form)
        result[form] = [c["name"] for c in check_container(cfb, top[form], form, problems, FORM_CLSID)]
    return problems, result


def main(paths):
    failed = 0
    for path in paths:
        problems, forms = check_file(path)
        print("%s %s: %s" % ("FAIL" if problems else "PASS", path, forms))
        for problem in problems:
            print("  " + problem)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
