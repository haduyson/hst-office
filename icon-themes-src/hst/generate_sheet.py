# SPDX-License-Identifier: AGPL-3.0-only
"""Contact sheets of the rendered icon sets: native pixels, no resampling."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SIZES = (16, 24, 32)


def contact_sheet(families, stage, theme, palette, rendered):
    # Every icon is pasted at its native pixel size. No resampling, supersampling
    # or device-scale multiplier. Pages allow 100% inspection of the large stage.
    cols, cell_w, cell_h = 6, 204, 80
    width = cols*cell_w
    header = 52
    font_path = REPO/'extensions/hst-vietnamese-tools/banners/fonts/BeVietnamPro-Regular.ttf'
    font = ImageFont.truetype(str(font_path), 11)
    heading = ImageFont.truetype(str(font_path), 16)
    selected = [f for f in families if f['stage'] == stage]

    def draw_sheet(items, offset=0):
        height = header + math.ceil(len(items)/cols)*cell_h
        sheet = Image.new('RGB', (width, height), palette['surface'])
        d = ImageDraw.Draw(sheet)
        d.text((12, 8), f'HST · Stage {stage} · {palette["mode"]} · 100% · 16 / 24 / 32 px', font=heading, fill=palette['text'])
        d.text((12, 31), f'{len(selected)} original glyphs · each group: 16, 24, 32 native pixels · no scaling', font=font, fill=palette['text'])
        for i, f in enumerate(items):
            x, y = (i % cols)*cell_w, header+(i//cols)*cell_h
            d.line((x, y+cell_h-1, x+cell_w, y+cell_h-1), fill=palette['line'])
            for px, size in zip((16, 62, 119), SIZES):
                icon=rendered[theme, f['glyph'], size]
                sheet.paste(icon, (x+px, y+4+(32-size)//2), icon)
            name=f['glyph']
            # Two lines for long UNO resource names; never hide the suffix.
            prefix=f'{offset+i+1:03d} '
            split=len(name)
            while font.getlength(prefix+name[:split])>cell_w-16:
                split-=1
            lines=[name] if split==len(name) else [name[:split],name[split:]]
            for j,line in enumerate(lines):
                d.text((x+8, y+42+13*j), f'{offset+i+1:03d} '+line if j==0 else '    '+line, font=font, fill=palette['text'])
        return sheet

    out = ROOT/'contact-sheets'
    out.mkdir(exist_ok=True)
    draw_sheet(selected).save(out/f'stage-{stage}-{palette["mode"]}.png')
    if len(selected)>90:
        for i in range(0,len(selected),60):
            draw_sheet(selected[i:i+60],i).save(out/f'stage-{stage}-{palette["mode"]}-page-{i//60+1:02}.png')
