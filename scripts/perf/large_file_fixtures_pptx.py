# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Presentation fixtures for large_file_fixtures_sized.py (python-pptx; the media kind needs ffmpeg).

write_pptx_kind(path, kind, units):
- images   one distinct photo per slide (1280 px, as the presentation program compresses pictures) and a screenshot
           on every third slide (`units` slides)
- media    a title slide then one embedded H.264 clip per slide with its poster picture (`units` clips)
- shapes   `units` slides of about 120 shapes each: text boxes, filled autoshapes, connectors-like lines, a group and
           a small table (diagram-heavy decks)
All text is generated and all pictures and clips are noise; nothing here reads a user file.
"""
import io
import os
import random
import tempfile

from large_file_fixture_words import sentence
from large_file_fixtures_media import noise_png, photo_jpeg, video_mp4


def deck():
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def images_slide(prs, rnd, i):
    from pptx.util import Inches
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Hình %d: %s" % (i + 1, sentence(rnd, 5))
    slide.shapes.add_picture(io.BytesIO(photo_jpeg(rnd, 1280, 853)), Inches(0.8), Inches(1.4), width=Inches(7.5))
    if i % 3 == 0:
        slide.shapes.add_picture(io.BytesIO(noise_png(rnd, 1600, 1000)), Inches(8.6), Inches(1.6), width=Inches(4.3))
    box = slide.shapes.add_textbox(Inches(8.6), Inches(4.5), Inches(4.3), Inches(2.5)).text_frame
    box.word_wrap = True
    box.text = sentence(rnd, 30)


def media_slide(prs, rnd, i, tmp):
    from pptx.util import Inches
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Video %d: %s" % (i + 1, sentence(rnd, 4))
    clip = os.path.join(tmp, "clip%d.mp4" % i)
    with open(clip, "wb") as f:
        f.write(video_mp4(20, 2500, i))
    poster = os.path.join(tmp, "poster%d.jpg" % i)
    with open(poster, "wb") as f:
        f.write(photo_jpeg(rnd, 1280, 720))
    slide.shapes.add_movie(clip, Inches(1.5), Inches(1.4), Inches(10), Inches(5.6), poster_frame_image=poster,
                           mime_type="video/mp4")


def shapes_slide(prs, rnd, i):
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu, Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Sơ đồ %d: %s" % (i + 1, sentence(rnd, 4))
    kinds = (MSO_SHAPE.ROUNDED_RECTANGLE, MSO_SHAPE.OVAL, MSO_SHAPE.CHEVRON, MSO_SHAPE.RIGHT_ARROW, MSO_SHAPE.HEXAGON)
    w, h = prs.slide_width, prs.slide_height
    for k in range(100):
        x, y = rnd.randrange(0, w - Inches(1.5)), rnd.randrange(Inches(1.3), h - Inches(0.8))
        shp = slide.shapes.add_shape(kinds[k % 5], Emu(x), Emu(y), Inches(1.4), Inches(0.6))
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        shp.text_frame.text = sentence(rnd, 3)
        shp.text_frame.paragraphs[0].runs[0].font.size = Pt(9)
    group = slide.shapes.add_group_shape()
    for k in range(12):
        group.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.3 + k % 4), Inches(5 + k // 4 * 0.6), Inches(0.9),
                               Inches(0.5)).text_frame.text = str(k)
    for k in range(6):
        box = slide.shapes.add_textbox(Inches(0.5 + 2 * k), Inches(6.7), Inches(1.9), Inches(0.6)).text_frame
        box.word_wrap = True
        box.text = sentence(rnd, 10)
    rows, cols = 4, 4
    table = slide.shapes.add_table(rows, cols, Inches(9), Inches(0.2), Inches(4), Inches(1)).table
    for r in range(rows):
        for c in range(cols):
            table.cell(r, c).text = sentence(rnd, 1)


def write_pptx_kind(path, kind, units, seed=13):
    rnd = random.Random(seed)
    prs = deck()
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(units):
            if kind == "images":
                images_slide(prs, rnd, i)
            elif kind == "media":
                media_slide(prs, rnd, i, tmp)
            else:
                shapes_slide(prs, rnd, i)
        prs.core_properties.title = "Báo cáo tổng hợp"
        prs.save(path)
