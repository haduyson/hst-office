# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Extract "Equation Native" (MTEF) streams from .doc/.docx. Read-only; never runs macros.
import sys, os, io, zipfile, json, re, struct
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfb_reader import CFB


def compobj_progid(ole, prefix):
    i = ole.find(prefix + ['\x01CompObj'])
    if i is None:
        return None
    d = ole.read(ole.ents[i])
    # CompObj: 28-byte header, then user type, clipboard format, progid (length-prefixed ANSI)
    try:
        o = 28
        out = []
        for _ in range(3):
            n = struct.unpack_from('<I', d, o)[0]
            o += 4
            if n in (0xffffffff, 0xfffffffe):
                o += 4
                out.append('')
                continue
            out.append(d[o:o + n].rstrip(b'\0').decode('latin1'))
            o += n
        return out[2]
    except Exception:
        return None


def mtef_info(b):
    if len(b) < 33:
        return {}
    cb = struct.unpack_from('<H', b, 0)[0]
    m = b[cb:]
    r = dict(hdr=cb, mtef=m[0], platform=m[1], product=m[2], prodver=f'{m[3]}.{m[4]}')
    if m[0] >= 5:
        e = m.find(b'\0', 5)
        r['appkey'] = m[5:e].decode('latin1')
    return r


def from_ole(ole, prefix, tag, outdir, res):
    pid = compobj_progid(ole, prefix)
    i = ole.find(prefix + ['Equation Native'])
    if i is None:
        res.append(dict(id=tag, progid=pid, native=False))
        return
    b = ole.read(ole.ents[i])
    open(os.path.join(outdir, tag + '.eqn'), 'wb').write(b)
    r = dict(id=tag, progid=pid, native=True, bytes=len(b))
    r.update(mtef_info(b))
    res.append(r)


def doc(path, outdir, res):
    ole = CFB(open(path, 'rb').read())
    pi = ole.find(['ObjectPool'])
    if pi is None:
        return
    for name in sorted(ole.children(pi)):
        from_ole(ole, ['ObjectPool', name], 'pool' + name, outdir, res)


def docx(path, outdir, res):
    z = zipfile.ZipFile(path)
    for n in sorted(z.namelist()):
        if n.endswith('.bin') and 'embeddings' in n:
            d = z.read(n)
            if d[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                continue
            from_ole(CFB(d), [], re.sub(r'\W', '_', n), outdir, res)


src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
res = []
(docx if src.endswith('x') else doc)(src, outdir, res)
json.dump(res, open(os.path.join(outdir, 'index.json'), 'w'), indent=0)
print(os.path.basename(src), len(res), Counter(
    (r.get('progid'), r.get('mtef'), r.get('appkey'), r.get('product'), r.get('prodver')) for r in res).most_common())
