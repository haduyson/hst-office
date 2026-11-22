#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Check the Windows MSI's registration of the HST PDF preview handler and thumbnail provider.

    check-msi-pdf-preview.py --msi FILE

hstpdfpreview.dll (Explorer preview pane and thumbnails of PDF files, rendered with the office's own
pdfiumlo.dll) must be installed next to the other Explorer extensions and registered without taking
anything from another PDF program:
- the CLSIDs (prevhost.exe AppID for the preview handler), PreviewHandlers and Approved entries;
- ShellEx of HST Office's own ProgID HSTOffice.Pdf (used only while the user's PDF app is HST Office);
- SystemFileAssociations\\.pdf\\ShellEx, the shell's lowest-priority slot, each value in its own
  component whose condition installs it only when AppSearch found the slot empty or already ours;
- nothing under .pdf\\ShellEx or any other ProgID.
Needs msiinfo (msitools), or msilib on Windows Python <= 3.12."""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from msi_forced_reinstall import read_tables  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_msi_no_cli", ROOT / "scripts/check-msi-no-cli.py")
_no_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_no_cli)

PREVIEW_CLSID = "{6058E664-567B-4207-82EE-F250B8F88276}"
THUMBNAIL_CLSID = "{61440647-9253-4376-A0B3-66622FA3B055}"
PREVIEW_IID = "{8895b1c6-b41f-4c1c-a562-0d564250836f}"
THUMBNAIL_IID = "{e357fccd-a995-4576-b01f-234630154e96}"
PREVHOST_APPID = "{6d2b5079-2f0b-48dd-ab7f-97cec514d30b}"
DLL = "[INSTALLLOCATION]program\\shlxthdl\\hstpdfpreview.dll"
HKCR, HKMU = "0", "-1"
SFA = "SystemFileAssociations\\.pdf\\ShellEx\\"
# (slot property, CLSID property, CLSID, RegLocator signature, shell extension IID)
SLOTS = (("HSTPDFPREVIEWSLOT", "HSTPDFPREVIEWCLSID", PREVIEW_CLSID, "HstPdfPreviewSlot", PREVIEW_IID),
         ("HSTPDFTHUMBNAILSLOT", "HSTPDFTHUMBNAILCLSID", THUMBNAIL_CLSID, "HstPdfThumbnailSlot", THUMBNAIL_IID))
COLUMNS = {"File": ("File", "Component_", "FileName"),
           "Component": ("Component", "Directory_", "Condition"),
           "Registry": ("Registry", "Root", "Key", "Name", "Value", "Component_"),
           "AppSearch": ("Property", "Signature_"),
           "RegLocator": ("Signature_", "Root", "Key", "Name", "Type"),
           "Property": ("Property", "Value")}


def required_rows():
    """(Root, Key, Name, Value) rows every installer must have, outside the conditional slots."""
    rows = []
    for clsid, label in ((PREVIEW_CLSID, "Preview Handler"), (THUMBNAIL_CLSID, "Thumbnail Provider")):
        rows += [(HKCR, f"CLSID\\{clsid}\\InprocServer32", "", DLL),
                 (HKCR, f"CLSID\\{clsid}\\InprocServer32", "ThreadingModel", "Apartment"),
                 (HKMU, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Shell Extensions\\Approved", clsid,
                  f"HST Office PDF {label}")]
    rows += [(HKCR, f"CLSID\\{PREVIEW_CLSID}", "AppID", PREVHOST_APPID),
             (HKMU, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PreviewHandlers", PREVIEW_CLSID,
              "HST Office PDF Preview Handler"),
             (HKCR, f"HSTOffice.Pdf\\ShellEx\\{PREVIEW_IID}", "", PREVIEW_CLSID),
             (HKCR, f"HSTOffice.Pdf\\ShellEx\\{THUMBNAIL_IID}", "", THUMBNAIL_CLSID)]
    return rows


def msi_errors(tables):
    """Errors of the tables read from a built MSI ({table: [row dict]})."""
    errors = []
    files = {_no_cli.long_name(r["FileName"]).lower(): r["Component_"] for r in tables.get("File", [])}
    directory = {r["Component"]: r["Directory_"] for r in tables.get("Component", [])}
    condition = {r["Component"]: r.get("Condition", "") for r in tables.get("Component", [])}
    if "hstpdfpreview.dll" not in files:
        errors.append("hstpdfpreview.dll is not in the File table")
    elif "shlxthdl.dll" in files and directory.get(files["hstpdfpreview.dll"]) != directory.get(files["shlxthdl.dll"]):
        errors.append("hstpdfpreview.dll is not installed in program\\shlxthdl next to shlxthdl.dll "
                      "(it loads ..\\pdfiumlo.dll from there)")

    registry = tables.get("Registry", [])
    by_value = {(r["Root"], r["Key"], r["Name"], r["Value"]): r for r in registry}
    for row in required_rows():
        found = by_value.get(row)
        if not found:
            errors.append(f"missing registry value {row}")
        elif "SLOT" in condition.get(found["Component_"], ""):
            errors.append(f"{row[1]} sits in a component with a slot condition: it would be skipped too")

    properties = {r["Property"]: r["Value"] for r in tables.get("Property", [])}
    searches = {r["Property"]: r["Signature_"] for r in tables.get("AppSearch", [])}
    locators = {r["Signature_"]: r for r in tables.get("RegLocator", [])}
    for slot, clsid_property, clsid, signature, iid in SLOTS:
        if properties.get(clsid_property) != clsid:
            errors.append(f"Property {clsid_property} is {properties.get(clsid_property)!r}, not {clsid}")
        if searches.get(slot) != signature:
            errors.append(f"AppSearch does not set {slot} from {signature}")
        locator = locators.get(signature)
        expected = ("2", f"SOFTWARE\\Classes\\{SFA}{iid}", "", "18")  # HKLM, default value, raw, 64-bit view
        if not locator or (locator["Root"], locator["Key"], locator["Name"], locator["Type"]) != expected:
            errors.append(f"RegLocator {signature} is {locator and tuple(locator.values())}, expected {expected}")
        rows = [r for r in registry if r["Root"] == HKCR and r["Key"] == SFA + iid]
        if len(rows) != 1 or rows[0]["Name"] != "" or rows[0]["Value"] != clsid:
            errors.append(f"expected one {SFA}{iid} = {clsid} row, found {[(r['Name'], r['Value']) for r in rows]}")
            continue
        component = rows[0]["Component_"]
        want = f"NOT {slot} OR {slot}={clsid_property}"
        if want not in condition.get(component, ""):
            errors.append(f"component {component} of {SFA}{iid} has condition {condition.get(component)!r}, "
                          f"lacks {want!r}: another program's handler could be overwritten")
        others = [r["Key"] for r in registry if r["Component_"] == component and r is not rows[0]]
        if others:
            errors.append(f"component {component} gates more than the {SFA}{iid} slot: {others[:3]}")

    ours = {PREVIEW_CLSID.lower(), THUMBNAIL_CLSID.lower()}
    for r in registry:
        if r["Value"].lower() in ours and "\\shellex\\" in r["Key"].lower():
            if not (r["Key"].startswith("HSTOffice.Pdf\\ShellEx\\") or r["Key"].startswith(SFA)):
                errors.append(f"{r['Key']} points at an HST PDF handler: only HSTOffice.Pdf and "
                              "SystemFileAssociations may (the .pdf key belongs to the user's PDF program)")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--msi", type=Path, required=True, help="built MSI")
    args = parser.parse_args(argv)
    try:
        if not args.msi.is_file():
            raise RuntimeError(f"{args.msi} is not a file")
        present = _no_cli.table_names(args.msi)
        errors = msi_errors(read_tables(args.msi, {t: c for t, c in COLUMNS.items() if t in present}))
    except (OSError, RuntimeError, KeyError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for error in errors:
        print("FAIL:", error)
    print(f"PDF preview registration: {len(errors)} failures ({args.msi}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
