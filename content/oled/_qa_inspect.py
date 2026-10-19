"""Extract visual QA contact sheets and measure OLED black levels across all 10 couple videos."""

from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"c:\startingup\theribbon")
VIDEOS_DIR = ROOT / "content" / "videos"
QA_DIR = VIDEOS_DIR / "preview_qa"
FONTS_DIR = ROOT / "content" / "oled" / "fonts"
SANS_KO = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"

QA_DIR.mkdir(parents=True, exist_ok=True)

# 1. Extract 6 key moments from Couple 01 (showing different templates & lit ceremony steps)
c01 = VIDEOS_DIR / "01-이서준-김하은.mp4"
cap = cv2.VideoCapture(str(c01))
fps = cap.get(cv2.CAP_PROP_FPS) or 24.0

moments = [
    (8.0, "01_s01_falling_cube_step1", "Shot 01 · Falling Cube (식순 01 점등)"),
    (34.0, "02_s03_carousel_3d_step2", "Shot 03 · 3D Carousel (식순 02 점등)"),
    (46.0, "03_s04_light_sweep_step3", "Shot 04 · Light Sweep & Crystal (식순 03 점등)"),
    (60.5, "04_broll_rings_step4", "B-Roll · Wedding Rings Bridge (식순 04 점등)"),
    (68.0, "05_s06_accumulate_step4", "Shot 06 · 3D Accumulate Cards (식순 04 점등)"),
    (114.0, "06_s10_finale_cube_step6", "Shot 10 · Finale Cube (식순 06 점등)"),
]

tiles = []
for sec, slug, label in moments:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
    ok, frm = cap.read()
    if not ok:
        continue
    out_p = QA_DIR / f"{slug}.jpg"
    cv2.imwrite(str(out_p), frm, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
    tiles.append((rgb, f"{sec:04.1f}s  |  {label}"))
cap.release()

# Build a 3x2 storyboard sheet of Couple 01 across its 120s timeline
tw, th = 540, 960
sheet = Image.new("RGB", (tw * 3, th * 2), (10, 10, 10))
font = ImageFont.truetype(SANS_KO, 22)
font.set_variation_by_axes([600])
for idx, (rgb, label) in enumerate(tiles):
    im = Image.fromarray(rgb).resize((tw, th), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, tw, 38), fill=(0, 0, 0))
    d.text((14, 19), label, font=font, fill=(232, 206, 164), anchor="lm")
    gx, gy = (idx % 3) * tw, (idx // 3) * th
    sheet.paste(im, (gx, gy))
sheet.save(QA_DIR / "couple_01_timeline_sheet.jpg", "JPEG", quality=92)

# 2. Extract 1 frame per couple across all 10 videos (at different template moments) + measure black ratio
cast = json.loads((ROOT / "content" / "couples" / "cast.json").read_text(encoding="utf-8"))
sample_secs = [8.0, 20.0, 34.0, 46.0, 56.0, 68.0, 80.0, 92.0, 104.0, 114.0]
grid_10 = Image.new("RGB", (tw * 5, th * 2), (10, 10, 10))
stats = []

for i, c in enumerate(cast["couples"]):
    vp = VIDEOS_DIR / f"{c['folder']}.mp4"
    vcap = cv2.VideoCapture(str(vp))
    vfps = vcap.get(cv2.CAP_PROP_FPS) or 24.0
    fcount = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
    sec = sample_secs[i]
    vcap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * vfps))
    ok, frm = vcap.read()
    vcap.release()
    if not ok:
        continue
    # Measure OLED black ratio in bottom ceremony panel & overall canvas
    mx = frm.max(axis=2)
    bot_mx = frm[1340:, :].max(axis=2)
    overall_black = float((mx <= 8).mean())
    bot_black = float((bot_mx <= 8).mean())
    stats.append(
        {
            "id": c["id"],
            "couple": f"{c['groom']}·{c['bride']}",
            "frames": fcount,
            "duration_sec": round(fcount / vfps, 2),
            "sample_sec": sec,
            "overall_black_ratio": round(overall_black, 3),
            "bottom_panel_black_ratio": round(bot_black, 3),
        }
    )
    rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb).resize((tw, th), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, tw, 38), fill=(0, 0, 0))
    d.text((14, 19), f"{c['id']} {c['groom']}·{c['bride']} ({sec:.0f}s)", font=font, fill=(255, 248, 240), anchor="lm")
    gx, gy = (i % 5) * tw, (i // 5) * th
    grid_10.paste(im, (gx, gy))

grid_10.save(QA_DIR / "all_10_couples_sheet.jpg", "JPEG", quality=92)
(QA_DIR / "qa_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
print("QA sheets and stats generated:", len(stats))
