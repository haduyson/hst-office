# SPDX-License-Identifier: AGPL-3.0-only
"""PNG encoding and review sheet for the offline ribbon banners."""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "extensions/hst-vietnamese-tools/banners"
FONT = ART / "fonts"


def png_bytes(image):
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def preview(outputs, solutions):
    comparison_y = 150 + len(solutions) * 240
    compact_y = comparison_y + 202
    sheet = Image.new("RGB", (1200, compact_y + 300), "#f2f5f8")
    draw = ImageDraw.Draw(sheet)
    bold = ImageFont.truetype(str(FONT / "BeVietnamPro-Bold.ttf"), 24)
    regular = ImageFont.truetype(str(FONT / "BeVietnamPro-Regular.ttf"), 14)
    draw.text((32, 22), "HASON TECH · Banner công ty và giải pháp", font=bold, fill="#192d43")
    draw.text((32, 60), "360 × 104 px · 6 giải pháp + HASON TECH · Chu kỳ 10 giây", font=regular, fill="#526071")
    draw.text((32, 94), "1× · Kích thước trên ribbon", font=regular, fill="#526071")
    draw.text((440, 94), "2× · Xuất ảnh cho màn hình mật độ cao", font=regular, fill="#526071")
    for n, solution in enumerate(solutions):
        y = 130 + n * 240
        for scale, x in ((1, 32), (2, 440)):
            im = Image.open(io.BytesIO(outputs[ART / f'{solution["id"]}@{scale}x.png']))
            sheet.paste(im, (x, y), im)
    draw.text((32, comparison_y), "HST Post / eChatbot · So sánh bảng màu", font=bold, fill="#192d43")
    draw.text((32, comparison_y + 38), "1× · Xanh lá cây đậm / Xanh ngọc đậm", font=regular, fill="#526071")
    for name, x in (("hst-post", 32), ("echatbot", 440)):
        im = Image.open(io.BytesIO(outputs[ART / f"{name}@1x.png"]))
        sheet.paste(im, (x, comparison_y + 70), im)
    draw.text((32, compact_y), "Ảnh thu gọn · 160 × 104 px · Cửa sổ hẹp hơn 1280 px", font=bold, fill="#192d43")
    draw.text((32, compact_y + 38), "1× trên nền sáng · 1× trên nền tối (thẻ sáng)", font=regular, fill="#526071")
    draw.rectangle((0, compact_y + 186, 1200, compact_y + 300), fill="#2b2b2b")
    for n, solution in enumerate(solutions):
        im = Image.open(io.BytesIO(outputs[ART / f'{solution["id"]}-compact@1x.png']))
        sheet.paste(im, (32 + n * 166, compact_y + 70), im)
        sheet.paste(im, (32 + n * 166, compact_y + 192), im)
    return png_bytes(sheet)
