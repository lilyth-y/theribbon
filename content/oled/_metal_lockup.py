"""Place the metal words into a portrait typographic lockup on exact black."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(r"C:\Users\USER\.cursor\projects\c-startingup-theribbon\assets")
OUT = Path(r"c:\startingup\theribbon\content\oled\type")
W, H = 1080, 1920
GOLD = (232, 206, 164)
FONTS = Path(r"c:\startingup\theribbon\content\oled\fonts")
LATIN = str(FONTS / "Cinzel.ttf")


def key_rgba(path: Path, cut: int = 18) -> Image.Image:
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    mx = rgb.max(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    alpha = np.where((chroma < 18) & (mx < cut), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), alpha]), "RGBA")


def trim(im: Image.Image, pad: int = 12) -> Image.Image:
    alpha = np.asarray(im)[:, :, 3]
    ys, xs = np.where(alpha > 0)
    box = (
        max(0, int(xs.min()) - pad),
        max(0, int(ys.min()) - pad),
        min(im.width, int(xs.max()) + pad),
        min(im.height, int(ys.max()) + pad),
    )
    return im.crop(box)


def fit_width(im: Image.Image, width: int) -> Image.Image:
    height = max(1, round(im.height * width / im.width))
    return im.resize((width, height), Image.Resampling.LANCZOS)


def tracked(draw, text, y, face, fill, tracking):
    widths = []
    for ch in text:
        box = face.getbbox(ch)
        widths.append(box[2] - box[0])
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) // 2
    for ch, width in zip(text, widths):
        box = face.getbbox(ch)
        draw.text((x - box[0], y), ch, font=face, fill=fill)
        x += width + tracking


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    en = fit_width(trim(key_rgba(ASSETS / "our-forever-metal.jpg")), 980)
    ko = fit_width(trim(key_rgba(ASSETS / "promise-metal-ko.jpg")), 860)
    write_lockup(OUT / "our-forever.png", [("en", en, 0), ("ko", ko, 48)])

    our = trim(key_rgba(ASSETS / "our-metal.jpg"))
    forever = trim(key_rgba(ASSETS / "forever-metal.jpg"))
    forever = fit_width(forever, 980)
    our = our.resize((max(1, round(our.width * forever.height / our.height)), forever.height), Image.Resampling.LANCZOS)
    if our.width > 980:
        our = fit_width(our, 980)
    ko_small = fit_width(trim(key_rgba(ASSETS / "promise-metal-ko.jpg")), 780)
    write_lockup(
        OUT / "our-forever-stack.png",
        [("our", our, 0), ("forever", forever, 28), ("ko", ko_small, 56)],
    )


def write_lockup(path: Path, rows: list[tuple[str, Image.Image, int]]) -> None:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    gap = sum(g for _, _, g in rows[1:])
    block_h = sum(im.height for _, im, _ in rows) + gap
    y = (H - block_h) // 2 + 30
    top = y
    for _, im, space in rows:
        y += space
        canvas.alpha_composite(im, ((W - im.width) // 2, y))
        y += im.height

    flat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(flat)
    face = ImageFont.truetype(LATIN, 26)
    face.set_variation_by_axes([550])
    label_y = max(80, top - 120)
    tracked(draw, "THEREBORN", label_y, face, GOLD + (255,), 14)
    rule_w = 140
    draw.line(((W - rule_w) // 2, label_y + 52, (W + rule_w) // 2, label_y + 52), fill=GOLD + (255,), width=2)
    canvas = Image.alpha_composite(canvas, flat)

    rgb = np.asarray(canvas.convert("RGB")).astype(np.int16)
    mx = rgb.max(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    rgb[(chroma < 16) & (mx < 14)] = 0
    rgb[mx <= 3] = 0
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(path, "PNG", optimize=True)
    saved = np.asarray(Image.open(path))
    smx = saved.max(axis=2)
    print(path.name, "black", round(float((smx == 0).mean()), 4), "dirty", int(((smx > 0) & (smx <= 3)).sum()), "heights", [im.height for _, im, _ in rows])


if __name__ == "__main__":
    main()
