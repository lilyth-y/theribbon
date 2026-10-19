import json
import shutil
import subprocess
import sys

sys.path.insert(0, r"c:\startingup\theribbon\content\oled")
import render_couple_videos as r

cast = json.loads(r.CAST_PATH.read_text(encoding="utf-8"))
rows = []
for c in cast["couples"]:
    mp4 = r.OUT_ROOT / f"{c['folder']}.mp4"
    dst = r.COUPLES_ROOT / c["folder"] / f"couple-{c['id']}-mbox-2m.mp4"
    shutil.copy2(mp4, dst)
    probe = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-show_entries",
                "stream=codec_name,width,height",
                "-of",
                "json",
                str(mp4),
            ],
            text=True,
        )
    )
    fmt = probe["format"]
    vstream = [s for s in probe["streams"] if s.get("width")][0]
    astream = [s for s in probe["streams"] if s.get("codec_name") == "aac"][0]
    c["video"] = str(mp4.relative_to(r.THERIBBON_ROOT)).replace("\\", "/")
    c["folder_video"] = str(dst.relative_to(r.THERIBBON_ROOT)).replace("\\", "/")
    rows.append(
        {
            "id": c["id"],
            "groom": c["groom"],
            "bride": c["bride"],
            "video": c["video"],
            "couple_folder_copy": c["folder_video"],
            "resolution": [vstream["width"], vstream["height"]],
            "audio_codec": astream["codec_name"],
            "duration_sec": round(float(fmt["duration"]), 2),
            "size_mb": round(int(fmt["size"]) / (1024 * 1024), 2),
            "photos_included": len(c["shots"]),
        }
    )

r.CAST_PATH.write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")
manifest = {
    "resolution": [r.W, r.H],
    "fps": 24,
    "duration_sec": 120.0,
    "oled_canvas": "#000000",
    "layout": {"top_video_stage": [r.W, r.TOP_H], "bottom_ceremony_order": [r.W, r.BOT_H]},
    "mbox_templates_used": [p["template_id"] for p in r.PHOTO_TEMPLATE_PLAN],
    "broll_sources_used": {k: str(v) for k, v in r.BROLL_SOURCES.items()},
    "fx_sources_used": {k: str(v) for k, v in r.FX_SOURCES.items()},
    "ceremony_steps": r.CEREMONY_STEPS,
    "videos": rows,
}
(r.OUT_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("verified", len(rows), "videos")
