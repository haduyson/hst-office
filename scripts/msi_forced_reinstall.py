# SPDX-License-Identifier: AGPL-3.0-only
"""MSI table reading and the forced reinstall over the 1.0.0 betas 1-4 (hst-msi-replace-old-betas.patch), for
check-msi-upgrade.py.

Betas 1-4 stamped HST's files 26.8.1.1, above the real 1.0.0.x versions, so costing would skip them. A detect-only
Upgrade row sets HSTLEGACYPRODUCTS; then, only when it is set and before costing, property actions set
REINSTALLMODE=amus (files go in whatever the version on disk) and VC_REDIST=0 (the C++ runtime merge-module
components are not costed, so System32's runtime is never replaced)."""
import re
import shutil
import subprocess
from pathlib import Path

LEGACY_DETECTED = "HSTLEGACYPRODUCTS"  # set by the detect-only row on the betas' range
LEGACY_FORCED = {"REINSTALLMODE": "amus", "VC_REDIST": "0"}  # what the property actions set when it is set
SEQUENCES = ("InstallExecuteSequence", "InstallUISequence")
# upstream msi_templates InstallE.idt / InstallU.idt: (FindRelatedProducts, CostInitialize); patch mode only
TEMPLATE_SEQUENCE = {"InstallExecuteSequence": (100, 350), "InstallUISequence": (150, 400)}
SET_PROPERTY = 51  # custom action type: set a property from a formatted text
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


def parse_idt(text):
    """Rows of an exported table (msiinfo export / .idt): names, types, key line, then data."""
    lines = text.replace("\r\n", "\n").split("\n")
    names = lines[0].split("\t")
    return [dict(zip(names, line.split("\t") + [""] * len(names))) for line in lines[3:] if line]


def read_tables(path, columns):
    """{table: [row dict]} of an MSI file for the tables in columns ({table: column names}): msiinfo (msitools),
    or msilib on Windows Python <= 3.12."""
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
    return {table: export(table) for table in columns}
