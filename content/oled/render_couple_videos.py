"""MBOX Wedding Ceremony Video Assembly for The Reborn (1080x1920 Portrait).

Integrates MBOX_Upproject renderer engines & template footage sources:
- Falling Cube / Cube Fly (envato-elements-CubeFantasy / ElegantCubeSlideshow / Flying_Boxes)
- 3D Carousel Orbit (drive-8_03_10_3D_carousel_3)
- 3D Accumulate Cards (mixkit-831)
- CC Page Turn 3D Mesh (mixkit-802)
- CC Light Sweep & Crystal Shell Refraction (mixkit-594)
- Cinematic Parallax Zoom-Push (mixkit-591)
- Vertical Crane Slide (drive-8_02_6_3D_vertical_slide)
- Parallax Sphere Multi-Layer (envato-elements-BeautifulMemoriesSphere)

Layout (1080x1920, solid #000000 OLED canvas):
- Top stage (1080x1340): Couple 10-photo MBOX multi-template video + template FX overlays
  + B-roll wedding clips from MBOX AEP footage (rose petals, rings, bouquet).
  Every photo of the 10 shots appears in full across the ~120s timeline.
- Bottom stage (1080x580, y=1340..1920): Ceremony order (식순) on pure #000000 background,
  synchronously lighting up the active ceremony step as the video progresses.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MBOX_ROOT = Path(r"c:\startingup\MBOX_Upproject")
if str(MBOX_ROOT) not in sys.path:
    sys.path.insert(0, str(MBOX_ROOT))

from renderer.camera_motion import ease_in_out
from renderer.ue3d_depth_renderer import UE3DDepthRenderer

THERIBBON_ROOT = Path(r"c:\startingup\theribbon")
COUPLES_ROOT = THERIBBON_ROOT / "content" / "couples"
CAST_PATH = COUPLES_ROOT / "cast.json"
FONTS_DIR = THERIBBON_ROOT / "content" / "oled" / "fonts"
OUT_ROOT = THERIBBON_ROOT / "content" / "videos"

W, H = 1080, 1920
TOP_H = 1340
BOT_H = H - TOP_H  # 580

TITLE_KO = str(FONTS_DIR / "GowunBatang-Bold.ttf")
BODY_KO = str(FONTS_DIR / "GowunBatang-Regular.ttf")
LATIN = str(FONTS_DIR / "Cinzel.ttf")
SANS_KO = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"

BGM_PATH = MBOX_ROOT / "AEP" / "premium" / "bgm" / "wedding-march-bossa.mp3"

AEP_DIR = MBOX_ROOT / "AEP"
FX_SOURCES = {
    "cube_bokeh": AEP_DIR / "envato-elements-ElegantCubeSlideshow" / "(Footage)" / "- Elegant Cube Slideshow" / "03 Other" / "Footage" / "Bokeh.mp4",
    "cube_leaks": AEP_DIR / "envato-elements-ElegantCubeSlideshow" / "(Footage)" / "- Elegant Cube Slideshow" / "03 Other" / "Footage" / "Leaks_02.mp4",
    "glass_dust": AEP_DIR / "_collected_footage" / "drive" / "8_02_9_2D_글래스슬라이드" / "Dust.mp4",
    "glass_flares": AEP_DIR / "_collected_footage" / "drive" / "8_02_9_2D_글래스슬라이드" / "Flares_1.mp4",
    "light_leaks": AEP_DIR / "_collected_footage" / "drive" / "8_03_3_2D_유리슬라이드" / "2024_04_28_Light_Leaks_01.mp4",
    "particles": AEP_DIR / "_collected_footage" / "drive" / "8_03_3_2D_유리슬라이드" / "2024_04_28_Particles_01.mp4",
}

BROLL_SOURCES = {
    "petals": AEP_DIR / "_envato_intake" / "staging" / "mixkit" / "mixkit-837" / "extracted" / "LoveVertical folder" / "(Footage)" / "mixkit-rose-petals-3237.mp4",
    "rings": AEP_DIR / "mixkit-elegant-wedding-slideshow-802" / "WeddingSlideshow folder" / "(Footage)" / "mixkit-engagement-jewelry-5218.mp4",
    "bouquet": AEP_DIR / "mixkit-elegant-wedding-slideshow-802" / "WeddingSlideshow folder" / "(Footage)" / "mixkit-bridal-bouquet-of-white-flowers-in-a-close-up-shot-18204.mp4",
}

CEREMONY_STEPS = [
    {"idx": 1, "ko": "개식사 · 촛불점화", "en": "OPENING & CANDLE LIGHTING"},
    {"idx": 2, "ko": "신랑 입장", "en": "GROOM ENTRANCE"},
    {"idx": 3, "ko": "신부 입장 · 맞절", "en": "BRIDE ENTRANCE & BOW"},
    {"idx": 4, "ko": "혼인서약 · 성혼선언", "en": "MARRIAGE VOWS & DECLARATION"},
    {"idx": 5, "ko": "축가 · 양가 인사", "en": "CELEBRATION & GREETING"},
    {"idx": 6, "ko": "행진 · 폐식", "en": "WEDDING MARCH & FINALE"},
]

# Total timeline = 4.0s Intro + 10 * 9.0s Photo holds + 9 * 1.5s Transitions + 3 * 3.5s B-roll bridges + 2.0s Finale = 120.0s
PHOTO_TEMPLATE_PLAN = [
    {"shot_idx": 0, "template_id": "envato-elements-CubeFantasy", "family": "falling_cube", "step_idx": 1, "fx": "cube_bokeh"},
    {"shot_idx": 1, "template_id": "drive-8_03_6_3D_큐브3개", "family": "cube_fly", "step_idx": 1, "fx": "particles"},
    {"shot_idx": 2, "template_id": "drive-8_03_10_3D_carousel_3", "family": "carousel_3d", "step_idx": 2, "fx": "glass_flares"},
    {"shot_idx": 3, "template_id": "mixkit-594", "family": "light_sweep", "step_idx": 3, "fx": "light_leaks"},
    {"shot_idx": 4, "template_id": "mixkit-802", "family": "page_turn", "step_idx": 3, "fx": "glass_dust"},
    {"shot_idx": 5, "template_id": "mixkit-831", "family": "accumulate_cards", "step_idx": 4, "fx": "cube_bokeh"},
    {"shot_idx": 6, "template_id": "envato-elements-BeautifulMemoriesSphere", "family": "parallax_sphere", "step_idx": 4, "fx": "cube_leaks"},
    {"shot_idx": 7, "template_id": "drive-8_02_6_3D_vertical_slide", "family": "vertical_slide", "step_idx": 5, "fx": "particles"},
    {"shot_idx": 8, "template_id": "mixkit-591", "family": "cinematic_zoom", "step_idx": 5, "fx": "glass_flares"},
    {"shot_idx": 9, "template_id": "envato-elements-ElegantCubeSlideshow", "family": "falling_cube_finale", "step_idx": 6, "fx": "cube_bokeh"},
]

BROLL_BRIDGES = {
    1: {"broll_key": "petals", "step_idx": 2},
    4: {"broll_key": "rings", "step_idx": 4},
    7: {"broll_key": "bouquet", "step_idx": 5},
}


def load_font(path: str, size: int, weight: Optional[int] = None) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            face.set_variation_by_axes([weight])
        except Exception:
            pass
    return face


class PreparedCard:
    """Pre-built white/gold-framed photo card (both full-size and mini-cube size) for fast OpenCV warping."""

    def __init__(self, raw_bgr: np.ndarray, width: int, height: int):
        self.raw = raw_bgr
        self.main = self._build_framed(raw_bgr, int(width * 0.84), int(height * 0.84), pad=10, crystal=False)
        self.crystal = self._build_framed(raw_bgr, int(width * 0.84), int(height * 0.84), pad=12, crystal=True)
        self.mini = self._build_framed(raw_bgr, int(width * 0.34), int(height * 0.34), pad=6, crystal=False)
        self.mid = self._build_framed(raw_bgr, int(width * 0.56), int(height * 0.56), pad=8, crystal=False)

    @staticmethod
    def _build_framed(photo: np.ndarray, max_w: int, max_h: int, pad: int = 10, crystal: bool = False) -> np.ndarray:
        h, w = photo.shape[:2]
        scale = min(max_w / float(max(1, w)), max_h / float(max(1, h)))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        card = cv2.resize(photo, (nw, nh), interpolation=cv2.INTER_AREA)
        framed = np.full((nh + pad * 2, nw + pad * 2, 3), (244, 240, 232), dtype=np.uint8)
        framed[pad : pad + nh, pad : pad + nw] = card
        if crystal:
            # Crystal Shell bevel highlight border
            cv2.rectangle(framed, (1, 1), (framed.shape[1] - 2, framed.shape[0] - 2), (210, 235, 255), 2)
            cv2.rectangle(framed, (pad - 1, pad - 1), (pad + nw, pad + nh), (255, 255, 255), 1)
        return framed


def warp_card_onto(
    canvas: np.ndarray,
    framed_card: np.ndarray,
    yaw_deg: float,
    pitch_deg: float,
    scale: float,
    cx_norm: float = 0.5,
    cy_norm: float = 0.5,
    opacity: float = 1.0,
) -> np.ndarray:
    """Fast single-pass perspective warp + ROI blend directly onto `canvas` (zero full-frame float arrays)."""
    if opacity <= 0.01:
        return canvas
    H, W = canvas.shape[:2]
    fh, fw = framed_card.shape[:2]
    sw = fw * scale
    sh = fh * scale

    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    left_h = sh * (1.0 - 0.32 * math.sin(yaw) if yaw > 0 else 1.0 + 0.14 * abs(math.sin(yaw)))
    right_h = sh * (1.0 + 0.14 * abs(math.sin(yaw)) if yaw > 0 else 1.0 - 0.32 * math.sin(-yaw))
    left_h = max(sh * 0.55, min(sh * 1.15, left_h))
    right_h = max(sh * 0.55, min(sh * 1.15, right_h))

    cx = cx_norm * W
    cy = cy_norm * H
    dx = cx - sw * 0.5
    dy = cy - sh * 0.5
    x_shift = math.sin(yaw) * sw * 0.20
    y_shift = math.sin(pitch) * sh * 0.16

    src = np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]])
    dst = np.float32(
        [
            [dx + x_shift, dy + (sh - left_h) * 0.5 + y_shift],
            [dx + sw - x_shift, dy + (sh - right_h) * 0.5 - y_shift],
            [dx + sw + x_shift * 0.28, dy + (sh + right_h) * 0.5 - y_shift],
            [dx - x_shift * 0.28, dy + (sh + left_h) * 0.5 + y_shift],
        ]
    )

    # Compute tight bounding box in canvas to avoid warping across empty black pixels
    x0 = max(0, int(math.floor(float(dst[:, 0].min()))) - 2)
    y0 = max(0, int(math.floor(float(dst[:, 1].min()))) - 2)
    x1 = min(W, int(math.ceil(float(dst[:, 0].max()))) + 2)
    y1 = min(H, int(math.ceil(float(dst[:, 1].max()))) + 2)
    bw, bh = x1 - x0, y1 - y0
    if bw <= 2 or bh <= 2:
        return canvas

    dst_local = dst - np.float32([[x0, y0]])
    M = cv2.getPerspectiveTransform(src, dst_local)
    patch = cv2.warpPerspective(framed_card, M, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    poly_mask = np.zeros((bh, bw), dtype=np.uint8)
    cv2.fillConvexPoly(poly_mask, np.int32(np.round(dst_local)), 255, lineType=cv2.LINE_AA)

    roi = canvas[y0:y1, x0:x1]
    if opacity >= 0.99:
        cv2.copyTo(patch, poly_mask, roi)
    else:
        blended = cv2.addWeighted(roi, 1.0 - opacity, patch, opacity, 0)
        cv2.copyTo(blended, poly_mask, roi)
    return canvas


def add_diagonal_light_sweep(canvas: np.ndarray, progress: float) -> np.ndarray:
    """Fast CC Light Sweep specular highlight across the center card area."""
    h, w = canvas.shape[:2]
    cx = int((progress * 1.4 - 0.2) * w)
    bw = 90
    x0 = max(0, cx - bw)
    x1 = min(w, cx + bw)
    if x1 <= x0:
        return canvas
    roi = canvas[:, x0:x1]
    # Only brighten non-black pixels (where the photo card actually sits)
    non_black = (roi.max(axis=2) > 16).astype(np.uint8) * 255
    glow = np.full_like(roi, (32, 46, 58), dtype=np.uint8)
    swept = cv2.add(roi, glow)
    cv2.copyTo(swept, non_black, roi)
    return canvas


_SHARED_SAMPLER_CACHE: Dict[str, List[np.ndarray]] = {}


class ClipSampler:
    """Pre-loads and caches pre-cleaned FX & B-roll frames across couple renders inside a worker."""

    def __init__(self, target_w: int, target_h: int, fps: int = 24):
        self.w = target_w
        self.h = target_h
        self.fps = fps

    def get_frame(self, path: Path, frame_idx: int, max_seconds: float = 4.0, pre_clean_fx: bool = False) -> Optional[np.ndarray]:
        key = f"{path}_{self.w}x{self.h}_{pre_clean_fx}"
        if key not in _SHARED_SAMPLER_CACHE:
            frames: List[np.ndarray] = []
            if path.is_file():
                cap = cv2.VideoCapture(str(path))
                max_f = int(max_seconds * self.fps)
                while len(frames) < max_f:
                    ok, frm = cap.read()
                    if not ok:
                        break
                    fh, fw = frm.shape[:2]
                    scale = max(self.w / float(max(1, fw)), self.h / float(max(1, fh)))
                    nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
                    resized = cv2.resize(frm, (nw, nh), interpolation=cv2.INTER_LINEAR)
                    x0 = max(0, (nw - self.w) // 2)
                    y0 = max(0, (nh - self.h) // 2)
                    crop = resized[y0 : y0 + self.h, x0 : x0 + self.w]
                    if pre_clean_fx:
                        crop = cv2.subtract(crop, (24, 24, 24, 0))
                    frames.append(crop)
                cap.release()
            _SHARED_SAMPLER_CACHE[key] = frames
        seq = _SHARED_SAMPLER_CACHE[key]
        if not seq:
            return None
        return seq[frame_idx % len(seq)]


def render_oled_photo_hold(
    family: str,
    cards: List[PreparedCard],
    idx: int,
    t: float,
    width: int,
    height: int,
) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    n = len(cards)
    card = cards[idx]

    if family in ("falling_cube", "falling_cube_finale"):
        is_finale = family == "falling_cube_finale"
        eased = ease_in_out(min(1.0, t / 0.28)) if t < 0.28 else 1.0
        # 3 background falling mini-cubes from companion shots
        for k in range(3):
            sub = cards[(idx + k + 1) % n]
            phase = t * math.pi * 1.4 + k * 2.1
            cy = 0.18 + ((t * 0.55 + k * 0.31) % 0.68)
            cx = (0.20 if k % 2 == 0 else 0.80) + 0.04 * math.sin(phase)
            yaw = 26.0 * math.sin(phase) + (16.0 if k % 2 == 0 else -16.0)
            pitch = 12.0 * math.cos(phase * 0.8)
            warp_card_onto(canvas, sub.mini, yaw, pitch, 0.92, cx, cy, opacity=0.32)

        idle_t = max(0.0, (t - 0.28) / 0.72) if t >= 0.28 else 0.0
        hero_cy = 0.50 - (1.0 - eased) * 0.20
        hero_yaw = (1.0 - eased) * (-38.0 if idx % 2 == 0 else 38.0) + math.sin(idle_t * math.pi) * (6.0 if not is_finale else 3.5)
        hero_pitch = (1.0 - eased) * 14.0 + math.cos(idle_t * math.pi) * 2.5
        hero_scale = (0.86 + 0.14 * eased) * (1.0 + (0.06 * idle_t if is_finale else 0.04 * math.sin(idle_t * math.pi)))
        warp_card_onto(canvas, card.main, hero_yaw, hero_pitch, hero_scale, 0.50, hero_cy, opacity=1.0)
        return canvas

    if family == "cube_fly":
        yaw = math.sin(t * math.pi * 2) * 8.5
        pitch = math.cos(t * math.pi) * 4.0
        sc = 0.94 + 0.06 * math.sin(t * math.pi)
        warp_card_onto(canvas, card.main, yaw, pitch, sc, 0.50, 0.50, opacity=1.0)
        return canvas

    if family == "carousel_3d":
        sway = math.sin(t * math.pi) * 0.18
        for off in (-1, 1):
            sub = cards[(idx + off) % n]
            ang = math.pi * 0.5 + off * 0.68 + sway
            depth = (math.sin(ang) + 1.0) * 0.5
            yaw = math.degrees(math.cos(ang)) * 26.0
            cx = 0.50 + math.cos(ang) * 0.29
            cy = 0.50 + (math.sin(ang) - 0.8) * 0.06
            warp_card_onto(canvas, sub.mid, yaw, -3.0, 0.78 + 0.14 * depth, cx, cy, opacity=0.34)
        hero_yaw = math.sin(t * math.pi * 2) * 5.0
        warp_card_onto(canvas, card.main, hero_yaw, 1.5, 0.96 + 0.04 * math.sin(t * math.pi), 0.50, 0.50, opacity=1.0)
        return canvas

    if family == "accumulate_cards":
        enter_t = min(1.0, t / 0.30)
        enter_eased = 1.0 - (1.0 - enter_t) ** 3
        bg_poses = [
            (-16.0, 6.0, 0.88, 0.30, 0.47),
            (15.0, -5.0, 0.88, 0.70, 0.52),
            (-10.0, 8.0, 0.90, 0.34, 0.55),
        ]
        start_i = max(0, idx - 3)
        for k, prev_i in enumerate(range(start_i, idx)):
            yaw, pitch, sc, cx, cy = bg_poses[k % len(bg_poses)]
            warp_card_onto(canvas, cards[prev_i].mid, yaw, pitch, sc, cx, cy, opacity=0.38)
        start_cx = 0.50 + (0.42 if idx % 2 == 0 else -0.42)
        cx = start_cx + (0.50 - start_cx) * enter_eased
        cy = 0.66 + (0.50 - 0.66) * enter_eased
        yaw = (28.0 if idx % 2 == 0 else -28.0) * (1.0 - enter_eased) + math.sin(t * math.pi) * 4.5
        pitch = -12.0 * (1.0 - enter_eased) + math.cos(t * math.pi) * 2.5
        sc = 1.06 + (0.96 - 1.06) * enter_eased
        warp_card_onto(canvas, card.main, yaw, pitch, sc, cx, cy, opacity=1.0)
        return canvas

    if family == "light_sweep":
        yaw = math.sin(t * math.pi) * 4.0
        sc = 0.94 + 0.05 * t
        warp_card_onto(canvas, card.crystal, yaw, 2.0, sc, 0.50, 0.50, opacity=1.0)
        return add_diagonal_light_sweep(canvas, (t * 1.15) % 1.0)

    if family == "page_turn":
        yaw = math.sin(t * math.pi) * 3.5
        sc = 0.95 + 0.04 * math.sin(t * math.pi)
        warp_card_onto(canvas, card.main, yaw, -2.0, sc, 0.50, 0.50, opacity=1.0)
        return canvas

    if family == "parallax_sphere":
        twin = cards[(idx + 1) % n]
        warp_card_onto(canvas, twin.mid, -14.0, 5.0, 0.96, 0.34, 0.48, opacity=0.28)
        sway = math.sin(t * math.pi * 2) * 8.0
        boom = math.cos(t * math.pi) * 3.5
        warp_card_onto(canvas, card.main, sway, boom, 0.95 + 0.04 * math.sin(t * math.pi), 0.52, 0.50, opacity=1.0)
        return canvas

    if family == "vertical_slide":
        eased = ease_in_out(min(1.0, t / 0.25)) if t < 0.25 else 1.0
        cy = 0.50 + (1.0 - eased) * 0.20
        yaw = math.sin(t * math.pi) * 4.0
        pitch = (1.0 - eased) * 10.0
        warp_card_onto(canvas, card.main, yaw, pitch, 0.95 + 0.04 * t, 0.50, cy, opacity=1.0)
        return canvas

    # cinematic_zoom (mixkit-591)
    sc = 0.92 + 0.10 * t
    yaw = math.sin(t * math.pi) * 3.0
    warp_card_onto(canvas, card.main, yaw, 1.5, sc, 0.50, 0.50, opacity=1.0)
    return canvas


def render_falling_cube_transition(
    card_a: PreparedCard,
    card_b: PreparedCard,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    p = ease_in_out(progress)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    if p < 0.58:
        lp = p / 0.58
        warp_card_onto(
            canvas,
            card_a.main,
            yaw_deg=lp * 78.0,
            pitch_deg=-lp * 14.0,
            scale=0.96 - 0.20 * lp,
            cx_norm=0.50,
            cy_norm=0.50 + 0.15 * lp,
            opacity=1.0 - 0.65 * lp,
        )
    if p > 0.34:
        lp = (p - 0.34) / 0.66
        warp_card_onto(
            canvas,
            card_b.main,
            yaw_deg=-78.0 * (1.0 - lp),
            pitch_deg=16.0 * (1.0 - lp),
            scale=0.76 + 0.20 * lp,
            cx_norm=0.50,
            cy_norm=0.50 - 0.16 * (1.0 - lp),
            opacity=min(1.0, lp * 1.25),
        )
    return canvas


def render_oled_transition(
    next_family: str,
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    card_a: PreparedCard,
    card_b: PreparedCard,
    progress: float,
    width: int,
    height: int,
    ue_renderer: UE3DDepthRenderer,
) -> np.ndarray:
    if next_family in ("falling_cube", "falling_cube_finale", "cube_fly"):
        return render_falling_cube_transition(card_a, card_b, progress, width, height)
    if next_family == "page_turn":
        return ue_renderer.render_3d_page_turn_mesh_transition(frame_a, frame_b, progress)
    if next_family == "light_sweep":
        return ue_renderer.render_light_sweep_transition(frame_a, frame_b, progress)
    if next_family == "cinematic_zoom":
        return ue_renderer.render_cinematic_zoom_transition(frame_a, frame_b, progress)
    alpha = 0.5 - 0.5 * math.cos(max(0.0, min(1.0, progress)) * math.pi)
    return cv2.addWeighted(frame_a, 1.0 - alpha, frame_b, alpha, 0)


class CeremonyBottomRenderer:
    """Pre-renders and caches the bottom 1080x580 ceremony order (식순) panel on exact #000000."""

    def __init__(self, groom: str, bride: str):
        self.groom = groom
        self.bride = bride
        self._step_panels: Dict[int, np.ndarray] = {}
        self.f_step_active = load_font(TITLE_KO, 34)
        self.f_step_idle = load_font(BODY_KO, 28)
        self.f_num = load_font(LATIN, 24, 550)
        self.f_en = load_font(LATIN, 16, 500)
        self.f_header = load_font(SANS_KO, 22, 500)
        self.f_live = load_font(SANS_KO, 20, 600)

    def get_panel(self, active_step_idx: int, pulse: float = 0.5) -> np.ndarray:
        p_bin = int(round(max(0.0, min(1.0, pulse)) * 6))
        key = active_step_idx * 100 + p_bin
        if key in self._step_panels:
            return self._step_panels[key]

        im = Image.new("RGB", (W, BOT_H), (0, 0, 0))
        d = ImageDraw.Draw(im)

        gold = (232, 206, 164)
        gold_dim = (118, 98, 72)
        ivory = (255, 248, 240)
        muted = (110, 104, 96)

        d.line((120, 24, W - 120, 24), fill=(90, 74, 52), width=1)
        header = f"THEREBORN   ·   {self.groom}  &  {self.bride}   ·   예식 순서"
        d.text((W // 2, 52), header, font=self.f_header, fill=gold, anchor="mm")

        y0 = 104
        row_h = 74
        glow_boost = int(28 * (p_bin / 6.0))

        for step in CEREMONY_STEPS:
            idx = step["idx"]
            cy = y0 + (idx - 1) * row_h
            is_active = idx == active_step_idx
            is_done = idx < active_step_idx

            if is_active:
                box_x0, box_x1 = 110, W - 110
                border_col = (min(255, 215 + glow_boost), min(255, 182 + glow_boost), min(255, 130 + glow_boost))
                d.rounded_rectangle(
                    (box_x0, cy - 28, box_x1, cy + 28),
                    radius=14,
                    outline=border_col,
                    width=2,
                )
                dot_x = box_x0 + 38
                d.ellipse((dot_x - 9, cy - 9, dot_x + 9, cy + 9), fill=ivory, outline=border_col, width=2)
                d.text((box_x0 + 76, cy), f"0{idx}", font=self.f_num, fill=border_col, anchor="lm")
                d.text((box_x0 + 138, cy - 2), step["ko"], font=self.f_step_active, fill=ivory, anchor="lm")
                d.text((box_x1 - 30, cy), "진행 중", font=self.f_live, fill=border_col, anchor="rm")
            else:
                box_x0, box_x1 = 110, W - 110
                dot_x = box_x0 + 38
                col_num = gold_dim if is_done else (75, 68, 58)
                col_txt = (150, 142, 130) if is_done else muted
                d.ellipse((dot_x - 4, cy - 4, dot_x + 4, cy + 4), fill=col_num)
                d.text((box_x0 + 76, cy), f"0{idx}", font=self.f_num, fill=col_num, anchor="lm")
                d.text((box_x0 + 138, cy - 1), step["ko"], font=self.f_step_idle, fill=col_txt, anchor="lm")
                d.text((box_x1 - 30, cy), step["en"], font=self.f_en, fill=col_num, anchor="rm")

        arr = np.asarray(im, dtype=np.int16)
        arr[arr.max(axis=2) <= 4] = 0
        bgr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2BGR)
        self._step_panels[key] = bgr
        return bgr


class TopBadgeOverlay:
    """Caches the top header badge per shot index (0..9) with uint8 mask for fast copyTo."""

    def __init__(self, groom: str, bride: str, total_shots: int = 10):
        self.groom = groom
        self.bride = bride
        self.total_shots = total_shots
        self._cache: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        self.f_en = load_font(LATIN, 22, 550)
        self.f_ko = load_font(TITLE_KO, 30)

    def apply(self, stage: np.ndarray, shot_idx: int) -> None:
        if shot_idx not in self._cache:
            im = Image.new("RGBA", (W, 84), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            gold = (232, 206, 164, 255)
            ivory = (255, 248, 240, 255)
            d.text((86, 48), "THEREBORN", font=self.f_en, fill=gold, anchor="lm")
            d.text((W // 2, 48), f"{self.groom} · {self.bride}", font=self.f_ko, fill=ivory, anchor="mm")
            d.text((W - 86, 48), f"{shot_idx + 1:02d} / {self.total_shots:02d}", font=self.f_en, fill=gold, anchor="rm")
            arr = np.asarray(im)
            bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
            mask = (arr[:, :, 3] > 24).astype(np.uint8) * 255
            self._cache[shot_idx] = (bgr, mask)
        bgr, mask = self._cache[shot_idx]
        # Clear top strip to pure #000000 then stamp crisp badge
        stage[:84, :] = (stage[:84, :] // 3)
        cv2.copyTo(bgr, mask, stage[:84, :])


def make_intro_title_layer(groom: str, bride: str, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gold = (232, 206, 164, 255)
    ivory = (255, 248, 240, 255)
    d.text((width // 2, 360), "THEREBORN", font=load_font(LATIN, 30, 550), fill=gold, anchor="mm")
    d.line((width // 2 - 90, 410, width // 2 + 90, 410), fill=gold, width=2)
    d.text((width // 2, 560), f"{groom}  ·  {bride}", font=load_font(TITLE_KO, 86), fill=ivory, anchor="mm")
    d.text((width // 2, 700), "끊이지 않는 인연, 특별한 순간", font=load_font(BODY_KO, 36), fill=gold, anchor="mm")
    arr = np.asarray(layer)
    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    mask = (arr[:, :, 3] > 20).astype(np.uint8) * 255
    return bgr, mask


def render_couple_video(
    couple: dict,
    fps: int = 24,
    hold_sec: float = 9.0,
    trans_sec: float = 1.5,
    broll_sec: float = 3.5,
    intro_sec: float = 4.0,
    outro_sec: float = 2.0,
) -> dict:
    t_start = time.time()
    cid = couple["id"]
    groom = couple["groom"]
    bride = couple["bride"]
    folder = couple["folder"]
    shots = [COUPLES_ROOT / rel for rel in couple["shots"]]
    if len(shots) < 10:
        raise RuntimeError(f"Couple {cid} has {len(shots)} shots, expected 10")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_mp4 = OUT_ROOT / f"{folder}.mp4"
    temp_raw = OUT_ROOT / f"_raw_{cid}.mp4"

    ue_renderer = UE3DDepthRenderer(width=W, height=TOP_H)
    sampler = ClipSampler(target_w=W, target_h=TOP_H, fps=fps)
    bottom_ui = CeremonyBottomRenderer(groom=groom, bride=bride)
    badge = TopBadgeOverlay(groom=groom, bride=bride, total_shots=len(shots))
    intro_bgr, intro_mask = make_intro_title_layer(groom, bride, W, TOP_H)

    cards: List[PreparedCard] = [PreparedCard(ue_renderer.prepare_photo_bytes(str(p)), W, TOP_H) for p in shots]

    intro_frames = int(round(intro_sec * fps))
    hold_frames = int(round(hold_sec * fps))
    trans_frames = int(round(trans_sec * fps))
    broll_frames = int(round(broll_sec * fps))
    outro_frames = int(round(outro_sec * fps))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_raw), fourcc, float(fps), (W, H))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {temp_raw}")

    frame_cursor = 0
    full_frame = np.zeros((H, W, 3), dtype=np.uint8)

    def emit(top_stage: np.ndarray, step_idx: int, shot_idx: int, show_badge: bool = True) -> None:
        nonlocal frame_cursor
        if show_badge:
            badge.apply(top_stage, shot_idx)
        # Keep bottom 24px of top_stage pure black for clean separation above ceremony order panel
        top_stage[TOP_H - 24 :, :] = 0
        pulse = 0.5 + 0.5 * math.sin(frame_cursor / float(fps) * math.pi * 1.5)
        bot_stage = bottom_ui.get_panel(step_idx, pulse=pulse)
        full_frame[:TOP_H, :] = top_stage
        full_frame[TOP_H:, :] = bot_stage
        writer.write(full_frame)
        frame_cursor += 1

    # 1. Opening Title + Emerging Hero Cube (4.0s)
    for f in range(intro_frames):
        t = f / float(max(1, intro_frames - 1))
        canvas = np.zeros((TOP_H, W, 3), dtype=np.uint8)
        if t > 0.20:
            p_card = ease_in_out((t - 0.20) / 0.80)
            warp_card_onto(canvas, cards[0].main, (1.0 - p_card) * -28.0, 6.0, 0.72 + 0.16 * p_card, 0.50, 0.54, opacity=0.36 * p_card)
        fx = sampler.get_frame(FX_SOURCES["cube_bokeh"], frame_cursor, pre_clean_fx=True)
        if fx is not None:
            canvas = cv2.addWeighted(canvas, 1.0, fx, 0.26, 0)
        fade_in = math.sin(min(1.0, t * 1.25) * math.pi * 0.5)
        titled = cv2.addWeighted(canvas, 1.0, intro_bgr, fade_in, 0)
        cv2.copyTo(titled, intro_mask, canvas)
        emit(canvas, step_idx=1, shot_idx=0, show_badge=False)

    # 2. All 10 Photos across MBOX template families + B-roll bridges
    for i, plan in enumerate(PHOTO_TEMPLATE_PLAN):
        fam = plan["family"]
        step_idx = plan["step_idx"]
        fx_path = FX_SOURCES[plan["fx"]]

        for f in range(hold_frames):
            t = f / float(max(1, hold_frames - 1))
            stage = render_oled_photo_hold(fam, cards, i, t, W, TOP_H)
            fx = sampler.get_frame(fx_path, frame_cursor, pre_clean_fx=True)
            if fx is not None:
                stage = cv2.addWeighted(stage, 1.0, fx, 0.26, 0)
            emit(stage, step_idx=step_idx, shot_idx=i, show_badge=True)

        if i in BROLL_BRIDGES:
            br_info = BROLL_BRIDGES[i]
            br_path = BROLL_SOURCES[br_info["broll_key"]]
            br_step = br_info["step_idx"]
            end_photo_stage = render_oled_photo_hold(fam, cards, i, 1.0, W, TOP_H)
            next_fam = PHOTO_TEMPLATE_PLAN[i + 1]["family"]
            start_next_stage = render_oled_photo_hold(next_fam, cards, i + 1, 0.0, W, TOP_H)

            for bf in range(broll_frames):
                bt = bf / float(max(1, broll_frames - 1))
                br_raw = sampler.get_frame(br_path, bf, max_seconds=4.5, pre_clean_fx=False)
                if br_raw is None:
                    br_out = end_photo_stage.copy()
                else:
                    br_card = PreparedCard._build_framed(br_raw, int(W * 0.82), int(TOP_H * 0.78), pad=10)
                    br_stage = np.zeros((TOP_H, W, 3), dtype=np.uint8)
                    warp_card_onto(br_stage, br_card, math.sin(bt * math.pi) * 5.0, 2.0, 0.96, 0.50, 0.50, opacity=1.0)
                    if bt < 0.22:
                        alpha = bt / 0.22
                        br_out = cv2.addWeighted(end_photo_stage, 1.0 - alpha, br_stage, alpha, 0)
                    elif bt > 0.78:
                        alpha = (bt - 0.78) / 0.22
                        br_out = cv2.addWeighted(br_stage, 1.0 - alpha, start_next_stage, alpha, 0)
                    else:
                        br_out = br_stage
                emit(br_out, step_idx=br_step, shot_idx=i, show_badge=True)

        if i < len(PHOTO_TEMPLATE_PLAN) - 1:
            next_plan = PHOTO_TEMPLATE_PLAN[i + 1]
            next_fam = next_plan["family"]
            frame_a = render_oled_photo_hold(fam, cards, i, 1.0, W, TOP_H)
            frame_b = render_oled_photo_hold(next_fam, cards, i + 1, 0.0, W, TOP_H)
            for tf in range(trans_frames):
                prog = (tf + 1) / float(trans_frames)
                t_stage = render_oled_transition(
                    next_fam, frame_a, frame_b, cards[i], cards[i + 1], prog, W, TOP_H, ue_renderer
                )
                fx = sampler.get_frame(fx_path, frame_cursor, pre_clean_fx=True)
                if fx is not None:
                    t_stage = cv2.addWeighted(t_stage, 1.0, fx, 0.22, 0)
                emit(t_stage, step_idx=next_plan["step_idx"], shot_idx=i + 1 if prog > 0.5 else i, show_badge=True)

    # 3. Finale Hold & Fade to pure #000000 (2.0s)
    last_stage = render_oled_photo_hold("falling_cube_finale", cards, 9, 1.0, W, TOP_H)
    for f in range(outro_frames):
        t = f / float(max(1, outro_frames - 1))
        fade = 1.0 - ease_in_out(t)
        faded = cv2.convertScaleAbs(last_stage, alpha=fade, beta=0)
        emit(faded, step_idx=6, shot_idx=9, show_badge=True)

    writer.release()

    total_dur = frame_cursor / float(fps)
    fade_st = max(0.0, total_dur - 1.5)
    cmd = ["ffmpeg", "-y", "-i", str(temp_raw)]
    if BGM_PATH.is_file():
        cmd += [
            "-stream_loop",
            "-1",
            "-i",
            str(BGM_PATH),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            f"afade=t=in:st=0:d=1.0,afade=t=out:st={fade_st:.2f}:d=1.5",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
    else:
        cmd += [
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]

    res = subprocess.run(cmd, capture_output=True)
    if temp_raw.is_file():
        try:
            temp_raw.unlink()
        except OSError:
            pass
    if res.returncode != 0:
        err = (res.stderr or b"").decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"ffmpeg failed for couple {cid}: {err}")

    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(out_mp4),
    ]
    probe = json.loads(subprocess.check_output(probe_cmd, text=True))["format"]
    elapsed = time.time() - t_start
    return {
        "id": cid,
        "groom": groom,
        "bride": bride,
        "file": str(out_mp4.relative_to(THERIBBON_ROOT)).replace("\\", "/"),
        "duration_sec": round(float(probe["duration"]), 2),
        "size_mb": round(int(probe["size"]) / (1024 * 1024), 2),
        "photos_included": len(shots),
        "render_time_sec": round(elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--couples", nargs="*", default=[], help="Couple IDs e.g. 01 02 (empty = all 10)")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    cast = json.loads(CAST_PATH.read_text(encoding="utf-8"))
    couples = cast["couples"]
    if args.couples:
        wanted = {c.zfill(2) for c in args.couples}
        couples = [c for c in couples if c["id"] in wanted]

    t0 = time.time()
    manifest_rows: List[dict] = []

    if len(couples) == 1 or args.workers <= 1:
        for couple in couples:
            row = render_couple_video(couple, fps=args.fps)
            manifest_rows.append(row)
            print(
                f"[OK] {row['id']} {row['groom']}·{row['bride']} -> {row['file']} "
                f"({row['duration_sec']}s, {row['size_mb']}MB, {row['render_time_sec']}s)",
                flush=True,
            )
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(render_couple_video, c, args.fps): c for c in couples}
            for fut in as_completed(futs):
                row = fut.result()
                manifest_rows.append(row)
                print(
                    f"[OK] {row['id']} {row['groom']}·{row['bride']} -> {row['file']} "
                    f"({row['duration_sec']}s, {row['size_mb']}MB, {row['render_time_sec']}s)",
                    flush=True,
                )

    manifest_rows.sort(key=lambda r: r["id"])
    manifest_path = OUT_ROOT / "manifest.json"
    manifest_data = {
        "resolution": [W, H],
        "fps": args.fps,
        "target_duration_sec": 120.0,
        "oled_canvas": "#000000",
        "layout": {
            "top_video_stage": [W, TOP_H],
            "bottom_ceremony_order": [W, BOT_H],
        },
        "mbox_templates_used": [p["template_id"] for p in PHOTO_TEMPLATE_PLAN],
        "broll_sources_used": {k: str(v) for k, v in BROLL_SOURCES.items()},
        "ceremony_steps": CEREMONY_STEPS,
        "videos": manifest_rows,
        "total_elapsed_sec": round(time.time() - t0, 1),
    }
    manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== All {len(manifest_rows)} videos completed in {manifest_data['total_elapsed_sec']}s ===", flush=True)


if __name__ == "__main__":
    main()
