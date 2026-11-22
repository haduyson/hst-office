# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST Công thức: which embedded objects are MathType equations, from their OLE data (no UNO here).

An OLE object's data is an OLE compound file; its root entry names the program that made it by class id:
  - Equation Editor 3.x ("Equation.3"), which Word removed in 2018, so these can no longer be edited there;
  - MathType 4-7 ("Equation.DSMT4"), written as MTEF version 5.
Both become Math formulas with the office's MathType import (com.sun.star.comp.Math.MathTypeFilter)."""
import struct

EQUATION3 = "0002CE02-0000-0000-C000-000000000046"
MATHTYPE = "0002CE03-0000-0000-C000-000000000046"
MATH = "078B7ABA-54FC-457F-8551-6147E776A997"  # LibreOffice Math (the CLSID property of a formula object)
SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")


def root_class_id(data):
    """The class id of the compound file's root entry as "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", "" if none."""
    if len(data) < 512 or data[:8] != SIGNATURE:
        return ""
    shift = struct.unpack_from("<H", data, 0x1E)[0]
    first_directory_sector = struct.unpack_from("<I", data, 0x30)[0]
    if not 7 <= shift <= 16 or first_directory_sector >= 0xFFFFFFFA:
        return ""
    entry = (first_directory_sector + 1) << shift
    if entry + 0x60 > len(data):
        return ""
    raw = data[entry + 0x50:entry + 0x60]
    first, second, third = struct.unpack_from("<IHH", raw)
    return "%08X-%04X-%04X-%s-%s" % (first, second, third, raw[8:10].hex().upper(), raw[10:].hex().upper())


def is_mathtype(data):
    """True for Equation Editor 3.x and MathType 4-7 equations."""
    return root_class_id(data) in (EQUATION3, MATHTYPE)


def is_math_clsid(clsid):
    return (clsid or "").upper() == MATH
