"""Transparent-OLED overlay stills for The Ribbon.

Install files are RGB PNG, 1080x1920, with exact #000000. On the panel those
pixels are transparent. Do not use the preview JPGs on the glass.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
COUPLES = ROOT.parent / "couples"
CAST_PATH = COUPLES / "cast.json"
FONTS = ROOT / "fonts"
W, H = 1080, 1920

IVORY = (255, 248, 240)
GOLD = (232, 206, 164)
GOLD_DIM = (168, 142, 108)
BLUSH = (255, 214, 206)
ORANGE = (255, 176, 110)

TITLE_KO = str(FONTS / "GowunBatang-Bold.ttf")
BODY_KO = str(FONTS / "GowunBatang-Regular.ttf")
LATIN = str(FONTS / "Cinzel.ttf")
SANS_KO = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"

# Single-hall per floor (1차 도입 기준: 층당 단독 홀의 시간대별 예식 안내, 임시 시각)
SAMPLE_HALLS = [
    {"hall": "12:00 예식", "time": "진행 예정", "id": "01"},
    {"hall": "14:00 예식", "time": "다음 예식", "id": "02"},
]


def font(path: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(path, size)
    if weight is not None:
        face.set_variation_by_axes([weight])
    return face


def canvas() -> Image.Image:
    return Image.new("RGB", (W, H), (0, 0, 0))


def crush(im: Image.Image, threshold: int = 3) -> Image.Image:
    arr = np.asarray(im).astype(np.int16)
    dark = arr.max(axis=2) <= threshold
    arr[dark] = 0
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def paste_rgba(base: Image.Image, layer: Image.Image) -> Image.Image:
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def orb(cx: int, cy: int, radius: int, color: tuple[int, int, int], peak: int) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = layer.load()
    x0, x1 = max(0, cx - radius), min(W, cx + radius)
    y0, y1 = max(0, cy - radius), min(H, cy + radius)
    for y in range(y0, y1):
        dy = y - cy
        for x in range(x0, x1):
            d = math.hypot(x - cx, dy) / radius
            if d >= 1:
                continue
            a = int(peak * (1 - d) ** 2.2)
            if a > 0:
                px[x, y] = (*color, a)
    return layer


def petal_sprite(length: int, width: int, color: tuple[int, int, int], alpha: int) -> Image.Image:
    im = Image.new("RGBA", (length + 8, width + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (*color, alpha)
    d.polygon(
        [(length * 0.5, 2), (length - 2, width * 0.62), (length * 0.5, width - 2), (2, width * 0.62)],
        fill=fill,
    )
    d.ellipse((length * 0.18, 2, length * 0.82, width * 0.72), fill=fill)
    return im


def draw_tracked(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], face, fill, tracking: int) -> None:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=face, fill=fill, anchor="lt")
        box = face.getbbox(ch)
        x += (box[2] - box[0]) + tracking


def tracked_width(text: str, face, tracking: int) -> int:
    width = 0
    for i, ch in enumerate(text):
        box = face.getbbox(ch)
        width += box[2] - box[0]
        if i < len(text) - 1:
            width += tracking
    return width


def center_tracked(draw, text, y, face, fill, tracking) -> None:
    x = (W - tracked_width(text, face, tracking)) // 2
    draw_tracked(draw, text, (x, y), face, fill, tracking)


def line(draw, y, width, color, stroke=2) -> None:
    x0 = (W - width) // 2
    draw.line((x0, y, x0 + width, y), fill=color, width=stroke)


def rings(cx: int, cy: int, radius: int = 78) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gap = 36
    for shift in (-gap, gap):
        d.ellipse(
            (cx - radius + shift, cy - radius, cx + radius + shift, cy + radius),
            outline=(*GOLD, 255),
            width=6,
        )
    diamond = [(cx, cy - 16), (cx + 10, cy), (cx, cy + 16), (cx - 10, cy)]
    d.polygon(diamond, fill=(*IVORY, 255))
    return layer


def given(full: str) -> str:
    return full[1:] if len(full) > 2 else full


def load_cast() -> list[dict]:
    data = json.loads(CAST_PATH.read_text(encoding="utf-8"))
    return data["couples"]


def save(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    crush(im).save(path, "PNG", optimize=True)


def render_initials(couple: dict) -> Image.Image:
    im = canvas()
    im = paste_rgba(im, orb(360, 700, 420, ORANGE, 52))
    im = paste_rgba(im, rings(W // 2, 1210))
    rng = np.random.default_rng(int(couple["id"]))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for _ in range(7):
        length = int(rng.integers(36, 78))
        width = int(rng.integers(18, 36))
        sprite = petal_sprite(length, width, BLUSH, int(rng.integers(140, 210)))
        sprite = sprite.rotate(float(rng.uniform(0, 180)), expand=True, resample=Image.BICUBIC)
        x = int(rng.integers(80, W - 160))
        y = int(rng.integers(180, 560))
        if 300 < x < 780 and 620 < y < 1100:
            x = 80 if x < W // 2 else W - 180
        layer.alpha_composite(sprite, (x, y))
    im = paste_rgba(im, layer)
    d = ImageDraw.Draw(im)
    name = font(TITLE_KO, 168)
    mark = font(LATIN, 28, 550)
    center_tracked(d, "THEREBORN", 560, mark, GOLD, 12)
    line(d, 620, 180, GOLD, 2)
    d.text((W // 2, 810), given(couple["groom"]), font=name, fill=IVORY, anchor="mm")
    d.text((W // 2, 1000), given(couple["bride"]), font=name, fill=IVORY, anchor="mm")
    return im


def render_step(title: str, index: int, couple: dict) -> Image.Image:
    im = canvas()
    im = paste_rgba(im, orb(W // 2, 860, 360, ORANGE, 36))
    d = ImageDraw.Draw(im)
    label = font(SANS_KO, 32, 500)
    num = font(LATIN, 32, 550)
    title_font = font(TITLE_KO, 120)
    names = font(BODY_KO, 46)
    center_tracked(d, "식순", 700, label, GOLD, 18)
    line(d, 770, 120, GOLD, 2)
    d.text((W // 2, 980), title, font=title_font, fill=IVORY, anchor="mm")
    pair = f"{couple['groom']}  ·  {couple['bride']}"
    d.text((W // 2, 1160), pair, font=names, fill=GOLD, anchor="mm")
    d.text((W // 2, 1260), f"{index}  /  3", font=num, fill=GOLD_DIM, anchor="mm")
    return im


def petal_frame(i: int, count: int = 24) -> Image.Image:
    im = canvas()
    rng = np.random.default_rng(11)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for n in range(16):
        length = int(rng.integers(28, 90))
        width = max(14, length // 2)
        sprite = petal_sprite(length, width, BLUSH if n % 3 else IVORY, int(rng.integers(120, 220)))
        phase = float(rng.uniform(0, math.tau))
        speed = float(rng.uniform(90, 220))
        x0 = int(rng.integers(40, W - 80))
        y0 = int(rng.integers(0, H))
        drift = int(28 * math.sin(phase + i / count * math.tau))
        y = int((y0 + i / count * speed * 8) % (H + 200) - 100)
        x = max(0, min(W - sprite.size[0], x0 + drift))
        turned = sprite.rotate(phase * 57 + i * 6, expand=True, resample=Image.BICUBIC)
        layer.alpha_composite(turned, (x, y))
    for n, (cx, cy, rad, peak) in enumerate(
        ((220, 480, 260, 48), (820, 1100, 340, 40), (540, 1560, 220, 34))
    ):
        oy = int((cy + i * (18 + n * 7)) % (H + 400) - 200)
        im = paste_rgba(im, orb(cx, oy, rad, ORANGE, peak))
    return paste_rgba(im, layer)


def render_idle() -> Image.Image:
    im = canvas()
    d = ImageDraw.Draw(im)
    center_tracked(d, "THEREBORN", H // 2 - 20, font(LATIN, 28, 550), GOLD_DIM, 14)
    return im


def render_halls(couples: list[dict]) -> Image.Image:
    by_id = {c["id"]: c for c in couples}
    im = canvas()
    d = ImageDraw.Draw(im)
    center_tracked(d, "THEREBORN", 280, font(LATIN, 28, 550), GOLD, 12)
    d.text((W // 2, 390), "오늘 예식", font=font(TITLE_KO, 72), fill=IVORY, anchor="mm")
    line(d, 460, 160, GOLD, 2)
    y = 560
    for row in SAMPLE_HALLS:
        couple = by_id[row["id"]]
        d.text((160, y), row["hall"], font=font(SANS_KO, 32, 500), fill=GOLD, anchor="lt")
        d.text((160, y + 66), row["time"], font=font(SANS_KO, 42, 500), fill=GOLD_DIM, anchor="lt")
        d.text((160, y + 150), f"{couple['groom']}  ·  {couple['bride']}", font=font(TITLE_KO, 56), fill=IVORY, anchor="lt")
        y += 420
    return im


def render_lobby_couple(couple: dict, when: str) -> Image.Image:
    im = canvas()
    im = paste_rgba(im, orb(W // 2, 780, 300, ORANGE, 28))
    d = ImageDraw.Draw(im)
    center_tracked(d, "THEREBORN", 520, font(LATIN, 28, 550), GOLD, 12)
    line(d, 590, 140, GOLD, 2)
    d.text((W // 2, 760), couple["groom"], font=font(TITLE_KO, 96), fill=IVORY, anchor="mm")
    d.text((W // 2, 910), couple["bride"], font=font(TITLE_KO, 96), fill=IVORY, anchor="mm")
    d.text((W // 2, 1090), when, font=font(SANS_KO, 36, 500), fill=GOLD, anchor="mm")
    return im


def render_frame() -> Image.Image:
    im = canvas()
    d = ImageDraw.Draw(im)
    inset, arm = 96, 150
    stroke = 4
    corners = [
        (inset, inset, 1, 1),
        (W - inset, inset, -1, 1),
        (inset, H - inset, 1, -1),
        (W - inset, H - inset, -1, -1),
    ]
    for x, y, sx, sy in corners:
        d.line((x, y, x + arm * sx, y), fill=GOLD, width=stroke)
        d.line((x, y, x, y + arm * sy), fill=GOLD, width=stroke)
    cx, cy = W // 2, 250
    d.arc((cx - 70, cy - 20, cx + 70, cy + 80), 200, 340, fill=GOLD, width=4)
    d.polygon([(cx, cy - 36), (cx + 10, cy - 8), (cx, cy), (cx - 10, cy - 8)], fill=IVORY)
    d.text((W // 2, H - 180), "오늘, 여기서", font=font(TITLE_KO, 44), fill=IVORY, anchor="mm")
    return im


def render_package() -> Image.Image:
    im = canvas()
    d = ImageDraw.Draw(im)
    # Upper half stays black so a physical album behind the glass remains visible.
    y = 1180
    center_tracked(d, "웨딩 패키지", y, font(SANS_KO, 28, 500), GOLD, 8)
    d.text((W // 2, y + 90), "앨범  ·  원본  ·  액자", font=font(TITLE_KO, 50), fill=IVORY, anchor="mm")
    line(d, y + 160, 120, GOLD, 2)
    d.text((W // 2, y + 230), "가격은 상담 시 안내", font=font(SANS_KO, 32, 500), fill=GOLD, anchor="mm")
    d.text((W // 2, y + 300), "제휴  ·  드레스 피팅", font=font(BODY_KO, 38), fill=IVORY, anchor="mm")
    return im


def measure(path: Path) -> dict:
    im = Image.open(path)
    arr = np.asarray(im)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise SystemExit(f"{path} is not RGB")
    mx = arr.max(axis=2)
    dirty = int(((mx > 0) & (mx <= 3)).sum())
    black = float((mx == 0).mean())
    return {
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "size": list(im.size),
        "mode": im.mode,
        "black_ratio": round(black, 4),
        "dirty_near_black": dirty,
    }


def simulate(overlay: Path, background: Path, out: Path) -> None:
    bg = Image.open(background).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    ov = np.asarray(Image.open(overlay).convert("RGB")).astype(np.float32)
    base = np.asarray(bg).astype(np.float32)
    Image.fromarray(np.clip(base + ov, 0, 255).astype(np.uint8)).save(out, "JPEG", quality=90)


def main() -> None:
    couples = load_cast()
    by_id = {c["id"]: c for c in couples}
    reports = []

    for couple in couples:
        path = ROOT / "ceremony" / "initials" / f"{couple['id']}.png"
        save(render_initials(couple), path)
        reports.append(measure(path))

    steps = [("신랑 입장", 1), ("신부 입장", 2), ("혼인서약", 3)]
    featured = by_id["01"]
    for title, index in steps:
        path = ROOT / "ceremony" / "steps" / f"0{index}.png"
        save(render_step(title, index, featured), path)
        reports.append(measure(path))

    for i in range(24):
        path = ROOT / "ceremony" / "petals" / f"{i:02d}.png"
        save(petal_frame(i), path)
    reports.append(measure(ROOT / "ceremony" / "petals" / "00.png"))
    reports.append(measure(ROOT / "ceremony" / "petals" / "12.png"))

    idle = ROOT / "lobby" / "idle.png"
    save(render_idle(), idle)
    reports.append(measure(idle))

    halls = ROOT / "lobby" / "halls.png"
    save(render_halls(couples), halls)
    reports.append(measure(halls))

    for couple in couples:
        path = ROOT / "lobby" / f"{couple['id']}.png"
        save(render_lobby_couple(couple, "일정 미정"), path)
        reports.append(measure(path))

    frame = ROOT / "photozone" / "frame.png"
    package = ROOT / "consult" / "package.png"
    save(render_frame(), frame)
    save(render_package(), package)
    reports.append(measure(frame))
    reports.append(measure(package))

    preview = ROOT / "preview"
    preview.mkdir(exist_ok=True)
    hall_photo = COUPLES / featured["folder"] / "couple-01-classic-hall.jpg"
    dark_photo = COUPLES / by_id["06"]["folder"] / "couple-06-candle-reception.jpg"
    simulate(ROOT / "ceremony" / "initials" / "01.png", hall_photo, preview / "initials-on-bright-hall.jpg")
    simulate(ROOT / "ceremony" / "initials" / "01.png", dark_photo, preview / "initials-on-dark-reception.jpg")
    simulate(ROOT / "ceremony" / "steps" / "03.png", dark_photo, preview / "vows-on-dark-reception.jpg")

    pkg = np.asarray(Image.open(package))
    upper = pkg[:1000]
    if int(upper.max()) != 0:
        raise SystemExit("package overlay leaked into the upper half")
    frame_arr = np.asarray(Image.open(frame))
    center = frame_arr[700:1200, 300:780]
    if int(center.max()) != 0:
        raise SystemExit("photo frame center is not empty")

    fails = [r for r in reports if r["dirty_near_black"] or r["size"] != [W, H] or r["black_ratio"] < 0.55]
    manifest = {
        "canvas": {"pixels": [W, H], "background": "#000000", "mode": "RGB"},
        "install": "PNG files only. #000000 is the transparent pixel. Preview JPGs are simulations.",
        "schedule": "Single-hall per floor (1차 기준). 12:00 / 14:00 are sample time slots, not a live booking feed.",
        "names": "Fictional sample couples. Ceremony type uses given names. Lobby type uses full names.",
        "steps_shown": ["신랑 입장", "신부 입장", "혼인서약"],
        "removed": ["Congratulatory guestbook messages"],
        "not_built": [
            "Live AR mirror",
            "Proximity sensor",
            "Real package prices",
        ],
        "checks": reports,
        "failed_checks": fails,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if fails:
        raise SystemExit(f"{len(fails)} frames failed the black-pixel check")
    print(f"frames_checked {len(reports)} failed 0")


if __name__ == "__main__":
    main()
