# SPDX-License-Identifier: AGPL-3.0-only
# Render each sampled equation twice through LibreOffice (UNO): the original WMF/EMF preview
# (what MathType drew) and the converted StarMath formula; then build side-by-side contact sheets.
import sys, os, json, subprocess, uno
from com.sun.star.beans import PropertyValue
from PIL import Image, ImageDraw


def pv(n, v):
    p = PropertyValue()
    p.Name, p.Value = n, v
    return p


port, vdir = sys.argv[1], os.path.abspath(sys.argv[2])
local = uno.getComponentContext()
res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
ctx = res.resolve('uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext' % port)
desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
sample = json.load(open(os.path.join(vdir, 'sample.json')))
draw = desk.loadComponentFromURL('private:factory/sdraw', '_blank', 0, (pv('Hidden', True),))
page = draw.DrawPages.getByIndex(0)
gef = ctx.ServiceManager.createInstanceWithContext('com.sun.star.drawing.GraphicExportFilter', ctx)
for r in (sample if not os.environ.get('SKIP_RENDER') else []):
    n = r['n']
    src = os.path.join(vdir, r['preview'])
    d = desk.loadComponentFromURL(uno.systemPathToFileUrl(src), '_blank', 0, (pv('Hidden', True),))
    d.storeToURL(uno.systemPathToFileUrl(os.path.join(vdir, '%03d-orig.png' % n)),
                 (pv('FilterName', 'draw_png_Export'),
                  pv('FilterData', uno.Any('[]com.sun.star.beans.PropertyValue',
                                           (pv('PixelWidth', 900), pv('PixelHeight', 0))))))
    d.close(True)
    shape = draw.createInstance('com.sun.star.drawing.OLE2Shape')
    page.add(shape)
    shape.CLSID = '078B7ABA-54FC-457F-8551-6147E776A997'
    model = shape.Model
    model.BaseFontHeight = 12
    model.Formula = r['sm']
    vis = shape.EmbeddedObject.getVisualAreaSize(1)
    shape.setSize(vis)  # the formula's natural size, no distortion
    gef.setSourceDocument(shape)
    w = max(200, int(shape.Size.Width / 2540 * 300))
    gef.filter((pv('URL', uno.systemPathToFileUrl(os.path.join(vdir, '%03d-conv.png' % n))),
                pv('MediaType', 'image/png'),
                pv('FilterData', uno.Any('[]com.sun.star.beans.PropertyValue', (pv('PixelWidth', w),)))))
    page.remove(shape)
draw.close(True)


def flat(path):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, 'white')
    return Image.alpha_composite(bg, im).convert('RGB')


def trim(im):
    g = im.convert('L').point(lambda x: 0 if x > 245 else 255)
    bb = g.getbbox()
    return im.crop(bb) if bb else im


rows = []
for r in sample:
    n = r['n']
    a = trim(flat(os.path.join(vdir, '%03d-orig.png' % n)))
    b = trim(flat(os.path.join(vdir, '%03d-conv.png' % n)))
    for im in (a, b):
        if im.width > 760:
            im.thumbnail((760, 400))
    a.thumbnail((760, 400))
    b.thumbnail((760, 400))
    h = max(a.height, b.height) + 26
    row = Image.new('RGB', (1560, h), 'white')
    row.paste(a, (10, 22))
    row.paste(b, (790, 22))
    dr = ImageDraw.Draw(row)
    dr.text((10, 4), '#%03d %s %s %s' % (n, r['doc'], ','.join(r['constructs']), ','.join(r.get('issues', {}))),
            fill='blue')
    dr.line((780, 0, 780, h), fill='gray')
    dr.line((0, h - 1, 1560, h - 1), fill='gray')
    rows.append(row)
sheet, y, k = Image.new('RGB', (1560, 1500), 'white'), 0, 0
for row in rows + [None]:
    if row is None or (sheet is not None and y + row.height > 1500):
        sheet.crop((0, 0, 1560, max(y, 1))).save(os.path.join(vdir, 'sheet-%02d.png' % k))
        k += 1
        sheet, y = Image.new('RGB', (1560, 1500), 'white'), 0
        if row is None:
            break
    sheet.paste(row, (0, y))
    y += row.height
print('sheets', k)
