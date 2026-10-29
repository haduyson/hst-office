# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the HST Office build does not name LibreOffice / The Document Foundation in its UI.

Usage: python3 tests/runtime/check-no-libreoffice-ui.py [--instdir upstream/libreoffice/instdir]
                                                         [--src upstream/libreoffice]

(a) About: the copyright text built by cui/source/dialogs/about.cxx has no "LibreOffice", no
    URL and no "github", and that text is compiled into the installed program.
(b) Every installed Vietnamese .mo is free of "LibreOffice" / "Document Foundation" except
    the allow-listed entries (legal texts, engine version notes).
(c) The source-code notice (contact e-mail, no URL) is at the top of the licence document
    (LICENSE.html / LICENSE) and in the Help > License Information dialog source.
(d) No "github" (any case) in installed UI resources: .mo catalogues, registry .xcd, menubar /
    notebookbar / dialog definitions under share/config, the HST extension. Allow-listed with a
    reason: the licence documents (third-party sections) and the bundled third-party dictionary
    extensions (their authors' project pages).
(e) No link to an online extension catalogue (extensions.libreoffice.org, hub.libreoffice.org/extensions)
    in the same resources, except the licence documents and the third-party dictionary extensions.
Exit 1 when any check fails.
"""
import argparse
import gettext
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GITHUB = re.compile(r"github", re.IGNORECASE)
CATALOGUE = re.compile(r"extensions\.libreoffice\.org|hub\.libreoffice\.org/extensions", re.IGNORECASE)
NOTICE_MAIL = "lienhe@hasontech.vn"
NAMES = re.compile(r"libreoffice|document\s*foundation", re.IGNORECASE)

# (msgctxt prefix, reason). Matched against the .mo key "msgctxt" of each entry.
ALLOWED_CONTEXTS = (
    ("licensedialog|", "licence dialog: upstream copyright notice required by MPL-2.0 / third-party terms"),
    ("readme.xrm", "README/licence documents: credits and legal text"),
)
# Substrings that make an entry acceptable regardless of context.
ALLOWED_TEXT = (
    ("libreoffice-profile.zip", "name of the file the safe-mode export really writes (technical)"),
)


def copyright_text(src):
    """Text assembled by AboutDialog::GetCopyrightString (string literals only)."""
    with open(os.path.join(src, "cui/source/dialogs/about.cxx"), encoding="utf-8") as handle:
        code = handle.read()
    body = code.split("OUString AboutDialog::GetCopyrightString()", 1)[1].split("return aCopyrightString", 1)[0]
    literals = re.findall(r'u"((?:[^"\\]|\\.)*)"', body)
    decode = lambda s: re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), s).replace("\\n", "\n")
    return "".join(decode(s) for s in literals)


def check_about(instdir, src, failures):
    text = copyright_text(src)
    if NAMES.search(text):
        failures.append("About copyright text names LibreOffice/Document Foundation")
    if re.search(r"https?://|www\.", text) or GITHUB.search(text):
        failures.append("About copyright text contains a URL or github")
    if "Th\u00F4ng tin gi\u1EA5y ph\u00E9p" not in text:
        failures.append("About copyright text does not point to Help > License Information")
    needle = text.split("\n")[0].encode("utf-16-le")  # notice line
    libs = glob.glob(os.path.join(instdir, "program", "lib*.so"))
    if not any(needle in open(lib, "rb").read() for lib in libs):
        failures.append("About notice text is not compiled into any installed library (stale build?)")
    print(f"about: text ok ({len(text)} chars)")


def check_licence(instdir, src, failures):
    """HST source-code notice at the top of the licence document and in the dialog source."""
    for name in ("LICENSE.html", "LICENSE"):
        path = os.path.join(instdir, name)
        if not os.path.isfile(path):
            failures.append(f"{name} not installed")
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            head = handle.read(6000)
        start = head.find("HST Office l")  # Vietnamese notice paragraph
        end = head.find("This product is made available subject")  # upstream licence text
        section = head[start:end] if 0 <= start < end else ""
        if NOTICE_MAIL not in section or "HST Office is open-source" not in section:
            failures.append(f"{name}: no HST source-code notice before the upstream licence text")
        if re.search(r"https?://|github", section, re.IGNORECASE):
            failures.append(f"{name}: HST notice section contains a URL")
    with open(os.path.join(src, "sfx2/source/appl/appserv.cxx"), encoding="utf-8") as handle:
        code = handle.read()
    if NOTICE_MAIL not in code.split("class LicenseDialog", 1)[1].split("class SafeModeQueryDialog", 1)[0]:
        failures.append("Help > License Information dialog source lacks the notice")
    print("licence: notice checked")


# Directories (relative to instdir) whose files are UI resources for (d)/(e); a file is skipped
# only when it matches ALLOWED_FILES.
UI_ROOTS = ("share/registry", "share/config", "share/extensions/hst-vietnamese-tools")
UI_SUFFIXES = (".xcd", ".xml", ".ui", ".xcu", ".xcs", ".txt", ".json", ".py", ".xdl")
ALLOWED_FILES = (("share/extensions/dict-", "bundled third-party dictionary extensions: authors' project pages"),)


def check_links(instdir, failures):
    scanned = hits = 0
    for root in UI_ROOTS:
        for base, _dirs, names in os.walk(os.path.join(instdir, root)):
            for name in names:
                path = os.path.join(base, name)
                rel = os.path.relpath(path, instdir)
                if not name.endswith(UI_SUFFIXES) or any(rel.startswith(p) for p, _ in ALLOWED_FILES):
                    continue
                with open(path, encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
                scanned += 1
                for label, pattern in (("github", GITHUB), ("extension catalogue", CATALOGUE)):
                    match = pattern.search(content)
                    if match:
                        hits += 1
                        failures.append(f"{rel}: {label} reference {content[max(0, match.start() - 30):match.end() + 40]!r}")
    print(f"links: {scanned} resource files scanned, {hits} github/catalogue references")


def allowed(key, text):
    ctx = key.split("\x04", 1)[0] if "\x04" in key else ""
    for prefix, _ in ALLOWED_CONTEXTS:
        if ctx.startswith(prefix):
            return True
    rest = text
    for token, _ in ALLOWED_TEXT:
        rest = rest.replace(token, "")
    return rest != text and not NAMES.search(rest)


def check_mo(instdir, failures):
    files = sorted(glob.glob(os.path.join(instdir, "program/resource/vi/LC_MESSAGES/*.mo")))
    if not files:
        failures.append("no Vietnamese .mo files installed")
    hits = 0
    for path in files:
        with open(path, "rb") as handle:
            catalog = gettext.GNUTranslations(handle)._catalog
        for key, text in catalog.items():
            if isinstance(text, str) and (GITHUB.search(text) or CATALOGUE.search(text)):
                failures.append(f"{os.path.basename(path)}: github/catalogue reference in {str(key)[:60]!r}")
            if not key or not isinstance(text, str) or not NAMES.search(text):
                continue
            if allowed(key if isinstance(key, str) else "", text):
                continue
            hits += 1
            failures.append(f"{os.path.basename(path)}: {str(key)[:70]!r} -> {text[:90]!r}")
    print(f"mo: {len(files)} files, {hits} unexpected mentions")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--src", default=os.path.join(ROOT, "upstream/libreoffice"))
    args = parser.parse_args()
    failures = []
    check_about(args.instdir, args.src, failures)
    check_mo(args.instdir, failures)
    check_licence(args.instdir, args.src, failures)
    check_links(args.instdir, failures)
    for line in failures:
        print("FAIL:", line)
    print("PASS" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
