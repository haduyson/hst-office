# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the HST Office build does not name LibreOffice / The Document Foundation in its UI.

Usage: python3 tests/runtime/check-no-libreoffice-ui.py [--instdir upstream/libreoffice/instdir]
                                                         [--src upstream/libreoffice]

(a) About: the copyright text built by cui/source/dialogs/about.cxx has no "LibreOffice" and
    names the source code location, and that text is compiled into the installed program.
(b) Every installed Vietnamese .mo is free of "LibreOffice" / "Document Foundation" except
    the allow-listed entries (legal texts, extension site, engine version notes).
Exit 1 when any check fails.
"""
import argparse
import gettext
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_URL = "github.com/haduyson/hst-office"
NAMES = re.compile(r"libreoffice|document\s*foundation", re.IGNORECASE)

# (msgctxt prefix, reason). Matched against the .mo key "msgctxt" of each entry.
ALLOWED_CONTEXTS = (
    ("licensedialog|", "licence dialog: upstream copyright notice required by MPL-2.0 / third-party terms"),
    ("readme.xrm", "README/licence documents: credits and legal text"),
)
# Substrings that make an entry acceptable regardless of context.
ALLOWED_TEXT = (
    ("libreoffice-profile.zip", "name of the file the safe-mode export really writes (technical)"),
    ("extensions.libreoffice.org", "extension site kept on purpose"),
    ("hub.libreoffice.org/extensions", "extension site kept on purpose"),
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
    if SOURCE_URL not in text:
        failures.append(f"About copyright text lacks {SOURCE_URL}")
    needle = text.split("\n")[1 if "\n" in text else 0].encode("utf-16-le")  # notice first line
    libs = glob.glob(os.path.join(instdir, "program", "lib*.so"))
    if not any(needle in open(lib, "rb").read() for lib in libs):
        failures.append("About notice text is not compiled into any installed library (stale build?)")
    print(f"about: text ok ({len(text)} chars)")


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
    for line in failures:
        print("FAIL:", line)
    print("PASS" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
