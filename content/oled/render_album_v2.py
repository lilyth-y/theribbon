"""Upper-panel album films for the 55-inch OLED.

The lower timetable is a separate display, so these films are full-frame
1080x1920 and do not burn in ceremony steps. Each couple uses one template.
Motion is a continuous function of time: no looping overlays and no position
wraps, which is what made the previous 24fps films sit still and then jump.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"c:\startingup\theribbon")
COUPLES = ROOT / "content" / "couples"
CAST_PATH = COUPLES / "cast.json"
FONTS = ROOT / "content" / "oled" / "fonts"
OUT = ROOT / "content" / "videos"
BGM = Path(r"c:\startingup\MBOX_Upproject\AEP\premium\bgm\wedding-march-bossa.mp3")

W, H = 1080, 1920
FPS = 30
INTRO, HOLD, TRANS, OUTRO = 2.4, 4.4, 0.9, 1.8

TEMPLATES: Dict[str, Tuple[str, str]] = {
    "01": ("editorial", "풀블리드"),
    "02": ("gold_frame", "골드 프레임"),
    "03": ("carousel", "캐러셀"),
    "04": ("light_sweep", "라이트 스윕"),
    "05": ("stack", "카드 스택"),
    "06": ("parallax", "시차"),
    "07": ("rise", "상승"),
    "08": ("zoom", "줌 푸시"),
    "09": ("pair", "위아래"),
    "10": ("orbit", "오빗"),
}


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def load_bgr(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"unreadable image: {path}")
    return img


def cover_base(photo: np.ndarray, overscan: float = 1.14) -> np.ndarray:
    h, w = photo.shape[:2]
    scale = max(W / float(w), H / float(h)) * overscan
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    return cv2.resize(photo, (nw, nh), interpolation=cv2.INTER_LANCZOS4)


def framed_card(photo: np.ndarray, max_w: int, max_h: int, pad: int = 18) -> np.ndarray:
    h, w = photo.shape[:2]
    scale = min(max_w / float(w), max_h / float(h))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    card = cv2.resize(photo, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.full((nh + pad * 2, nw + pad * 2, 3), (244, 240, 232), dtype=np.uint8)
    canvas[pad : pad + nh, pad : pad + nw] = card
    cv2.rectangle(canvas, (8, 8), (canvas.shape[1] - 9, canvas.shape[0] - 9), (196, 168, 116), 2)
    return canvas


def blit_cover(base: np.ndarray, zoom: float, cx: float, cy: float) -> np.ndarray:
    """Sub-pixel crop. zoom is relative to a cover of the canvas, 1.0 fills the frame."""
    bh, bw = base.shape[:2]
    view_w = W / max(0.5, zoom)
    view_h = H / max(0.5, zoom)
    # base already includes overscan, so zoom 1 maps to the full canvas, not the whole base.
    cover = max(W / float(bw) * 1.14, H / float(bh) * 1.14)
    src_w = view_w / cover
    src_h = view_h / cover
    x0 = cx * bw - src_w * 0.5
    y0 = cy * bh - src_h * 0.5
    x0 = min(max(0.0, x0), max(0.0, bw - src_w))
    y0 = min(max(0.0, y0), max(0.0, bh - src_h))
    dest_to_src = np.float32([[src_w / W, 0, x0], [0, src_h / H, y0]])
    return cv2.warpAffine(
        base,
        dest_to_src,
        (W, H),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )


def place_card(canvas: np.ndarray, card: np.ndarray, cx: float, cy: float, scale: float, yaw_deg: float = 0.0, opacity: float = 1.0) -> None:
    if opacity <= 0.01 or scale <= 0.01:
        return
    fh, fw = card.shape[:2]
    sw, sh = fw * scale, fh * scale
    yaw = math.radians(yaw_deg)
    squeeze = math.sin(yaw)
    left_h = sh * (1.0 - 0.22 * max(0.0, squeeze))
    right_h = sh * (1.0 - 0.22 * max(0.0, -squeeze))
    dx = cx * W - sw * 0.5 + math.sin(yaw) * sw * 0.08
    dy = cy * H - sh * 0.5
    src = np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]])
    dst = np.float32(
        [
            [dx, dy + (sh - left_h) * 0.5],
            [dx + sw, dy + (sh - right_h) * 0.5],
            [dx + sw, dy + (sh + right_h) * 0.5],
            [dx, dy + (sh + left_h) * 0.5],
        ]
    )
    x0 = max(0, int(math.floor(float(dst[:, 0].min()))) - 2)
    y0 = max(0, int(math.floor(float(dst[:, 1].min()))) - 2)
    x1 = min(W, int(math.ceil(float(dst[:, 0].max()))) + 2)
    y1 = min(H, int(math.ceil(float(dst[:, 1].max()))) + 2)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    local = dst - np.float32([[x0, y0]])
    patch = cv2.warpPerspective(card, cv2.getPerspectiveTransform(src, local), (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(np.round(local)), 255, lineType=cv2.LINE_AA)
    roi = canvas[y0:y1, x0:x1]
    if opacity >= 0.99:
        cv2.copyTo(patch, mask, roi)
    else:
        blended = cv2.addWeighted(roi, 1.0 - opacity, patch, opacity, 0)
        cv2.copyTo(blended, mask, roi)


def drift(abs_t: float, speed: float, phase: float, amount: float) -> float:
    return math.sin(abs_t * speed + phase) * amount


class Album:
    def __init__(self, photos: List[np.ndarray]):
        self.bases = [cover_base(p) for p in photos]
        self.hero = [framed_card(p, int(W * 0.86), int(H * 0.72)) for p in photos]
        self.mid = [framed_card(p, int(W * 0.62), int(H * 0.48), pad=12) for p in photos]
        self.mini = [framed_card(p, int(W * 0.38), int(H * 0.30), pad=10) for p in photos]
        self.n = len(photos)

    def render(self, family: str, index: int, abs_t: float, local_t: float) -> np.ndarray:
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        i = index % self.n
        if family == "editorial":
            return blit_cover(self.bases[i], 1.0 + 0.045 * (0.5 + 0.5 * math.sin(abs_t * 0.22)), 0.50 + drift(abs_t, 0.18, 0.4, 0.015), 0.50 + drift(abs_t, 0.15, 1.1, 0.012))
        if family == "zoom":
            z = 1.02 + 0.06 * ease(local_t)
            return blit_cover(self.bases[i], z, 0.50 + drift(abs_t, 0.16, 0.2, 0.01), 0.50 + drift(abs_t, 0.14, 0.7, 0.01))
        if family == "gold_frame":
            place_card(canvas, self.hero[i], 0.50 + drift(abs_t, 0.20, 0.0, 0.012), 0.52, 0.96 + drift(abs_t, 0.25, 0.6, 0.015), drift(abs_t, 0.35, 0.2, 3.2))
            return canvas
        if family == "carousel":
            for off, phase in ((-1, -0.9), (1, 0.9)):
                j = (i + off) % self.n
                ang = abs_t * 0.28 + phase
                place_card(canvas, self.mid[j], 0.50 + math.sin(ang) * 0.30, 0.56, 0.72, math.degrees(math.cos(ang)) * 0.22, opacity=0.42)
            place_card(canvas, self.hero[i], 0.50, 0.48, 0.90 + drift(abs_t, 0.3, 0.0, 0.012), drift(abs_t, 0.4, 0.5, 2.4))
            return canvas
        if family == "light_sweep":
            place_card(canvas, self.hero[i], 0.50, 0.50, 0.94, drift(abs_t, 0.3, 0.4, 2.0))
            # Band travels once per shot and is fully off-frame at both ends.
            band_x = int((-0.25 + 1.5 * ease(local_t)) * W)
            x0, x1 = max(0, band_x - 70), min(W, band_x + 70)
            if x1 > x0:
                roi = canvas[:, x0:x1]
                lit = np.clip(roi.astype(np.int16) + np.int16([18, 28, 36]), 0, 255).astype(np.uint8)
                mask = (roi.max(axis=2) > 12).astype(np.uint8) * 255
                cv2.copyTo(lit, mask, roi)
            return canvas
        if family == "stack":
            for k, off in enumerate((-2, -1)):
                j = (i + off) % self.n
                place_card(canvas, self.mid[j], 0.50 + off * 0.04, 0.50 + abs(off) * 0.015, 0.86 - abs(off) * 0.04, off * -4.0, opacity=0.35)
            place_card(canvas, self.hero[i], 0.50 + drift(abs_t, 0.22, 0.3, 0.01), 0.50, 0.92, drift(abs_t, 0.33, 0.8, 2.2))
            return canvas
        if family == "parallax":
            back = blit_cover(self.bases[(i + 1) % self.n], 1.08, 0.50 + drift(abs_t, 0.12, 1.0, 0.02), 0.50)
            back = (back.astype(np.float32) * 0.38).astype(np.uint8)
            canvas[:] = back
            place_card(canvas, self.hero[i], 0.50 + drift(abs_t, 0.20, 0.0, 0.02), 0.52, 0.78, drift(abs_t, 0.28, 0.5, 2.5))
            return canvas
        if family == "rise":
            cy = 0.50 + drift(abs_t, 0.24, 0.6, 0.012)
            place_card(canvas, self.hero[i], 0.50, cy, 0.94 + drift(abs_t, 0.2, 0.1, 0.012), drift(abs_t, 0.3, 0.9, 1.8))
            return canvas
        if family == "pair":
            top = blit_cover(self.bases[i], 1.05, 0.50 + drift(abs_t, 0.16, 0.2, 0.012), 0.42)
            bot = blit_cover(self.bases[(i + 1) % self.n], 1.05, 0.50 + drift(abs_t, 0.16, 2.0, 0.012), 0.58)
            canvas[: H // 2] = top[: H // 2]
            canvas[H // 2 + 8 :] = bot[H // 2 + 8 :]
            return canvas
        # orbit
        for k in range(3):
            phase = k * 2.094
            place_card(
                canvas,
                self.mini[(i + k + 1) % self.n],
                0.50 + math.sin(abs_t * 0.45 + phase) * 0.28,
                0.50 + math.cos(abs_t * 0.38 + phase) * 0.22,
                0.55,
                drift(abs_t, 0.5, phase, 8.0),
                opacity=0.55,
            )
        place_card(canvas, self.hero[i], 0.50, 0.50, 0.72 + drift(abs_t, 0.25, 0.0, 0.01), drift(abs_t, 0.32, 0.4, 2.0))
        return canvas


def title_layer(groom: str, bride: str) -> Tuple[np.ndarray, np.ndarray]:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    gold = (232, 206, 164, 255)
    ivory = (255, 248, 240, 255)
    draw.text((W // 2, 760), "THEREBORN", font=ImageFont.truetype(str(FONTS / "Cinzel.ttf"), 36), fill=gold, anchor="mm")
    draw.text((W // 2, 860), f"{groom}  ·  {bride}", font=ImageFont.truetype(str(FONTS / "GowunBatang-Bold.ttf"), 72), fill=ivory, anchor="mm")
    arr = np.asarray(layer)
    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    mask = (arr[:, :, 3] > 16).astype(np.uint8) * 255
    return bgr, mask


def timeline(n: int) -> List[Tuple[str, int, float, float]]:
    events: List[Tuple[str, int, float, float]] = []
    t = 0.0
    events.append(("intro", 0, t, INTRO))
    t += INTRO
    for i in range(n):
        events.append(("hold", i, t, HOLD))
        t += HOLD
        if i < n - 1:
            events.append(("trans", i, t, TRANS))
            t += TRANS
    events.append(("outro", n - 1, t, OUTRO))
    return events


def compose(album: Album, family: str, kind: str, index: int, abs_t: float, local_t: float, title: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    if kind == "trans":
        a = album.render(family, index, abs_t, 1.0)
        b = album.render(family, index + 1, abs_t, 0.0)
        alpha = ease(local_t)
        return cv2.addWeighted(a, 1.0 - alpha, b, alpha, 0)
    frame = album.render(family, index, abs_t, local_t if kind == "hold" else (0.0 if kind == "intro" else 1.0))
    if kind == "intro":
        fade = ease(min(1.0, local_t / 0.45))
        frame = cv2.convertScaleAbs(frame, alpha=0.35 + 0.65 * fade)
        if local_t < 0.82:
            text_a = ease(min(1.0, local_t / 0.25)) * (1.0 - ease(max(0.0, (local_t - 0.62) / 0.20)))
            if text_a > 0.02:
                bgr, mask = title
                stamped = cv2.addWeighted(frame, 1.0, bgr, text_a, 0)
                cv2.copyTo(stamped, mask, frame)
    elif kind == "outro":
        frame = cv2.convertScaleAbs(frame, alpha=1.0 - ease(local_t))
    return frame


def motion_report(album: Album, family: str) -> dict:
    """Hold-window smoothness. A jump is a frame that moves much faster than the window median."""
    frames = []
    abs0 = 12.0
    for f in range(int(2.4 * FPS)):
        frames.append(album.render(family, 0, abs0 + f / FPS, f / (2.4 * FPS)))
    diffs = []
    prev = cv2.resize(cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY), (180, 320))
    for frame in frames[1:]:
        g = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (180, 320))
        diffs.append(float(np.mean(cv2.absdiff(prev, g))))
        prev = g
    arr = np.array(diffs)
    med = float(np.median(arr))
    jumps = int(np.sum(arr > max(1.2, med * 3.0)))
    return {"family": family, "median": round(med, 3), "max": round(float(arr.max()), 3), "jumps": jumps}


def render_couple(couple: dict) -> dict:
    started = time.time()
    cid = couple["id"]
    family, label = TEMPLATES[cid]
    photos = [load_bgr(COUPLES / rel) for rel in couple["shots"]]
    album = Album(photos)
    events = timeline(len(photos))
    total = events[-1][2] + events[-1][3]
    out_mp4 = OUT / f"{couple['folder']}.mp4"
    OUT.mkdir(parents=True, exist_ok=True)
    title = title_layer(couple["groom"], couple["bride"])

    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
    ]
    if BGM.is_file():
        cmd += ["-stream_loop", "-1", "-i", str(BGM), "-map", "0:v:0", "-map", "1:a:0"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-g", str(FPS), "-movflags", "+faststart",
    ]
    if BGM.is_file():
        fade_st = max(0.0, total - 1.4)
        cmd += ["-c:a", "aac", "-b:a", "160k", "-af", f"volume=0.35,afade=t=in:st=0:d=0.8,afade=t=out:st={fade_st:.2f}:d=1.4", "-shortest"]
    else:
        cmd += ["-an"]
    cmd.append(str(out_mp4))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    frame_i = 0
    try:
        for kind, index, start, dur in events:
            count = int(round(dur * FPS))
            for f in range(count):
                abs_t = (start + f / FPS)
                local_t = f / max(1, count - 1)
                frame = compose(album, family, kind, index, abs_t, local_t, title)
                proc.stdin.write(frame.tobytes())
                frame_i += 1
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed for {cid}: {err[-1500:]}")

    folder_copy = COUPLES / couple["folder"] / f"couple-{cid}-mbox-2m.mp4"
    if folder_copy.parent.is_dir():
        shutil.copy2(out_mp4, folder_copy)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=avg_frame_rate,width,height",
        "-of", "json", str(out_mp4),
    ], text=True))
    return {
        "id": cid,
        "groom": couple["groom"],
        "bride": couple["bride"],
        "template": family,
        "template_ko": label,
        "file": str(out_mp4.relative_to(ROOT)).replace("\\", "/"),
        "frames": frame_i,
        "duration_sec": round(float(probe["format"]["duration"]), 2),
        "size_mb": round(int(probe["format"]["size"]) / (1024 * 1024), 2),
        "render_sec": round(time.time() - started, 1),
        "fps": FPS,
        "ceremony_in_video": False,
    }


def diagnose() -> None:
    cast = json.loads(CAST_PATH.read_text(encoding="utf-8"))
    couple = cast["couples"][0]
    photos = [load_bgr(COUPLES / rel) for rel in couple["shots"][:4]]
    album = Album(photos)
    failed = []
    for family, _label in dict.fromkeys(TEMPLATES.values()):
        report = motion_report(album, family)
        print(f"[motion] {report}", flush=True)
        if report["jumps"] > 0 or report["max"] > 8.0:
            failed.append(report)
    if failed:
        raise SystemExit(f"choppy templates: {failed}")
    print("[motion] all templates within the hold-jump limit", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--couples", nargs="*", default=[])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args()
    if args.diagnose:
        diagnose()
        return
    cast = json.loads(CAST_PATH.read_text(encoding="utf-8"))
    couples = cast["couples"]
    if args.couples:
        wanted = {c.zfill(2) for c in args.couples}
        couples = [c for c in couples if c["id"] in wanted]
    t0 = time.time()
    rows: List[dict] = []
    if len(couples) == 1 or args.workers <= 1:
        for couple in couples:
            row = render_couple(couple)
            rows.append(row)
            print(f"[OK] {row['id']} {row['template_ko']} {row['duration_sec']}s {row['size_mb']}MB in {row['render_sec']}s", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(render_couple, c): c for c in couples}
            for fut in as_completed(futs):
                row = fut.result()
                rows.append(row)
                print(f"[OK] {row['id']} {row['template_ko']} {row['duration_sec']}s {row['size_mb']}MB in {row['render_sec']}s", flush=True)
    rows.sort(key=lambda r: r["id"])
    manifest = {
        "resolution": [W, H],
        "fps": FPS,
        "oled_canvas": "#000000",
        "layout": "full_frame_upper_oled",
        "ceremony_in_video": False,
        "note": "Lower timetable is a separate display and is not burned into these films. One template per couple.",
        "videos": rows,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== {len(rows)} films in {manifest['elapsed_sec']}s ===", flush=True)


if __name__ == "__main__":
    main()
