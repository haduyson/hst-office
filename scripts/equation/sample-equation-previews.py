# SPDX-License-Identifier: AGPL-3.0-only
# Map docx OLE equations to their WMF/EMF preview and pick a stratified sample.
import sys, os, json, zipfile, re, random, collections
res = [json.loads(l) for l in open(sys.argv[1])]
corpus, outdir = sys.argv[2], sys.argv[3]
os.makedirs(outdir, exist_ok=True)
random.seed(7)
by_doc = collections.defaultdict(list)
for r in res:
    if 'sm' in r and r['id'].startswith('word_embeddings'):
        by_doc[r['doc']].append(r)
prev = {}
for doc in by_doc:
    path = [os.path.join(d, f) for d in (os.path.join(corpus, doc), os.path.join(corpus, 'img', doc))
            if os.path.isdir(d) for f in os.listdir(d) if f.endswith('.docx')][0]
    z = zipfile.ZipFile(path)
    rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', z.read('word/_rels/document.xml.rels').decode()))
    rels.update({k: v for v, k in re.findall(r'Target="([^"]+)"[^>]*Id="(rId\d+)"',
                                             z.read('word/_rels/document.xml.rels').decode())})
    x = z.read('word/document.xml').decode('utf8')
    for m in re.finditer(r'<w:object\b.*?</w:object>', x, re.S):
        blk = m.group(0)
        im = re.search(r'<v:imagedata[^>]*r:id="(rId\d+)"', blk)
        ob = re.search(r'<o:OLEObject[^>]*r:id="(rId\d+)"', blk)
        if im and ob and ob.group(1) in rels and im.group(1) in rels:
            key = re.sub(r'\W', '_', 'word/' + rels[ob.group(1)])
            prev[(doc, key)] = (path, 'word/' + rels[im.group(1)])
pick = []
cons = ['frac', 'root', 'matrix', 'pile', 'embell', 'fence', 'script', 'bigop', 'arrow', 'chem', 'viet', 'legacyfont', 'text']
cand = [r for rs in by_doc.values() for r in rs if (r['doc'], r['id'][:-0 or None]) in prev]
for c in cons:
    pool = [r for r in cand if c in r['constructs'] and r not in pick]
    pick += random.sample(pool, min(6, len(pool)))
pool = [r for r in cand if r not in pick and r.get('issues')]
pick += random.sample(pool, min(10, len(pool)))
pool = [r for r in cand if r not in pick]
pick += random.sample(pool, min(14, len(pool)))
for n, r in enumerate(pick):
    path, img = prev[(r['doc'], r['id'])]
    ext = img.rsplit('.', 1)[-1]
    open(os.path.join(outdir, '%03d.%s' % (n, ext)), 'wb').write(zipfile.ZipFile(path).read(img))
    r['n'] = n
    r['preview'] = '%03d.%s' % (n, ext)
json.dump(pick, open(os.path.join(outdir, 'sample.json'), 'w'), ensure_ascii=False, indent=0)
print(len(prev), 'previews mapped;', len(pick), 'sampled')
