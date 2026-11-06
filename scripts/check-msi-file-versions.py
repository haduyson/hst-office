#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check that upgrading from HST Office beta 1-4 cannot drop program files.

Beta 1-4 stamped HST's executables 26.8.1.1. Windows Installer skips a component whose key file on disk
has a higher version than the File table entry, and RemoveExistingProducts then deletes the file.
  check-msi-file-versions.py                  the patch series sets FILEVERSIONFLOOR above 26.8.1.1
  check-msi-file-versions.py --msi FILE       no executable outside merge modules is listed at or below 26.8.1.1
  check-msi-file-versions.py --msi FILE --old OLD.msi   also no same-named file's version goes down vs OLD
"""
import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/libreoffice/hst-msi-file-version-floor.patch"
LEGACY_MAX = "26.8.1.1"  # highest File version in the beta 1-4 MSIs
PE = (".bin", ".com", ".dll", ".exe", ".pyd")
VERSION = re.compile(r"\d+(\.\d+){0,3}")
COLUMNS = {"File": ("File", "Component_", "FileName", "Version"), "ModuleComponents": ("Component", "ModuleID", "Language")}


def key(version):
    parts = [int(x) for x in version.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def long_name(file_name):
    return file_name.split("|")[-1].lower()


def floor_errors(patch_text):
    floors = re.findall(r"^\+\s+FILEVERSIONFLOOR (\S+)$", patch_text, re.M)
    if len(floors) != 1 or not VERSION.fullmatch(floors[0]) or key(floors[0]) <= key(LEGACY_MAX):
        return [f"the patch series must set one FILEVERSIONFLOOR above {LEGACY_MAX}"]
    return []


def own_files(files, merged):
    return [f for f in files if f["Component_"] not in merged]


def below_floor(files):
    """Executables whose File-table version is not above beta 1-4's highest."""
    return sorted(long_name(f["FileName"]) for f in files if long_name(f["FileName"]).endswith(PE)
                  and VERSION.fullmatch(f["Version"]) and key(f["Version"]) <= key(LEGACY_MAX))


def downgraded(files, old_files):
    """Files whose version is lower than the same file (component and name) in the older MSI."""
    old = {(f["Component_"], long_name(f["FileName"])): f["Version"] for f in old_files}
    out = []
    for f in files:
        before, now = old.get((f["Component_"], long_name(f["FileName"])), ""), f["Version"]
        if VERSION.fullmatch(before) and VERSION.fullmatch(now) and key(now) < key(before):
            out.append(f"{long_name(f['FileName'])} {before} -> {now}")
    return sorted(out)


def read_table(path, table):
    """Rows of a table as dicts (msiinfo from msitools, or msilib on Windows Python <= 3.12)."""
    names = COLUMNS[table]
    if shutil.which("msiinfo"):
        done = subprocess.run(["msiinfo", "export", str(path), table], capture_output=True, text=True, check=False)
        if done.returncode != 0:
            if "ModuleComponents" == table:
                return []  # an MSI without merge modules has no such table
            raise RuntimeError(f"msiinfo export {table} failed: {done.stderr.strip()}")
        lines = done.stdout.replace("\r\n", "\n").split("\n")
        header = lines[0].split("\t")
        return [{n: dict(zip(header, line.split("\t"))).get(n, "") for n in names} for line in lines[3:] if line]
    try:
        import msilib  # Windows Python <= 3.12 only
    except ImportError as exc:
        raise RuntimeError("neither msiinfo (msitools) nor msilib is available") from exc
    db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)
    try:
        view = db.OpenView("SELECT " + ", ".join(f"`{n}`" for n in names) + f" FROM `{table}`")
    except msilib.MSIError:
        if table == "ModuleComponents":
            return []
        raise
    view.Execute(None)
    rows = []
    while (rec := view.Fetch()) is not None:
        rows.append({n: rec.GetString(i + 1) for i, n in enumerate(names)})
    view.Close()
    return rows


def msi_errors(path, old_path=None):
    merged = {r["Component"] for r in read_table(path, "ModuleComponents")}
    files = own_files(read_table(path, "File"), merged)
    errors = []
    low = below_floor(files)
    if low:
        errors.append(f"{len(low)} executables are listed at or below {LEGACY_MAX}; an upgrade from beta 1-4 "
                      f"drops them: " + ", ".join(low))
    if old_path:
        down = downgraded(files, read_table(old_path, "File"))
        if down:
            errors.append(f"{len(down)} files have a lower version than in {Path(old_path).name}: " + "; ".join(down))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--msi", type=Path, help="built MSI")
    parser.add_argument("--old", type=Path, help="older MSI (for example beta.4) to compare file versions with")
    args = parser.parse_args(argv)
    if args.old and not args.msi:
        parser.error("--old needs --msi")
    try:
        errors = msi_errors(args.msi, args.old) if args.msi else floor_errors(PATCH.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for error in errors:
        print("FAIL:", error)
    print(f"MSI file versions: {len(errors)} failures ({args.msi or PATCH.name}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
