"""30-second OLED slots from the existing 3D photo engines.

Full 1080x1920, solid black canvas, no ceremony steps and no name badge.
The day's five are the spatial families. The rest of the same catalog is
rendered so the page can still show it.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_couple_videos as engines
from renderer.ue3d_depth_renderer import UE3DDepthRenderer

ROOT = Path(r"c:\startingup\theribbon")
COUPLES = ROOT / "content" / "couples"
OUT = ROOT / "content" / "videos" / "depth"
CAST = json.loads((COUPLES / "cast.json").read_text(encoding="utf-8"))

W, H, FPS = 1080, 1920, 30
HOLD_SEC = 5.0
TRANS_SEC = 1.25
PHOTOS = 5

# couple id, family, Korean label, whether the day timetable uses it
PLAN = [
    ("10", "falling_cube", "폴링 큐브", True),
    ("03", "carousel_3d", "입체 캐러셀", True),
    ("05", "accumulate_cards", "쌓이는 카드", True),
    ("06", "cube_fly", "큐브 플라이", True),
    ("02", "parallax_sphere", "패럴랙스", True),
    ("01", "page_turn", "페이지 턴", False),
    ("07", "vertical_slide", "세로 슬라이드", False),
    ("04", "light_sweep", "라이트 스윕", False),
    ("08", "cinematic_zoom", "시네마틱 줌", False),
]


def load_bgr(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read {path}")
    return image


def couple_by_id(cid: str) -> dict:
    for row in CAST["couples"]:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def cards_for(cid: str) -> list:
    couple = couple_by_id(cid)
    shots = couple["shots"][:PHOTOS]
    if len(shots) < PHOTOS:
        raise RuntimeError(f"{cid} has {len(shots)} shots")
    return [engines.PreparedCard(load_bgr(COUPLES / rel), W, H) for rel in shots]


def transition(family: str, card_a, card_b, frame_a, frame_b, progress: float, ue) -> np.ndarray:
    if family in ("falling_cube", "cube_fly"):
        return engines.render_falling_cube_transition(card_a, card_b, progress, W, H)
    if family == "page_turn":
        return ue.render_3d_page_turn_mesh_transition(frame_a, frame_b, progress)
    if family == "light_sweep":
        return ue.render_light_sweep_transition(frame_a, frame_b, progress)
    if family == "cinematic_zoom":
        return ue.render_cinematic_zoom_transition(frame_a, frame_b, progress)
    alpha = 0.5 - 0.5 * math.cos(max(0.0, min(1.0, progress)) * math.pi)
    return cv2.addWeighted(frame_a, 1.0 - alpha, frame_b, alpha, 0)


def render_film(cid: str, family: str, ue, bench: bool = False) -> Path:
    cards = cards_for(cid)
    hold_n = int(round(HOLD_SEC * FPS))
    trans_n = int(round(TRANS_SEC * FPS))
    out = OUT / f"{cid}-{family}.mp4"
    proc = None
    if not bench:
        OUT.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                "-i", "-",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(out),
            ],
            stdin=subprocess.PIPE,
        )
    started = time.time()
    written = 0
    endpoints = {}

    def hold(index: int, t: float) -> np.ndarray:
        return engines.render_oled_photo_hold(family, cards, index, t, W, H)

    def emit(frame: np.ndarray) -> None:
        nonlocal written
        if frame.shape != (H, W, 3):
            raise RuntimeError(f"bad frame {frame.shape}")
        if proc is not None:
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        written += 1

    for i in range(PHOTOS):
        limit = 30 if bench and i == 0 else hold_n
        if bench and i > 0:
            break
        for f in range(limit):
            emit(hold(i, f / float(max(1, hold_n - 1))))
        if bench:
            break
        if i < PHOTOS - 1:
            endpoints[(i, 1.0)] = hold(i, 1.0)
            endpoints[(i + 1, 0.0)] = hold(i + 1, 0.0)
            for f in range(trans_n):
                progress = (f + 1) / float(trans_n)
                emit(
                    transition(
                        family,
                        cards[i],
                        cards[i + 1],
                        endpoints[(i, 1.0)],
                        endpoints[(i + 1, 0.0)],
                        progress,
                        ue,
                    )
                )
    if proc is not None:
        proc.stdin.close()
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg failed for {out} ({code})")
    elapsed = time.time() - started
    print(f"[OK] {cid} {family} frames={written} {elapsed:.1f}s {written / max(elapsed, 0.1):.1f} fps", flush=True)
    return out


def main() -> None:
    bench = "--bench" in sys.argv
    ue = UE3DDepthRenderer(width=W, height=H)
    rows = []
    plan = PLAN[:1] if bench else PLAN
    for cid, family, label, in_day in plan:
        path = render_film(cid, family, ue, bench=bench)
        if bench:
            shot = engines.render_oled_photo_hold(family, cards_for(cid), 0, 0.45, W, H)
            preview = OUT / "_preview_falling_cube.jpg"
            OUT.mkdir(parents=True, exist_ok=True)
            cv2.imencode(".jpg", shot, [int(cv2.IMWRITE_JPEG_QUALITY), 86])[1].tofile(str(preview))
            print(f"[preview] {preview}", flush=True)
            return
        couple = couple_by_id(cid)
        rows.append(
            {
                "id": cid,
                "family": family,
                "label": label,
                "in_day": in_day,
                "groom": couple["groom"],
                "bride": couple["bride"],
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "poster": couple["file"],
            }
        )
    (OUT / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
