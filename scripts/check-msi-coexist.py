#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check that a built HST Office MSI writes no registry name that LibreOffice also writes.

    check-msi-coexist.py [--msi FILE]

No argument (Quality CI): the registry lines the patch series adds to scp2. --msi FILE reads the Registry table (msiinfo, or msilib on Windows Python <= 3.12) and fails on: App Paths entries, the
vnd.libreoffice.* / vnd.sun.star.* URI schemes, LibreOffice's Explorer extension class IDs, ProgIDs named
LibreOffice.*, soffice.Star* or office.Extension*, keys under Software\\LibreOffice, and The Document Foundation
as publisher. Kept on purpose (see docs/BUILD_MATRIX.md): OLE embedding class IDs and the automation names
com.sun.star.ServiceManager, Writer.Application, Calc.Application and AppID\\soffice.exe."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "patches/libreoffice/series"

# LibreOffice's shell extension, property handler and search filter class ids (upstream shell/inc, ooofilt.hxx)
LIBREOFFICE_CLSIDS = (
    "087B3AE3-E237-4467-B8DB-5A38AB959AC9", "C52AF81D-F7A0-4AAB-8E87-F80A60CCD396",
    "63542C48-9552-494A-84F7-73AA6A7C99C1", "3B092F0C-7696-40E3-A80F-68D74DA84210",
    "AE424E85-F6DF-4910-A6A9-438797986431", "7BC0E710-5703-45BE-A29D-5D46D8B39262",
    "7BC0E713-5703-45BE-A29D-5D46D8B39262",
)
RULES = (
    ("App Paths entry", lambda key, value: re.search(r"\\App Paths\\", key, re.I)),
    ("LibreOffice URI scheme", lambda key, value: re.match(r"(vnd\.libreoffice\.|vnd\.sun\.star\.)", key, re.I)),
    ("LibreOffice ProgID", lambda key, value: any(re.match(r"(LibreOffice\.|soffice\.Star|office\.Extension)", s)
                                                    for s in (key, value))),
    ("LibreOffice Explorer extension class id", lambda key, value: any(g in (key + value).upper() for g in LIBREOFFICE_CLSIDS)),
    ("key under Software\\LibreOffice", lambda key, value: re.match(r"Software\\LibreOffice(\\|$)", key, re.I)),
    ("LibreOffice publisher or link", lambda key, value: re.search(r"Document Foundation|libreoffice\.org", value, re.I)),
)


def violations(rows):
    """[(rule, row)] for Registry rows (dicts with Registry, Key, Name, Value) that use a LibreOffice name."""
    found = []
    for row in rows:
        key, value = row.get("Key", ""), row.get("Value", "")
        for rule, test in RULES:
            if test(key, value):
                found.append((rule, row))
    return found


def read_registry(path):
    """Registry table rows of an MSI file."""
    names = ("Registry", "Root", "Key", "Name", "Value", "Component_")
    if shutil.which("msiinfo"):
        done = subprocess.run(["msiinfo", "export", str(path), "Registry"], capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"msiinfo export Registry failed: {done.stderr.strip()}")
        lines = done.stdout.replace("\r\n", "\n").split("\n")
        header = lines[0].split("\t")
        return [dict(zip(header, line.split("\t") + [""] * len(header))) for line in lines[3:] if line]
    try:
        import msilib  # Windows Python <= 3.12 only
    except ImportError as exc:
        raise RuntimeError("neither msiinfo (msitools) nor msilib is available") from exc
    db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)
    view, rows = db.OpenView("SELECT " + ", ".join(f"`{n}`" for n in names) + " FROM `Registry`"), []
    view.Execute(None)
    while (rec := view.Fetch()) is not None:
        rows.append({n: rec.GetString(i + 1) for i, n in enumerate(names)})
    view.Close()
    return rows


def series_rows():
    """Pseudo rows for every Subkey/Value line the patch series adds to scp2 (the static check)."""
    rows = []
    names = [n for n in SERIES.read_text(encoding="utf-8").split() if not n.startswith("#")]
    for name in names:
        current = None
        for line in (SERIES.parent / name).read_text(encoding="latin-1").splitlines():
            if line.startswith("+++ b/"):
                current = line[6:]
            elif current and current.startswith("scp2/") and line.startswith("+") and not line.startswith("+++"):
                m = re.search(r'\b(Subkey|Value)\s*=\s*"?(.*?)"?;', line)
                if m:
                    field = "Key" if m.group(1) == "Subkey" else "Value"
                    rows.append({"Registry": f"{name}:{current}", "Key": "", "Value": "", "Name": "", field: m.group(2)})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--msi", type=Path, help="built MSI to read instead of the patch series")
    args = parser.parse_args(argv)
    try:
        rows = read_registry(args.msi) if args.msi else series_rows()
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    found = violations(rows)
    for rule, row in found:
        print(f"FAIL: {rule}: {row.get('Key', '')} [{row.get('Name', '')}] = {row.get('Value', '')}")
    print(f"MSI coexistence: {len(rows)} registry rows, {len(found)} failures ({args.msi or 'patch series, added scp2 lines'}).")
    return 1 if found or not rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
