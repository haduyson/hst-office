#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Windows MSI upgrade rules: HST Office's own UpgradeCode, never LibreOffice's.

  check-msi-upgrade.py               check the Upgrade rows the patch series makes (quality CI, no MSI)
  check-msi-upgrade.py --msi FILE    check the Upgrade and Property tables of a built MSI
                                     (msiinfo from msitools, or msilib with Windows Python <= 3.12)
Rules: the UpgradeCode is HST's permanent code; downgrade detection (NEWPRODUCTS) uses only it;
a row on another code only removes, is bounded on both sides below 3.0 (LibreOffice for Windows
starts at 3.3) and covers the 1.0.0.1 betas that were installed under LibreOffice's code.
Windows Installer compares only the first three version fields."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/libreoffice/hst-msi-upgradecode.patch"
HST_UPGRADE_CODE = "{A1751BCB-2603-4428-A5DE-419B438ECFBC}"  # permanent, see docs/BUILD_MATRIX.md
LIBREOFFICE_UPGRADE_CODE = "{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}"  # upstream msi_templates/codes.txt
LEGACY_BETA_VERSION = "1.0.0.1"  # ProductVersion of the beta 1-4 MSIs
ONLY_DETECT, MIN_INCLUSIVE, MAX_INCLUSIVE = 2, 256, 512
GUID = re.compile(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")
VERSION = re.compile(r"\d+\.\d+\.\d+(\.\d+)?")


def three(version):
    """The part of a version Windows Installer compares: the first three fields."""
    return tuple(int(x) for x in version.split(".")[:3])


def matches(row, version):
    """Whether an Upgrade row's version range contains the version (a malformed range contains none)."""
    if not all(VERSION.fullmatch(v) for v in (version, row["VersionMin"], row["VersionMax"]) if v):
        return False
    v, attrs = three(version), row["Attributes"]
    if row["VersionMin"]:
        low = three(row["VersionMin"])
        if v < low or (v == low and not attrs & MIN_INCLUSIVE):
            return False
    if row["VersionMax"]:
        high = three(row["VersionMax"])
        if v > high or (v == high and not attrs & MAX_INCLUSIVE):
            return False
    return True


def validate(rows, properties):
    """Return a list of errors for the Upgrade rows and the Property table (dict)."""
    errors = []
    code = properties.get("UpgradeCode", "")
    if code != HST_UPGRADE_CODE:
        errors.append(f"UpgradeCode {code or '(missing)'} is not HST Office's permanent code {HST_UPGRADE_CODE}")
    if code == LIBREOFFICE_UPGRADE_CODE:
        errors.append("UpgradeCode is LibreOffice's: every installed LibreOffice blocks or replaces HST Office")
    if "ProductCode" in properties and not GUID.fullmatch(properties["ProductCode"]):
        errors.append(f"ProductCode is not a GUID: {properties['ProductCode']}")
    secure = set(filter(None, properties.get("SecureCustomProperties", "").split(";")))
    for row in rows:
        where = f"Upgrade row {row['UpgradeCode']} {row['VersionMin'] or '-'}..{row['VersionMax'] or '-'} {row['ActionProperty']}"
        bad = [f for f in ("VersionMin", "VersionMax") if row[f] and not VERSION.fullmatch(row[f])]
        if bad:
            errors.append(f"{where}: {' and '.join(bad)} is not a version")
            continue
        if secure and row["ActionProperty"] not in secure:
            errors.append(f"{where}: {row['ActionProperty']} is not in SecureCustomProperties")
        detects = bool(row["Attributes"] & ONLY_DETECT)
        if (detects or row["ActionProperty"] == "NEWPRODUCTS") and row["UpgradeCode"] != HST_UPGRADE_CODE:
            errors.append(f"{where}: newer-version detection on a code that is not HST Office's own")
        if row["UpgradeCode"] == HST_UPGRADE_CODE:
            continue
        if detects or row["ActionProperty"] != "OLDPRODUCTS":
            errors.append(f"{where}: a row on another product's code must only remove (OLDPRODUCTS)")
        if not row["VersionMin"] or not row["VersionMax"]:
            errors.append(f"{where}: a row on another product's code needs both VersionMin and VersionMax")
        elif three(row["VersionMax"]) >= (3, 0, 0) or three(row["VersionMin"]) > three(row["VersionMax"]):
            errors.append(f"{where}: the range must end below 3.0 (LibreOffice for Windows starts at 3.3)")
    if not any(r["UpgradeCode"] == HST_UPGRADE_CODE and r["ActionProperty"] == "OLDPRODUCTS" for r in rows):
        errors.append("no OLDPRODUCTS row on HST Office's code: later releases would not replace this one")
    if not any(r["UpgradeCode"] == HST_UPGRADE_CODE and r["ActionProperty"] == "NEWPRODUCTS" for r in rows):
        errors.append("no NEWPRODUCTS row on HST Office's code: downgrades would not be detected")
    if not any(r["UpgradeCode"] == LIBREOFFICE_UPGRADE_CODE and r["ActionProperty"] == "OLDPRODUCTS"
               and not r["Attributes"] & ONLY_DETECT and matches(r, LEGACY_BETA_VERSION) for r in rows):
        errors.append(f"no row removes the betas installed under LibreOffice's code (ProductVersion {LEGACY_BETA_VERSION})")
    return errors


def parse_idt(text):
    """Rows of an exported table (msiinfo export / .idt): names, types, key line, then data."""
    lines = text.replace("\r\n", "\n").split("\n")
    names = lines[0].split("\t")
    return [dict(zip(names, line.split("\t") + [""] * len(names))) for line in lines[3:] if line]


def upgrade_rows(raw):
    rows = []
    for r in raw:
        try:
            attributes = int(r.get("Attributes") or 0)
        except ValueError:
            raise ValueError(f"Upgrade row with a bad Attributes value: {r}") from None
        rows.append({k: r.get(k, "") for k in ("UpgradeCode", "VersionMin", "VersionMax", "ActionProperty")}
                    | {"Attributes": attributes})
    return rows


def read_msi(path):
    """Upgrade rows and Property dict of an MSI file."""
    if shutil.which("msiinfo"):
        def export(table):
            done = subprocess.run(["msiinfo", "export", str(path), table], capture_output=True, text=True, check=False)
            if done.returncode != 0:
                raise RuntimeError(f"msiinfo export {table} failed: {done.stderr.strip()}")
            return parse_idt(done.stdout)
        upgrade, prop = export("Upgrade"), export("Property")
    else:
        try:
            import msilib  # Windows Python <= 3.12 only
        except ImportError:
            raise RuntimeError("neither msiinfo (msitools) nor msilib is available") from None
        db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)

        def query(sql, count):
            view, out = db.OpenView(sql), []
            view.Execute(None)
            while (rec := view.Fetch()) is not None:
                out.append([rec.GetString(i + 1) for i in range(count)])
            view.Close()
            return out
        names = ("UpgradeCode", "VersionMin", "VersionMax", "Language", "Attributes", "Remove", "ActionProperty")
        upgrade = [dict(zip(names, r)) for r in query("SELECT " + ", ".join(f"`{n}`" for n in names) + " FROM `Upgrade`", 7)]
        prop = [{"Property": k, "Value": v} for k, v in query("SELECT `Property`, `Value` FROM `Property`", 2)]
    return upgrade_rows(upgrade), {r["Property"]: r["Value"] for r in prop}


def from_patch(patch_text, msi_version):
    """The Upgrade rows and properties the patched installer generates (rows as in upgrade.pm)."""
    added = [line[1:] for line in patch_text.splitlines() if line.startswith("+") and not line.startswith("+++")]
    codes = [m.group(1) for line in added if (m := re.fullmatch(r'en-US = "(\{[^"]+\})"', line.strip()))]
    variables = dict(line.split(None, 1) for line in added if re.fullmatch(r"\s+(CODEFILENAME|LEGACY\w+) \S+", line))
    if len(codes) != 1 or variables.get("CODEFILENAME") != "codes_hst.txt":
        raise ValueError("the patch must add codes_hst.txt with one UpgradeCode and set CODEFILENAME codes_hst.txt")
    if not any('"257"' in line and '"OLDPRODUCTS"' in line and "$legacycode" in line for line in added):
        raise ValueError("the patch no longer writes the legacy row as (LEGACYUPGRADECODE, min, max, 257, OLDPRODUCTS)")
    code = codes[0]
    rows = [{"UpgradeCode": code, "VersionMin": "", "VersionMax": msi_version, "Attributes": 513, "ActionProperty": "OLDPRODUCTS"},
            {"UpgradeCode": code, "VersionMin": msi_version, "VersionMax": "", "Attributes": 2, "ActionProperty": "NEWPRODUCTS"}]
    if "LEGACYUPGRADECODE" in variables:
        rows.append({"UpgradeCode": variables["LEGACYUPGRADECODE"], "VersionMin": variables.get("LEGACYUPGRADEVERSIONMIN", ""),
                     "VersionMax": variables.get("LEGACYUPGRADEVERSIONMAX", ""), "Attributes": 257, "ActionProperty": "OLDPRODUCTS"})
    return rows, {"UpgradeCode": code}


def repo_msi_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    build = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/write-hst-version.py"), "--build"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return f"{version}.{build}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--msi", type=Path, help="built MSI to read instead of the patch series")
    args = parser.parse_args(argv)
    try:
        if args.msi:
            rows, properties = read_msi(args.msi)
        else:
            rows, properties = from_patch(PATCH.read_text(encoding="utf-8"), repo_msi_version())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for row in rows:
        print("row:", row["UpgradeCode"], row["VersionMin"] or "-", row["VersionMax"] or "-", row["Attributes"], row["ActionProperty"])
    errors = validate(rows, properties)
    for error in errors:
        print("FAIL:", error)
    print(f"MSI upgrade rules: {len(rows)} Upgrade rows, {len(errors)} failures ({args.msi or PATCH.name}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
