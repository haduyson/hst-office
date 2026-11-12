#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the Windows MSI carries no legacy CLI-UNO (.NET Framework) bridge and puts nothing in the GAC.

    check-msi-no-cli.py [--msi FILE]

HST Office 1.0.0 and 1.0.1 installed cli_ure, cli_basetypes, cli_uretypes, cli_cppuhelper, cli_oootypes and their
publisher policy assemblies (policy.1.0.cli_*.dll, cli_*.config) into the .NET Global Assembly Cache; that step failed
on some machines (error 1304, Smart App Control). Basic, VBA and the OLE automation bridge do not use them.

No argument (Quality CI): build-config/windows-x86_64.conf keeps --disable-cli and --without-dotnet, the patch series
has hst-windows-no-cli-uno.patch gating the scp2 assembly items on ENABLE_CLI, and no patch adds an ASSEMBLY item to
scp2. --msi FILE (msiinfo, or msilib on Windows Python <= 3.12): no cli_* file in the File table, no MsiAssembly or
MsiAssemblyName row, and RemoveExistingProducts before InstallInitialize in InstallExecuteSequence, so an upgrade
uninstalls the old product (its GAC assemblies included) before installing this one."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from msi_forced_reinstall import read_tables  # noqa: E402

CONF = ROOT / "build-config/windows-x86_64.conf"
SERIES = ROOT / "patches/libreoffice/series"
PATCH = "hst-windows-no-cli-uno.patch"
# cli_ure.dll, cli_uno.dll, cli_oootypes.config, policy.1.0.cli_cppuhelper.dll; not Python's cli-32.exe launchers
CLI_FILE = re.compile(r"(policy\.\d+\.\d+\.)?cli_\w+\.(dll|config)", re.I)
ASSEMBLY_TABLES = ("MsiAssembly", "MsiAssemblyName")
GATE = "#if defined _MSC_VER && ! defined _ARM64_ && defined ENABLE_CLI"
GATED = {"scp2/source/ooo/ure.scp": GATE, "scp2/source/ooo/file_library_ooo.scp": GATE,
         "scp2/InstallModule_ure.mk": "\tENABLE_CLI \\", "scp2/InstallModule_ooo.mk": "\tENABLE_CLI \\"}
COLUMNS = {"File": ("File", "Component_", "FileName"), "MsiAssembly": ("Component_", "Feature_"),
           "MsiAssemblyName": ("Component_", "Name", "Value"), "InstallExecuteSequence": ("Action", "Condition", "Sequence")}


def long_name(file_name):
    """The long name of a File table FileName ("SHORT~1.DLL|long name.dll" or a name that is already short)."""
    return file_name.split("|")[-1]


def added_by_file(patch_text):
    """{path: [added lines]} of a unified diff."""
    added, current = {}, None
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].split("\t")[0]
            added.setdefault(current, [])
        elif current and line.startswith("+") and not line.startswith("+++"):
            added[current].append(line[1:])
    return added


def source_errors(conf_text, series, patches):
    """Errors of the configure options (text), the series (patch names) and the patches ({name: text})."""
    errors = []
    options = {line.strip() for line in conf_text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    for wanted in ("--disable-cli", "--without-dotnet"):
        if wanted not in options:
            errors.append(f"{CONF.name} lacks {wanted}: the .NET bridge would be built and packaged")
    for unwanted in ("--enable-cli", "--with-dotnet"):
        if any(o == unwanted or o.startswith(unwanted + "=") for o in options):
            errors.append(f"{CONF.name} has {unwanted}")
    if PATCH not in series:
        errors.append(f"{PATCH} is not in the patch series: scp2 still lists the CLI assemblies")
    elif PATCH not in patches:
        errors.append(f"{PATCH} is missing")
    else:
        added = added_by_file(patches[PATCH])
        for path, line in GATED.items():
            if line not in added.get(path, []):
                errors.append(f"{PATCH} no longer adds {line.strip()!r} to {path}")
    for name in series:
        for path, lines in added_by_file(patches.get(name, "")).items():
            if path.startswith("scp2/") and any(re.search(r"\bStyles\s*=.*\bASSEMBLY\b", line) for line in lines):
                errors.append(f"{name} adds an ASSEMBLY (Global Assembly Cache) item to {path}")
    return errors


def msi_errors(tables):
    """Errors of the tables read from a built MSI ({table: [row dict]}; a table the MSI lacks is absent)."""
    errors = [f"File {row['File']} ({long_name(row['FileName'])}) is a CLI-UNO bridge file"
              for row in tables.get("File", []) if CLI_FILE.fullmatch(long_name(row.get("FileName", "")))]
    if not tables.get("File"):
        errors.append("the MSI has no File rows: not an HST Office installer")
    for table in ASSEMBLY_TABLES:
        rows = tables.get(table, [])
        if rows:
            errors.append(f"{table} has {len(rows)} rows (e.g. {rows[0]['Component_']}): the MSI installs into the GAC")
    sequence = {row["Action"]: row.get("Sequence", "") for row in tables.get("InstallExecuteSequence", [])}
    remove, initialize = sequence.get("RemoveExistingProducts", ""), sequence.get("InstallInitialize", "")
    if not (remove.isdigit() and initialize.isdigit()):
        errors.append("InstallExecuteSequence lacks RemoveExistingProducts or InstallInitialize")
    elif int(remove) >= int(initialize):
        errors.append(f"RemoveExistingProducts ({remove}) runs after InstallInitialize ({initialize}): "
                      "an upgrade would not remove the old product before installing this one")
    return errors


def table_names(path):
    """The tables an MSI file has (msiinfo, or msilib on Windows Python <= 3.12)."""
    if shutil.which("msiinfo"):
        done = subprocess.run(["msiinfo", "tables", str(path)], capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"msiinfo tables failed: {done.stderr.strip()}")
        return set(done.stdout.split())
    try:
        import msilib  # Windows Python <= 3.12 only
    except ImportError as exc:
        raise RuntimeError("neither msiinfo (msitools) nor msilib is available") from exc
    db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)
    view, names = db.OpenView("SELECT `Name` FROM `_Tables`"), set()
    view.Execute(None)
    while (rec := view.Fetch()) is not None:
        names.add(rec.GetString(1))
    view.Close()
    return names


def read_msi(path):
    if not path.is_file():
        raise RuntimeError(f"{path} is not a file")
    present = table_names(path)
    return read_tables(path, {t: c for t, c in COLUMNS.items() if t in present})


def read_sources():
    series = [n for n in SERIES.read_text(encoding="utf-8").split() if not n.startswith("#")]
    patches = {n: (SERIES.parent / n).read_text(encoding="latin-1") for n in series if (SERIES.parent / n).is_file()}
    return CONF.read_text(encoding="utf-8"), series, patches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--msi", type=Path, help="built MSI to read instead of the configure options and patch series")
    args = parser.parse_args(argv)
    try:
        errors = msi_errors(read_msi(args.msi)) if args.msi else source_errors(*read_sources())
    except (OSError, RuntimeError, KeyError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for error in errors:
        print("FAIL:", error)
    print(f"No CLI-UNO bridge / GAC: {len(errors)} failures ({args.msi or 'configure options and patch series'}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
