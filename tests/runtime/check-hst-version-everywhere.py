#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: what a user can see as the version of HST Office is the HST release, never the engine version.

Usage (the Xvfb display must already run; it is never started or stopped here; soffice runs as the build user):
    python3 tests/runtime/check-hst-version-everywhere.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/hst-version-everywhere] [--display :97] [--port 22197] [--release 1.0.1]

The engine version is read from the program's own registry (ooSetupVersionAboutBox, e.g. 26.8.1.1); "26.8" and
"LibreOffice" must not appear in:
  1. `soffice --version`;
  2. the generator of documents saved by Writer, Sheets and Slides: meta:generator (ODF) and docProps/app.xml
     Application (OOXML) are "HSTOffice/<release>$<os>_<arch>"; AppVersion keeps its compatibility value; read back,
     the ODF document is classified as written by the engine version (import BuildId), as before the rename;
  3. PDF Producer ("HST Office <release> (<arch>)") and Creator ("HST Writer", "HST Sheets", "HST Slides"),
     the HTML generator and the EPS %%Creator;
  4. Help > About: the version label is "<release> (<arch>)", the Misc label reads "Sheets: ..." and "Copy version
     info" has no engine line;
  5. the Vietnamese UI catalogues name the apps Sheets and Slides, not Calc or Impress (legacy format names
     allowed), and carry no engine version.
Exit 1 when a check fails.
"""
import argparse
import gettext
import glob
import json
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_dialog_uitest as uit  # noqa: E402
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
ROWS = []
# Names of legacy clipboard and file formats ("Calc object of OpenOffice.org 1.0", "Impress 6"): kept.
LEGACY_CONTEXTS = ("STR_FORMAT_ID_STARCALC_60", "STR_FORMAT_ID_STARIMPRESS_60", "STR_FORMAT_ID_STRING_TSVC",
                   "STR_IMPRESS_DOCUMENT_FULLTYPE_60")
APP_WORD = re.compile(r"(?<![%\w])(?<!%PRODUCTNAME )(Calc|Impress)\b")


def record(name, ok, detail=""):
    ROWS.append((name, bool(ok)))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:400]), flush=True)


def engine_version(instdir):
    """ooSetupVersionAboutBox of the program, e.g. 26.8.1.1 (the version that must stay hidden)."""
    with open(os.path.join(instdir, "share", "registry", "main.xcd"), encoding="utf-8") as handle:
        match = re.search(r'<prop oor:name="ooSetupVersionAboutBox"><value>([^<]+)</value>', handle.read())
    if not match:
        raise SystemExit("main.xcd: no ooSetupVersionAboutBox")
    return match.group(1)


def engine_pattern(engine):
    """The engine's major.minor (26.8) as a version number, also inside 26.8.1.1."""
    return r"(?<![\d.])" + re.escape(".".join(engine.split(".")[:2])) + r"(?![\d])"


def forbidden(engine):
    return re.compile(engine_pattern(engine) + r"|LibreOffice", re.IGNORECASE)


def clean(name, text, bad):
    record(name + ": no engine version or LibreOffice", text and not bad.search(text), text)


def check_version_option(instdir, release, bad):
    run = subprocess.run(hst_gui._as_user_prefix() + [os.path.join(instdir, "program", "soffice"), "--version"],
                         capture_output=True, text=True, timeout=120, cwd="/")
    out = run.stdout.strip()
    record("soffice --version names the release", f"HST Office {release} " in out + " ", out)
    clean("soffice --version", out, bad)


def props(**values):
    return uit.props(**values)


def store(doc, url, filter_name):
    doc.storeToURL(url, props(FilterName=filter_name))


def xml_member(path, member):
    with zipfile.ZipFile(path) as archive:
        return archive.read(member).decode("utf-8")


def pdf_info(path):
    """Producer and Creator of a PDF from its Info dictionary (UTF-16 hex or literal strings)."""
    data = open(path, "rb").read()
    info = {}
    for key in ("Producer", "Creator"):
        match = re.search(rb"/" + key.encode() + rb"\s*(<FEFF[0-9A-Fa-f]*>|\((?:[^()\\]|\\.)*\))", data)
        if not match:
            info[key] = ""
            continue
        raw = match.group(1)
        info[key] = (bytes.fromhex(raw[1:-1].decode()).decode("utf-16-be").lstrip("﻿") if raw.startswith(b"<")
                     else raw[1:-1].decode("latin-1"))
    return info


def check_documents(harness, out, release, bad, engine):
    generator = re.compile(r"^HSTOffice/" + re.escape(release) + r"\$\w+_\w+$")
    url = lambda name: "file://" + os.path.join(out, name)
    cases = (("swriter", "writer8", "MS Word 2007 XML", "writer_pdf_Export", "HST Writer", "t"),
             ("scalc", "calc8", "Calc MS Excel 2007 XML", "calc_pdf_Export", "HST Sheets", "s"),
             ("simpress", "impress8", "Impress MS PowerPoint 2007 XML", "impress_pdf_Export", "HST Slides", "p"))
    for kind, odf, ooxml, pdf, creator, stem in cases:
        doc = harness.new_document(kind)
        try:
            if kind == "swriter":
                doc.getText().setString("HST")
                store(doc, url("t.html"), "HTML (StarWriter)")
            ext = {"swriter": ("odt", "docx"), "scalc": ("ods", "xlsx"), "simpress": ("odp", "pptx")}[kind]
            store(doc, url(f"{stem}.{ext[0]}"), odf)
            store(doc, url(f"{stem}.{ext[1]}"), ooxml)
            store(doc, url(f"{stem}.pdf"), pdf)
        finally:
            harness.close_document(doc)
        meta = re.search(r"<meta:generator>([^<]*)</meta:generator>",
                         xml_member(os.path.join(out, f"{stem}.{ext[0]}"), "meta.xml"))
        meta = meta.group(1) if meta else ""
        record(f"{ext[0]} meta:generator is HSTOffice/<release>", generator.match(meta), meta)
        clean(f"{ext[0]} meta:generator", meta, bad)
        app = xml_member(os.path.join(out, f"{stem}.{ext[1]}"), "docProps/app.xml")
        application = re.search(r"<Application>([^<]*)</Application>", app)
        application = application.group(1) if application else ""
        record(f"{ext[1]} Application is HSTOffice/<release>", generator.match(application), application)
        clean(f"{ext[1]} Application", application, bad)
        app_version = re.search(r"<AppVersion>([^<]*)</AppVersion>", app)
        # Interop: other office suites parse AppVersion as their own compatibility number (XX.YYYY).
        record(f"{ext[1]} AppVersion keeps the compatibility form",
               app_version and re.fullmatch(r"\d\d\.\d{4}", app_version.group(1)), app_version and app_version.group(1))
        info = pdf_info(os.path.join(out, f"{stem}.pdf"))
        record(f"{stem}.pdf Producer is HST Office <release>",
               re.fullmatch(r"HST Office " + re.escape(release) + r" \(\w+\)", info["Producer"]), info["Producer"])
        record(f"{stem}.pdf Creator is {creator}", info["Creator"] == creator, info["Creator"])
        clean(f"{stem}.pdf Producer", info["Producer"], bad)
    check_reimport(harness, url("t.odt"), release, engine)
    html = open(os.path.join(out, "t.html"), encoding="utf-8", errors="replace").read()
    meta = re.search(r'<meta name="generator" content="([^"]*)"', html)
    meta = meta.group(1) if meta else ""
    record("HTML generator names the release", meta.startswith(f"HST Office {release} ("), meta)
    clean("HTML generator", meta, bad)
    drawing = harness.new_document("sdraw")
    try:
        shape = drawing.createInstance("com.sun.star.drawing.RectangleShape")
        drawing.getDrawPages().getByIndex(0).add(shape)
        size = uno_struct("com.sun.star.awt.Size", Width=4000, Height=2000)
        shape.setSize(size)
        store(drawing, url("d.eps"), "draw_eps_Export")
    finally:
        harness.close_document(drawing)
    eps = open(os.path.join(out, "d.eps"), "rb").read(4096).decode("latin-1")
    creator = re.search(r"^%%Creator: (.*)$", eps, re.M)
    creator = creator.group(1).strip() if creator else ""
    record("EPS %%Creator names the release", creator == f"HST Office {release}", creator)


def check_reimport(harness, url, release, engine):
    """Interop: reading its own document back, HST Office classifies it as written by its engine version (Writer
    exposes the import's BuildId), so version-dependent import rules apply as for the engine's own documents."""
    doc = harness.office.desktop().loadComponentFromURL(url, "_blank", 0, props(Hidden=True))
    try:
        build_id = doc.getPropertyValue("BuildId")
    finally:
        doc.close(True)
    expected = ";26.8" if release.startswith("1.0.") else ";" + ".".join(engine.split(".")[:2])
    record("re-imported HSTOffice document maps to its engine version", build_id == expected,
           f"BuildId {build_id!r}, expected {expected!r}")


def uno_struct(name, **values):
    import uno
    struct = uno.createUnoStruct(name)
    for key, value in values.items():
        setattr(struct, key, value)
    return struct


def check_about(harness, release, bad):
    dialog = harness.open_dialog(".uno:About", "AboutDialog")
    try:
        texts = {wid: uit.state(dialog.getChild(wid)).get("Text", "")
                 for wid in ("lbVersionString", "lbEnvString", "lbUIString", "lbLocaleString", "lbMiscString",
                             "lbCopyright", "lbAbout") if uit.has_child(dialog, wid)}
        record("About version is <release> (<arch>)",
               re.fullmatch(re.escape(release) + r" \(\w+\)", texts.get("lbVersionString", "")),
               texts.get("lbVersionString"))
        misc = texts.get("lbMiscString", "")
        record("About Misc names Sheets, in Vietnamese", misc.startswith("Sheets: ") and "threaded" not in misc, misc)
        for wid, text in texts.items():
            record(f"About {wid}: no engine version, LibreOffice or Calc",
                   not bad.search(text) and not APP_WORD.search(text), text)
        uit.click(dialog, "btnCopyVersion")
        time.sleep(1)
        copied = clipboard_text(harness)
        record("Copy version info: release, no engine line",
               copied.startswith(f"Version: {release} (") and "Engine" not in copied and "Sheets: " in copied
               and not bad.search(copied) and not APP_WORD.search(copied), copied.replace("\n", " | "))
    finally:
        uit.click(dialog, "btnClose")


def clipboard_text(harness):
    contents = harness.office.service("com.sun.star.datatransfer.clipboard.SystemClipboard").getContents()
    for flavor in contents.getTransferDataFlavors():
        if flavor.MimeType.startswith("text/plain"):
            data = contents.getTransferData(flavor)
            return data if isinstance(data, str) else bytes(data.value).decode("utf-16-le", "replace")
    return ""


def check_catalogues(instdir, engine):
    leftovers, versions = [], []
    for path in sorted(glob.glob(os.path.join(instdir, "program", "resource", "vi", "LC_MESSAGES", "*.mo"))):
        with open(path, "rb") as handle:
            catalog = gettext.GNUTranslations(handle)._catalog
        for key, value in catalog.items():
            key = key if isinstance(key, str) else key[0]
            value = value if isinstance(value, str) else value[0]
            if not key or any(ctx in key for ctx in LEGACY_CONTEXTS):
                continue
            if APP_WORD.search(value):
                leftovers.append(f"{os.path.basename(path)}: {value[:90]}")
            if re.search(engine_pattern(engine), value):
                versions.append(f"{os.path.basename(path)}: {value[:90]}")
    record("vi catalogues name Sheets/Slides, not Calc/Impress", not leftovers,
           f"{len(leftovers)}: " + " || ".join(leftovers[:8]))
    record("vi catalogues carry no engine version", not versions, " || ".join(versions[:8]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "hst-version-everywhere"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=22197)
    parser.add_argument("--release", help="expected release id (default: data/hst/release.json)")
    args = parser.parse_args()
    instdir, out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    release = args.release or json.load(open(os.path.join(ROOT, "data", "hst", "release.json"),
                                             encoding="utf-8"))["release"]
    engine = engine_version(instdir)
    bad = forbidden(engine)
    print(f"release {release}, hidden engine version {engine}", flush=True)
    os.makedirs(out, exist_ok=True)
    check_version_option(instdir, release, bad)
    check_catalogues(instdir, engine)
    harness = uit.DialogHarness(instdir, os.path.join(out, "office"), args.port, args.display)
    docs = os.path.join(out, "office", "docs")
    os.makedirs(docs, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, docs], check=True)
    try:
        for group, check in (("documents", lambda: check_documents(harness, docs, release, bad, engine)),
                             ("about", lambda: check_about(harness, release, bad))):
            try:
                check()
            except Exception as error:  # noqa: BLE001 - report and go on with the next group
                record(f"{group}: ran to the end", False, repr(error))
    finally:
        harness.close()
    failed = [name for name, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
