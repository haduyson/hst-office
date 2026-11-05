# SPDX-License-Identifier: AGPL-3.0-only
"""Static analysis only, nothing executes: olevba reads each file as data. Run with `python -I` from another directory.

Usage: static_scan.py PKGDIR DIR OUT.jsonl [--jobs N]. PKGDIR holds oletools (pinned 0.60.2, pip --target). For each file:
macros yes/no, modules with source code, olevba's keyword analysis, the project code page, authoring application.
"""
import argparse
import concurrent.futures
import json
import logging
import multiprocessing
import os
import re
import signal
import sys
import zipfile

logging.disable(logging.CRITICAL)
EXTS = (".xls", ".xla", ".xlt", ".doc", ".dot", ".xlsm", ".xltm", ".xlam", ".xlsb", ".docm", ".dotm", ".xlsx", ".docx", ".pptm", ".ppt")


def office_app(path):
    """Application named in the document metadata, or ''."""
    import olefile
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as package:
                if "docProps/app.xml" in package.namelist():
                    text = package.read("docProps/app.xml")[:4000].decode("utf-8", "replace")
                    app = re.search(r"<Application>([^<]*)", text)
                    version = re.search(r"<AppVersion>([^<]*)", text)
                    return f"{app.group(1) if app else ''} {version.group(1) if version else ''}".strip()
            return ""
        if olefile.isOleFile(path):
            ole = olefile.OleFileIO(path)
            try:
                meta = ole.get_metadata()
                value = meta.creating_application or b""
                return value.decode("cp1252", "replace") if isinstance(value, bytes) else str(value)
            finally:
                ole.close()
    except Exception:  # noqa: BLE001 - damaged metadata
        return ""
    return ""


def project_codepage(path):
    """CodePage=NNN of the project's dir stream through pcodedmp-free parsing of the PROJECT text is unreliable: use oledir."""
    from oletools import olevba
    try:
        parser = olevba.VBA_Parser(path)
        try:
            for _sub, _stream, _name, _code in parser.extract_macros():
                break
            for sub in parser.ole_subfiles or [parser]:
                handle = sub.ole_file
                if handle is None:
                    continue
                for entry in handle.listdir():
                    if entry[-1].upper() == "DIR" and len(entry) >= 2 and entry[-2].upper() == "VBA":
                        raw = olevba.decompress_stream(bytearray(handle.openstream(entry).read()))
                        at = raw.find(b"\x03\x00\x02\x00\x00\x00")  # PROJECTCODEPAGE record
                        if at >= 0:
                            return int.from_bytes(raw[at + 6:at + 8], "little")
        finally:
            parser.close()
    except Exception:  # noqa: BLE001 - only informative
        return None
    return None


def scan_one(path):
    from oletools import olevba
    signal.alarm(120)
    result = dict(name=os.path.basename(path), bytes=os.path.getsize(path), app=office_app(path))
    try:
        parser = olevba.VBA_Parser(path)
        try:
            result["has_macros"] = bool(parser.detect_vba_macros())
            result["type"] = parser.type
            if result["has_macros"]:
                result["modules"] = [dict(stream=stream, module=name, code=code)
                                     for (_sub, stream, name, code) in parser.extract_macros()]
                result["analysis"] = [dict(kind=kind, keyword=keyword, description=description[:120])
                                      for kind, keyword, description in (parser.analyze_macros() or [])]
        finally:
            parser.close()
        if result["has_macros"]:
            result["codepage"] = project_codepage(path)
    except BaseException as error:  # noqa: BLE001 - encrypted or damaged, also the alarm
        result.update(has_macros=False, error=f"{type(error).__name__}: {error}"[:200])
    signal.alarm(0)
    return result


def alarm(_signum, _frame):
    raise TimeoutError("scan took too long")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pkgdir")
    parser.add_argument("dir")
    parser.add_argument("out")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    sys.path.insert(0, os.path.abspath(args.pkgdir))
    signal.signal(signal.SIGALRM, alarm)
    names = sorted(n for n in os.listdir(args.dir) if n.lower().endswith(EXTS))
    done = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as handle:
            done = {json.loads(line)["name"] for line in handle}
    context = multiprocessing.get_context("fork")
    with concurrent.futures.ProcessPoolExecutor(args.jobs, mp_context=context) as pool, \
            open(args.out, "a", encoding="utf-8") as out:
        paths = [os.path.join(args.dir, n) for n in names if n not in done]
        for result in pool.map(scan_one, paths, chunksize=4):
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
