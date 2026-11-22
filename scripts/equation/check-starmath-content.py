# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Feed every generated StarMath formula to a running LibreOffice Math (UNO) and flag parse errors.
# A StarMath parse error becomes an SmErrorNode, exported to MathML as the U+00BF glyph.
import sys, json, os, time, re, html, unicodedata, collections, uno
from com.sun.star.beans import PropertyValue


def pv(n, v):
    p = PropertyValue()
    p.Name, p.Value = n, v
    return p


port, src, dst, tmp = sys.argv[1], sys.argv[2], sys.argv[3], os.path.abspath(sys.argv[4])
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
for _ in range(60):
    try:
        ctx = resolver.resolve('uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext' % port)
        break
    except Exception:
        time.sleep(1)
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
doc = desktop.loadComponentFromURL('private:factory/smath', '_blank', 0, (pv('Hidden', True),))
url = uno.systemPathToFileUrl(os.path.join(tmp, 'f.mml'))
out = open(dst, 'w')
n = bad = 0
for line in open(src):
    r = json.loads(line)
    if 'sm' not in r:
        out.write(line)
        continue
    doc.Formula = r['sm']
    doc.storeToURL(url, (pv('FilterName', 'MathML XML (Math)'),))
    mml = open(os.path.join(tmp, 'f.mml'), encoding='utf8').read()
    # content check: letters/digits/=/+ of the rendered MathML must equal those of the MTEF source
    body = mml.split('<annotation')[0]
    toks = ''.join(re.findall(r'<m(?:i|n|o|text)[^>]*>([^<]*)</m(?:i|n|o|text)>', body))
    toks = unicodedata.normalize('NFC', html.unescape(toks))
    got = collections.Counter(c for c in toks if c.isalnum() or c in '=+')
    exp = collections.Counter(unicodedata.normalize('NFC', r.get('chars', '')))
    err = got != exp
    r['lo_parse_error'] = err
    if err:
        r['char_diff'] = dict(missing=''.join((exp - got).elements()), extra=''.join((got - exp).elements()))
    n += 1
    bad += err
    out.write(json.dumps(r, ensure_ascii=False) + '\n')
doc.close(True)
print('checked', n, 'parse errors', bad)
