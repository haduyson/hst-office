# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic pictures and video for the sized office fixtures (large_file_fixtures_sized.py). Needs Pillow; the video
needs ffmpeg on PATH. Nothing here reads a user file: every picture is generated noise."""
import io
import os
import subprocess
import tempfile


def photo_jpeg(rnd, w, h, quality=85):
    """A camera-sized photo: smooth blurred noise compresses like a real photo (about 0.3 bytes per pixel)."""
    from PIL import Image, ImageFilter
    img = Image.frombytes("RGB", (w // 8, h // 8), rnd.randbytes((w // 8) * (h // 8) * 3))
    img = img.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))
    grain = Image.frombytes("L", (w, h), rnd.randbytes(w * h)).convert("RGB")
    img = Image.blend(img, grain, 0.12)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def noise_png(rnd, w, h):
    """A screenshot: flat panels with rows of small 'text' blocks (what a pasted screen capture looks like)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), (246, 246, 246))
    d = ImageDraw.Draw(img)
    for _ in range(12):
        x, y = rnd.randrange(w - 200), rnd.randrange(h - 120)
        d.rectangle([x, y, x + rnd.randrange(100, w // 2), y + rnd.randrange(60, h // 3)],
                    fill=tuple(rnd.randrange(150, 256) for _ in range(3)))
    for y in range(20, h - 20, 18):
        x = 20
        while x < w - 60:
            word = rnd.randrange(12, 60)
            d.rectangle([x, y, x + word, y + 9], fill=tuple(rnd.randrange(0, 120) for _ in range(3)))
            x += word + rnd.randrange(5, 12)
    img.paste(Image.frombytes("RGB", (w // 4, h // 4), rnd.randbytes((w // 4) * (h // 4) * 3)), (w // 2, h // 2))
    buf = io.BytesIO()  # the pasted noise is a photo inside the capture, as screenshots of web pages have
    img.save(buf, "PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def video_mp4(seconds, kbps, seed):
    """An H.264 clip of moving noise at about kbps (so its size is seconds*kbps/8 KB); ffmpeg is required."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "cellauto=s=640x360:rate=25:rule=%d,format=yuv420p" % (18 + seed % 200),
                        "-t", str(seconds), "-c:v", "libx264", "-b:v", "%dk" % kbps, "-maxrate", "%dk" % kbps,
                        "-bufsize", "%dk" % (2 * kbps), "-pix_fmt", "yuv420p", path], check=True)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.remove(path)
