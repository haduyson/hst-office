# SPDX-License-Identifier: AGPL-3.0-only
# Insert converted formulas as Math objects in a Writer document, save as .docx (OMML), reopen,
# and check that every formula comes back as a Math object with the same letters/digits/=/+.
import sys, os, json, re, html, unicodedata, collections, zipfile, uno
from com.sun.star.beans import PropertyValue


def pv(n, v):
    p = PropertyValue()
    p.Name, p.Value = n, v
    return p


port, src, outdir = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
os.makedirs(outdir, exist_ok=True)
l = uno.getComponentContext()
ctx = l.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', l).resolve(
    'uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext' % port)
desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
recs = [json.loads(x) for x in open(src)]
recs = [r for r in recs if 'sm' in r]
limit = int(os.environ.get('LIMIT', '0')) or len(recs)
recs = recs[:limit]
from com.sun.star.text.TextContentAnchorType import AS_CHARACTER
doc = desk.loadComponentFromURL('private:factory/swriter', '_blank', 0, (pv('Hidden', True),))
text = doc.Text
for r in recs:
    cur = text.getEnd()
    obj = doc.createInstance('com.sun.star.text.TextEmbeddedObject')
    obj.CLSID = '078B7ABA-54FC-457F-8551-6147E776A997'
    obj.AnchorType = AS_CHARACTER
    text.insertTextContent(cur, obj, False)
    obj.Model.Formula = r['sm']
    text.insertControlCharacter(text.getEnd(), 0, False)  # paragraph break
path = os.path.join(outdir, 'roundtrip.docx')
doc.storeToURL(uno.systemPathToFileUrl(path), (pv('FilterName', 'MS Word 2007 XML'),))
doc.close(True)
xml = zipfile.ZipFile(path).read('word/document.xml').decode('utf8')
n_omml = len(re.findall(r'<m:oMath>', xml))
n_ole = xml.count('<o:OLEObject')
doc = desk.loadComponentFromURL(uno.systemPathToFileUrl(path), '_blank', 0, (pv('Hidden', True),))
back = []
pe = doc.Text.createEnumeration()
while pe.hasMoreElements():
    para = pe.nextElement()
    if not para.supportsService('com.sun.star.text.Paragraph'):
        continue
    found = None
    po = para.createEnumeration()
    while po.hasMoreElements():
        portion = po.nextElement()
        if portion.TextPortionType == 'Frame':
            ce = portion.createContentEnumeration('com.sun.star.text.TextContent')
            while ce.hasMoreElements():
                c = ce.nextElement()
                if c.supportsService('com.sun.star.text.TextEmbeddedObject'):
                    try:
                        found = c.Model.Formula
                    except Exception:
                        found = ''
    if found is not None:
        back.append(found)
math = desk.loadComponentFromURL('private:factory/smath', '_blank', 0, (pv('Hidden', True),))
url = uno.systemPathToFileUrl(os.path.join(outdir, 'f.mml'))


def chars(sm):
    math.Formula = sm
    math.storeToURL(url, (pv('FilterName', 'MathML XML (Math)'),))
    mml = open(os.path.join(outdir, 'f.mml'), encoding='utf8').read().split('<annotation')[0]
    toks = unicodedata.normalize('NFC', html.unescape(''.join(
        re.findall(r'<m(?:i|n|o|text)[^>]*>([^<]*)</m(?:i|n|o|text)>', mml))))
    return collections.Counter(c for c in toks if c.isalnum() or c in '=+')


bad = []
for r, b in zip(recs, back):
    exp = collections.Counter(unicodedata.normalize('NFC', r['chars']))
    got = chars(b)
    if got != exp:
        bad.append(dict(doc=r['doc'], id=r['id'], sm=r['sm'], back=b,
                        missing=''.join((exp - got).elements()), extra=''.join((got - exp).elements())))
math.close(True)
doc.close(True)
json.dump(bad, open(os.path.join(outdir, 'roundtrip-bad.json'), 'w'), ensure_ascii=False, indent=0)
print('formulas', len(recs), 'omml in docx', n_omml, 'ole in docx', n_ole, 'math objects after reload', len(back),
      'content mismatches', len(bad))
