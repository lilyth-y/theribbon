"""Slow brand-word reel for the transparent OLED.

Congratulatory guest messages were dropped. This reel carries only the
company's own words. Preview MP4 is H.264 yuv420p; frame-000.png is the exact
#000000 still.
"""

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 24
SECONDS = 12
IVORY = (255, 248, 240, 255)
GOLD = (232, 206, 164, 255)
ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
TITLE_KO = str(FONTS / "GowunBatang-Bold.ttf")
BODY_KO = str(FONTS / "GowunBatang-Regular.ttf")
LATIN = str(FONTS / "Cinzel.ttf")
OUT = ROOT / "flow"

LINES = [
    ("끊이지 않는 인연", 96, IVORY, TITLE_KO, None, -160),
    ("RE:BORN", 72, GOLD, LATIN, 550, 210),
    ("다시, 태어나다", 92, IVORY, TITLE_KO, None, -80),
    ("평생의 동반자", 84, GOLD, BODY_KO, None, 150),
    ("특별한 순간", 100, IVORY, TITLE_KO, None, -130),
    ("정직과 봉사", 78, GOLD, BODY_KO, None, 120),
    ("더 리:본", 92, IVORY, TITLE_KO, None, 0),
]


def load_face(path: str, size: int, weight: int | None):
    face = ImageFont.truetype(path, size)
    if weight is not None:
        face.set_variation_by_axes([weight])
    return face


FACES = {(path, size, weight): load_face(path, size, weight) for _, size, _, path, weight, _ in LINES}


def draw_frame(t: float) -> Image.Image:
    im = Image.new("RGB", (W, H), (0, 0, 0))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    span = H + 280
    travel = (t / SECONDS) * span
    for index, (text, size, fill, path, weight, xoff) in enumerate(LINES):
        y = int((index * span / len(LINES) - travel) % span - 140)
        x = W // 2 + xoff + int(36 * math.sin(t * 0.7 + index))
        face = FACES[(path, size, weight)]
        draw.text((x, y), text, font=face, fill=fill, anchor="mm")
    pts = []
    phase = t * 0.8
    for i in range(0, H, 18):
        x = int(W * 0.5 + 140 * math.sin(i / 220 + phase))
        y = int((i + travel * 0.35) % H)
        pts.append((x, y))
    if len(pts) > 1:
        draw.line(pts, fill=(186, 154, 108, 90), width=2)
    rgb = np.asarray(Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")).astype(np.int16)
    mx = rgb.max(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    rgb[(chroma < 14) & (mx < 12)] = 0
    rgb[mx <= 3] = 0
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    first = draw_frame(0)
    first.save(OUT / "frame-000.png", "PNG", optimize=True)
    preview = OUT / "brand-flow-preview.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(preview),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    frames = FPS * SECONDS
    for i in range(frames):
        frame = first if i == 0 else draw_frame(i / FPS)
        proc.stdin.write(np.asarray(frame).tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(err[-2000:])
    arr = np.asarray(first)
    mx = arr.max(axis=2)
    print("png", first.size, "black", round(float((mx == 0).mean()), 4), "dirty", int(((mx > 0) & (mx <= 3)).sum()))
    print("mp4", preview, "frames", frames)


if __name__ == "__main__":
    main()
