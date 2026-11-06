# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows MSI registers nothing under a name LibreOffice also registers: legacy StarOffice ProgIDs, App Paths,
the vnd.libreoffice.command URI scheme, the Explorer extension class IDs and keys under Software\\LibreOffice
(five appended patches).

Offline (CI): the patches themselves. With HST_LO_SRC set to a patched tree, scp2 and the shell extension sources
are scanned too; scripts/check-msi-coexist.py checks a built MSI and windows-smoke the installed registry."""
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "patches/libreoffice"
LEGACY, APP_PATHS, URI, SHELLEXT, KEYS = (DIR / f"hst-windows-{n}.patch" for n in (
    "own-legacy-progids", "no-app-paths", "no-libreoffice-uri-scheme", "own-shell-extension-clsids", "own-registry-keys"))
# LibreOffice's class id -> HST Office's (shell/inc/shlxthdl.hxx, propertyhdl.hxx, ooofilt.hxx)
CLSIDS = {
    "087B3AE3-E237-4467-B8DB-5A38AB959AC9": "2A30C089-4A9F-4456-9E48-AEB9FF0012A3",  # infotip
    "C52AF81D-F7A0-4AAB-8E87-F80A60CCD396": "0643B6EE-B40D-4AA5-AC91-6849F83692BD",  # column
    "63542C48-9552-494A-84F7-73AA6A7C99C1": "9A9E8777-D20C-40AD-826C-085F05B40FA6",  # property sheet
    "3B092F0C-7696-40E3-A80F-68D74DA84210": "BC84498F-C467-4BD6-9876-D44924DA54D0",  # thumbnail
    "AE424E85-F6DF-4910-A6A9-438797986431": "A5B95EEC-7757-43B4-A663-634CF2E9A67A",  # property handler
    "7BC0E710-5703-45BE-A29D-5D46D8B39262": "A0914CEA-1A1D-4B82-A200-FE2818319A03",  # indexing filter
    "7BC0E713-5703-45BE-A29D-5D46D8B39262": "11AF517D-5B69-4366-92C2-C1C3B7493418",  # persistent handler
}
APP_NAMES = {"soffice", "swriter", "scalc", "simpress", "sdraw", "smath", "sbase", "unopkg"}
INITIALIZER = re.compile(r"//\s*\{([0-9A-Fa-f-]{36})\}\s*\n[^{]*=\s*\{\s*([^;]*?)\}\s*;", re.S)


def hunks(patch):
    """{path: (removed lines, added lines, new side of the hunks)} of a patch."""
    out, current = {}, None
    for line in patch.read_text(encoding="latin-1").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], [], []))
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current[0].append(line[1:])
        elif current is not None and line.startswith("+"):
            current[1].append(line[1:])
            current[2].append(line[1:])
        elif current is not None and line.startswith(" "):
            current[2].append(line[1:])
    return out


def guid_of(initializer):
    """GUID string of a C initializer {0x..., 0x..., 0x..., {8 bytes}}."""
    n = [int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]+)", initializer)]
    return "%08X-%04X-%04X-%02X%02X-%s" % (n[0], n[1], n[2], n[3], n[4], "".join("%02X" % b for b in n[5:11]))


class CoexistRegistry(unittest.TestCase):
    def test_appended_in_order(self):
        series = [n for n in (DIR / "series").read_text(encoding="utf-8").split() if not n.startswith("#")]
        names = [p.name for p in (LEGACY, APP_PATHS, URI, SHELLEXT, KEYS)]
        start = series.index(names[0])
        self.assertEqual(series[start:start + 5], names)
        self.assertLess(series.index("hst-windows-app-user-model-ids.patch"), start)

    def test_legacy_progids_renamed_one_for_one(self):
        patched = hunks(LEGACY)
        self.assertNotIn("embedserv/source/embed/guid.cxx", patched)  # storage type names written into documents
        self.assertIn("shell/source/win32/shlxthandler/util/fileextensions.cxx", patched)
        total = 0
        for path, (removed, added, _new) in patched.items():
            self.assertFalse(any("soffice.Star" in line for line in added), path)
            self.assertEqual([line.replace("soffice.Star", "HSTOffice.Star") for line in removed], added, path)
            total += sum(line.count("soffice.Star") for line in removed)
        self.assertEqual(total, 268)  # every occurrence in the pinned sources

    def test_no_app_paths(self):
        patched = hunks(APP_PATHS)
        names = set()
        for path, (removed, added, _new) in patched.items():
            self.assertTrue(path.startswith("scp2/source/"), path)
            self.assertEqual(added, [], path)
            names |= set(re.findall(r"App Paths\\(\w+)\.exe", "\n".join(removed)))
        self.assertEqual(names, APP_NAMES)

    def test_no_libreoffice_uri_scheme(self):
        patched = hunks(URI)
        removed = "\n".join(line for r, _a, _n in patched.values() for line in r)
        added = "\n".join(line for _r, a, _n in patched.values() for line in a if not line.lstrip().startswith("//"))
        self.assertIn("REGISTER_URI_HANDLER( vnd.libreoffice.command", removed)
        self.assertNotIn("vnd.libreoffice", added)
        self.assertNotIn("vnd.sun.star", added)
        self.assertNotIn("URL Protocol", added)  # HSTOffice.OfficeURI is a ProgID, not a scheme
        self.assertIn('Subkey = "HSTOffice.OfficeURI\\shell\\open\\command";', added)
        for scheme in ("ms-word", "ms-excel", "ms-powerpoint", "ms-visio"):
            self.assertRegex(added, rf"REGISTRY_ENTRY_CAPABILITIES_URL\({scheme}, \w+, \w+, HSTOffice\.OfficeURI\)")

    def test_shell_extension_clsids_are_hst_own(self):
        patched = hunks(SHELLEXT)
        added_all = "\n".join(line for _r, a, _n in patched.values() for line in a)
        for old, new in CLSIDS.items():
            self.assertNotIn(old, added_all.upper())
            self.assertNotIn(old.replace("-", "_"), added_all.upper())
            self.assertIn(new, added_all)
        # every C initializer equals the GUID in its comment and is one of HST's
        for header in ("shell/inc/shlxthdl.hxx", "shell/inc/propertyhdl.hxx", "shell/source/win32/shlxthandler/ooofilt/ooofilt.hxx"):
            text = "\n".join(patched[header][2])
            found = INITIALIZER.findall(text)
            self.assertTrue(found, header)
            for comment, init in found:
                self.assertEqual(guid_of(init), comment.upper(), header)
                self.assertIn(comment.upper(), CLSIDS.values(), header)

    def test_handlers_leave_extension_keys_of_the_other_suite(self):
        patched = hunks(SHELLEXT)
        added = [line for _r, a, _n in patched.values() for line in a]
        self.assertFalse([line for line in added if re.search(r'Subkey = "\.\w+\\shellex\\', line)])
        moved = [line for line in added if re.search(r'Subkey = "HSTOffice\.[\w.]+\\shellex\\\{(00021500|BB2E617C)-', line)]
        self.assertEqual(len(moved), 43)  # 22 infotip + 21 thumbnail slots

    def test_ole_embedding_clsids_unchanged(self):
        for patch in (LEGACY, APP_PATHS, URI, SHELLEXT, KEYS):
            for path, (removed, added, _new) in hunks(patch).items():
                ole = lambda lines: sorted(re.findall(r'CLSID\\\{([0-9A-Fa-f-]{36})\}', "\n".join(lines)))
                old_ole = [g for g in ole(removed) if g.upper() not in CLSIDS]
                self.assertEqual(old_ole, [g for g in ole(added) if g.upper() not in CLSIDS.values()], f"{patch.name} {path}")

    def test_registry_keys_under_hst_vendor(self):
        patched = hunks(KEYS)
        self.assertEqual(set(patched), {"scp2/source/ooo/registryitem_ooo.scp", "scp2/source/ooo/ure.scp"})
        removed = "\n".join(line for r, _a, _n in patched.values() for line in r)
        added = "\n".join(line for _r, a, _n in patched.values() for line in a)
        self.assertEqual(removed.count("Software\\LibreOffice\\"), 8)
        self.assertEqual(added.count("Software\\%MANUFACTURER\\"), 8)
        for word in ("LibreOffice", "libreoffice", "Document Foundation"):
            self.assertNotIn(word, added)
        self.assertNotIn("migrateinstallpath", "\n".join(patched))  # still reads beta 1-4's old Layers key

    @unittest.skipUnless(os.environ.get("HST_LO_SRC"), "HST_LO_SRC (a patched tree) not set")
    def test_patched_tree_shares_nothing(self):
        tree = Path(os.environ["HST_LO_SRC"])
        left = []
        for top in ("scp2", "shell/inc", "shell/source/win32", "setup_native/source/win32"):
            for path in sorted((tree / top).rglob("*")):
                if not path.is_file() or path.suffix not in (".scp", ".inc", ".cxx", ".hxx", ".h", ".c"):
                    continue
                text = path.read_text(encoding="latin-1")
                rel = str(path.relative_to(tree))
                upper = text.upper()
                left += [f"{rel}: {g}" for g in CLSIDS if g in upper]
                if path.suffix in (".scp", ".inc"):
                    text = re.sub(r"//[^\n]*", "", text)
                    left += [f"{rel}: {m}" for m in re.findall(r"soffice\.Star\w*|App Paths\\\w+|vnd\.libreoffice\.\w+(?=[ ,)])|Software\\LibreOffice\\|The Document Foundation", text)]
                elif "soffice.Star" in text:
                    left.append(f"{rel}: soffice.Star")
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
