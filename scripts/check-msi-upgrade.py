#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Windows MSI upgrade rules. No argument: the patch series (Quality CI); --msi FILE: a built MSI
(msiinfo, or msilib on Windows Python <= 3.12). The UpgradeCode is HST's permanent code and the only one with
NEWPRODUCTS; a row on another code only removes, stays below 3.0 (LibreOffice for Windows starts at 3.3) and
covers the 1.0.0.1 betas installed under LibreOffice's code (only three version fields count); no component
keeps a beta 1-4 GUID. Installing over those betas: a detect-only row on the same range sets HSTLEGACYPRODUCTS, and
then two property actions between FindRelatedProducts and CostInitialize (execute and UI sequence) set
REINSTALLMODE=amus (the betas' files carry a higher version, 26.8.1.1, and would otherwise be skipped) and VC_REDIST=0
(the system C++ runtime is never costed, so the forced reinstall cannot replace it). Nothing else forces a reinstall."""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/libreoffice/hst-msi-upgradecode.patch"
SEED_PATCH = ROOT / "patches/libreoffice/hst-msi-component-guids.patch"
LEGACY_PATCH = ROOT / "patches/libreoffice/hst-msi-replace-old-betas.patch"
LEGACY_GUID_SEED = "1.0"  # beta 1-4: GUID = MD5(component name + "_1.0")
HST_UPGRADE_CODE = "{A1751BCB-2603-4428-A5DE-419B438ECFBC}"  # permanent, see docs/BUILD_MATRIX.md
LIBREOFFICE_UPGRADE_CODE = "{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}"  # upstream msi_templates/codes.txt
LEGACY_BETA_VERSION = "1.0.0.1"  # ProductVersion of the beta 1-4 MSIs
ONLY_DETECT, MIN_INCLUSIVE, MAX_INCLUSIVE = 2, 256, 512
LEGACY_DETECTED = "HSTLEGACYPRODUCTS"  # set by the detect-only row on the betas' range
LEGACY_FORCED = {"REINSTALLMODE": "amus", "VC_REDIST": "0"}  # what the property actions set when it is set
SEQUENCES = ("InstallExecuteSequence", "InstallUISequence")
# upstream msi_templates InstallE.idt / InstallU.idt: (FindRelatedProducts, CostInitialize); patch mode only
TEMPLATE_SEQUENCE = {"InstallExecuteSequence": (100, 350), "InstallUISequence": (150, 400)}
SET_PROPERTY = 51  # custom action type: set a property from a formatted text
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
        legacy_detect = detects and row["ActionProperty"] == LEGACY_DETECTED
        if (detects or row["ActionProperty"] == "NEWPRODUCTS") and row["UpgradeCode"] != HST_UPGRADE_CODE and not legacy_detect:
            errors.append(f"{where}: newer-version detection on a code that is not HST Office's own")
        if row["UpgradeCode"] == HST_UPGRADE_CODE:
            if row["ActionProperty"] == LEGACY_DETECTED:
                errors.append(f"{where}: {LEGACY_DETECTED} must detect the betas under LibreOffice's code only")
            continue
        if not legacy_detect and (detects or row["ActionProperty"] != "OLDPRODUCTS"):
            errors.append(f"{where}: a row on another product's code must only remove (OLDPRODUCTS) or detect the old betas ({LEGACY_DETECTED})")
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
    if not any(r["UpgradeCode"] == LIBREOFFICE_UPGRADE_CODE and r["ActionProperty"] == LEGACY_DETECTED
               and r["Attributes"] & ONLY_DETECT and matches(r, LEGACY_BETA_VERSION) for r in rows):
        errors.append(f"no detect-only row sets {LEGACY_DETECTED} for the betas under LibreOffice's code: installing over them drops files")
    if "a" in properties.get("REINSTALLMODE", "").lower():
        errors.append(f"REINSTALLMODE {properties['REINSTALLMODE']} forces every install to overwrite files, the system C++ runtime included")
    return errors


def forced_reinstall_errors(actions, sequences):
    """Errors for the actions that force the old betas' files in. actions: {name: (type, source, target)};
    sequences: {table: [(action, condition, number)]}. In both sequences, each LEGACY_FORCED property is set by a
    type-51 action conditioned on LEGACY_DETECTED between FindRelatedProducts and CostInitialize, and no other
    sequenced action sets REINSTALLMODE or VC_REDIST."""
    errors = []
    for table in SEQUENCES:
        rows = sequences.get(table, [])
        number = {action: seq for action, _, seq in rows}
        find, cost = number.get("FindRelatedProducts"), number.get("CostInitialize")
        if find is None or cost is None:
            errors.append(f"{table}: FindRelatedProducts or CostInitialize is missing")
            continue
        for prop, value in LEGACY_FORCED.items():
            setters = [(a, c, n) for a, c, n in rows if a in actions and actions[a][0] & 0x3F == SET_PROPERTY and actions[a][1] == prop]
            good = [a for a, c, n in setters if actions[a][2] == value and c.strip() == LEGACY_DETECTED and find < n < cost]
            if len(setters) != 1 or not good:
                found = ", ".join(f"{a}={actions[a][2]!r} if {c or 'always'} at {n}" for a, c, n in setters) or "none"
                errors.append(f"{table}: {prop} must be set to {value} only when {LEGACY_DETECTED} is set, between "
                              f"FindRelatedProducts ({find}) and CostInitialize ({cost}); found: {found}")
    return errors


def legacy_guid(name):  # the GUID beta 1-4 computed (upstream msiglobal.pm calculate_guid)
    d = hashlib.md5(f"{name}_{LEGACY_GUID_SEED}".encode()).hexdigest().upper()
    return "{%s-%s-%s-%s-%s}" % (d[:8], d[8:12], d[12:16], d[16:20], d[20:])


def component_errors(components):
    shared = sorted(name for name, guid in components if guid.upper() == legacy_guid(name))
    return [f"{len(shared)} components keep their beta 1-4 GUID (e.g. {shared[0]}): upgrading would drop their files"] if shared else []


def seed_errors(patch_text):  # beta 1-4 key files are numbered 26.8.1.1: shared GUIDs would be skipped, then removed
    seeds = re.findall(r"^\+\s+COMPONENTGUIDSEED (\S+)$", patch_text, re.M)
    return [] if len(seeds) == 1 and seeds[0] != LEGACY_GUID_SEED else ["the patch series must set one COMPONENTGUIDSEED other than 1.0"]


def parse_idt(text):
    """Rows of an exported table (msiinfo export / .idt): names, types, key line, then data."""
    lines = text.replace("\r\n", "\n").split("\n")
    names = lines[0].split("\t")
    return [dict(zip(names, line.split("\t") + [""] * len(names))) for line in lines[3:] if line]


def upgrade_rows(raw):
    bad = [r for r in raw if not re.fullmatch(r"\d*", r.get("Attributes") or "")]
    if bad:
        raise ValueError(f"Upgrade row with a bad Attributes value: {bad[0]}")
    return [{k: r.get(k, "") for k in ("UpgradeCode", "VersionMin", "VersionMax", "ActionProperty")}
            | {"Attributes": int(r.get("Attributes") or 0)} for r in raw]


def read_msi(path):
    """Upgrade rows, Property dict, and the errors of the component GUIDs and of the forced-reinstall actions."""
    columns = {"Upgrade": ("UpgradeCode", "VersionMin", "VersionMax", "Language", "Attributes", "Remove", "ActionProperty"),
               "Property": ("Property", "Value"), "Component": ("Component", "ComponentId"),
               "CustomAction": ("Action", "Type", "Source", "Target")} | {t: ("Action", "Condition", "Sequence") for t in SEQUENCES}
    if shutil.which("msiinfo"):
        def export(table):
            done = subprocess.run(["msiinfo", "export", str(path), table], capture_output=True, text=True, check=False)
            if done.returncode != 0:
                raise RuntimeError(f"msiinfo export {table} failed: {done.stderr.strip()}")
            return parse_idt(done.stdout)
    else:
        try:
            import msilib  # Windows Python <= 3.12 only
        except ImportError as exc:
            raise RuntimeError("neither msiinfo (msitools) nor msilib is available") from exc
        db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)

        def export(table):
            names = columns[table]
            view, out = db.OpenView("SELECT " + ", ".join(f"`{n}`" for n in names) + f" FROM `{table}`"), []
            view.Execute(None)
            while (rec := view.Fetch()) is not None:
                out.append(dict(zip(names, (rec.GetString(i + 1) for i in range(len(names))))))
            view.Close()
            return out
    tables = {table: export(table) for table in columns}
    components = [(r["Component"], r.get("ComponentId", "")) for r in tables["Component"]]
    actions = {r["Action"]: (int(r.get("Type") or 0), r.get("Source", ""), r.get("Target", "")) for r in tables["CustomAction"]}
    sequences = {t: [(r["Action"], r.get("Condition", ""), int(r.get("Sequence") or 0)) for r in tables[t]
                     if re.fullmatch(r"-?\d*", r.get("Sequence") or "")] for t in SEQUENCES}
    extra = component_errors(components) + forced_reinstall_errors(actions, sequences)
    return upgrade_rows(tables["Upgrade"]), {r["Property"]: r["Value"] for r in tables["Property"]}, extra


def added_lines(patch_text):
    """Lines a patch adds, per target file (the b/ path of each diff)."""
    out, current = {}, None
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            current = re.sub(r"^b/", "", line[4:].split("\t")[0].strip())
            out.setdefault(current, [])
        elif line.startswith("+") and current is not None:
            out[current].append(line[1:])
    return out


def from_legacy_patch(patch_text):
    """The detect-only Upgrade row, SecureCustomProperties and the forced-reinstall actions the patch adds."""
    added = added_lines(patch_text)
    files = {Path(name).name: lines for name, lines in added.items()}
    upgrade = files.get("upgrade.pm", [])
    if not any('"258"' in line and f'"{LEGACY_DETECTED}"' in line and "$legacycode" in line for line in upgrade):
        raise ValueError(f"the legacy patch no longer writes the detect row as (LEGACYUPGRADECODE, min, max, 258, {LEGACY_DETECTED})")
    secure = [line.split("\t", 1)[1] for line in files.get("Property.idt", []) if line.startswith("SecureCustomProperties\t")]
    if len(secure) != 1:
        raise ValueError("the legacy patch must add one SecureCustomProperties line to Property.idt")
    actions = {}
    for line in files.get("CustomAc.idt", []):
        f = line.split("\t")
        if len(f) >= 4 and f[1].isdigit():
            actions[f[0]] = (int(f[1]), f[2], f[3])
    sequences = {}
    for table, name in (("InstallExecuteSequence", "InstallE.idt"), ("InstallUISequence", "InstallU.idt")):
        find, cost = TEMPLATE_SEQUENCE[table]
        rows = [("FindRelatedProducts", "", find), ("CostInitialize", "", cost)]
        for line in files.get(name, []):
            f = line.split("\t")
            if len(f) == 3 and re.fullmatch(r"\d+", f[2]):
                rows.append((f[0], f[1], int(f[2])))
        sequences[table] = rows
    return {"SecureCustomProperties": secure[0]}, actions, sequences


def from_patch(patch_text, msi_version, legacy_detect=False):
    """The Upgrade rows and properties the patched installer generates (rows as in upgrade.pm); legacy_detect: the
    legacy patch adds the detect-only row on the same legacy code and range."""
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
        legacy = {"UpgradeCode": variables["LEGACYUPGRADECODE"], "VersionMin": variables.get("LEGACYUPGRADEVERSIONMIN", ""),
                  "VersionMax": variables.get("LEGACYUPGRADEVERSIONMAX", "")}
        rows.append(legacy | {"Attributes": 257, "ActionProperty": "OLDPRODUCTS"})
        if legacy_detect:
            rows.append(legacy | {"Attributes": 258, "ActionProperty": LEGACY_DETECTED})
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
            rows, properties, extra = read_msi(args.msi)
        else:
            rows, properties = from_patch(PATCH.read_text(encoding="utf-8"), repo_msi_version(), legacy_detect=True)
            secure, actions, sequences = from_legacy_patch(LEGACY_PATCH.read_text(encoding="utf-8"))
            properties |= secure
            extra = seed_errors(SEED_PATCH.read_text(encoding="utf-8")) + forced_reinstall_errors(actions, sequences)
            series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
            extra += [f"{p.name} is not in the patch series" for p in (PATCH, SEED_PATCH, LEGACY_PATCH) if p.name not in series]
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for row in rows:
        print("row:", row["UpgradeCode"], row["VersionMin"] or "-", row["VersionMax"] or "-", row["Attributes"], row["ActionProperty"])
    errors = validate(rows, properties) + extra
    for error in errors:
        print("FAIL:", error)
    print(f"MSI upgrade rules: {len(rows)} Upgrade rows, {len(errors)} failures ({args.msi or PATCH.name}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
