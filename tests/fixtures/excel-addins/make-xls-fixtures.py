#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Make the two .xls fixtures of tests/runtime/check-sheets-vnd-usd.py (run once by a developer; the outputs are
committed). Needs olefile and an HST Sheets build (its Python runs this script's UNO part).

Usage: <instdir>/program/python make-xls-fixtures.py <instdir>/program/soffice <port>

  xll-addin.xls      calls of an XLL add-in function as BIFF8 stores them ([MS-XLS] 2.4.271 SupBook with
                     cch=0x3A01 "add-in referencing", 2.4.105 ExternName per function, formulas ptgNameX + ptgFuncVar
                     with iftab 255): written by HST Sheets itself from =VND(A1) etc., whose add-in functions it
                     exports exactly this way.
  vntools-addin.xls  calls of a function of an add-in workbook: the same records with the add-in SupBook replaced by
                     an external-workbook SupBook whose virtPath is C:\\Program Files (x86)\\vnTools\\Ufunctions.xlam
                     ([MS-XLS] 2.5.277 VirtualPath: \\x01\\x01 volume, \\x03 directory separator), so each formula is
                     ptgNameX -> ExternName "VND" of that workbook + ptgFuncVar(255), as Excel writes .xla/.xlam UDF
                     calls. Written into a fresh one-stream compound file ([MS-CFB] version 3).
"""
import os
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "runtime"))
from excel_addin_fixtures import write_xlsx  # noqa: E402

CELLS = {"A1": 1500.25, "A2": 309848560,
         "B1": ("VND(A1)", ""), "B2": ("VND(A1,TRUE)", ""), "B3": ("USD(A1,TRUE)", ""),
         "B4": ('VND(A1,TRUE,1,"đồng","xu")', ""), "B5": ("USD(A1)", ""), "B6": ("VND(A2,,,,,TRUE)", "")}
VNTOOLS = b"\x01\x01C\x03Program Files (x86)\x03vnTools\x03Ufunctions.xlam"
FREE, END, FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD


def records(data):
    pos = 0
    while pos < len(data):
        kind, size = struct.unpack_from("<HH", data, pos)
        yield kind, data[pos + 4:pos + 4 + size]
        pos += 4 + size


def serialise(recs):
    return b"".join(struct.pack("<HH", kind, len(body)) + body for kind, body in recs)


def to_vntools(stream):
    recs = [(k, struct.pack("<HH", 0, len(VNTOOLS)) + b"\x00" + VNTOOLS if k == 0x01AE and b == b"\x01\x00\x01\x3a"
             else b) for k, b in records(stream)]
    # BoundSheet8 (0x85) stores the stream position of its sheet's BOF: positions moved, write them again
    positions, pos = [], 0
    for kind, body in recs:
        if kind == 0x0809 and pos:
            positions.append(pos)
        pos += 4 + len(body)
    sheets = iter(positions)
    return serialise([(k, struct.pack("<I", next(sheets)) + b[4:] if k == 0x85 else b) for k, b in recs])


def write_cfb(path, stream):
    stream += b"\0" * max(0, 4096 - len(stream))  # at least the mini-stream cutoff: regular sectors only
    count = (len(stream) + 511) // 512
    stream += b"\0" * (count * 512 - len(stream))
    fat = [FATSECT, END] + [3 + i if i < count - 1 else END for i in range(count)]
    fat += [FREE] * (128 - len(fat))

    def entry(name, kind, child, start, size):
        raw = name.encode("utf-16-le") + b"\0\0" if name else b""
        return (raw.ljust(64, b"\0") + struct.pack("<HBBIII", len(raw), kind, 1 if name else 0, FREE, FREE, child)
                + b"\0" * 36 + struct.pack("<IIi", start, size, 0))
    directory = (entry("Root Entry", 5, 1, END, 0) + entry("Workbook", 2, FREE, 2, len(stream))
                 + entry("", 0, FREE, 0, 0) * 2)
    header = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6)
              + b"\0" * 6 + struct.pack("<IIIIIIIII", 0, 1, 1, 0, 4096, END, 0, END, 0)
              + struct.pack("<I", 0) + struct.pack("<I", FREE) * 108)
    with open(path, "wb") as handle:
        handle.write(header + struct.pack("<128I", *fat) + directory + stream)


def export_xls(soffice, port, source, target):
    import uno
    from com.sun.star.beans import PropertyValue
    with tempfile.TemporaryDirectory() as profile:
        office = subprocess.Popen([soffice, "--headless", "--norestore", "-env:UserInstallation=file://" + profile,
                                   "--accept=socket,host=127.0.0.1,port=%s;urp;" % port])
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            for _ in range(120):
                try:
                    ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext" % port)
                    break
                except Exception:  # noqa: BLE001 - the office is still starting
                    time.sleep(1)
            desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(source), "_blank", 0,
                                               (PropertyValue(Name="Hidden", Value=True),))
            doc.storeToURL(uno.systemPathToFileUrl(target), (PropertyValue(Name="FilterName", Value="MS Excel 97"),))
            doc.close(True)
            desktop.terminate()
        finally:
            time.sleep(2)
            if office.poll() is None:
                office.terminate()
            office.wait(30)


def main():
    import olefile
    soffice, port = sys.argv[1], sys.argv[2]
    with tempfile.TemporaryDirectory() as tmp:
        source = write_xlsx(os.path.join(tmp, "plain.xlsx"), CELLS)
        xll = os.path.join(HERE, "xll-addin.xls")
        export_xls(soffice, port, source, xll)
    stream = olefile.OleFileIO(xll).openstream("Workbook").read()
    assert b"\x01\x00\x01\x3a" in stream, "no add-in SupBook in the export"
    write_cfb(os.path.join(HERE, "vntools-addin.xls"), to_vntools(stream))
    print("wrote xll-addin.xls, vntools-addin.xls")


if __name__ == "__main__":
    main()
