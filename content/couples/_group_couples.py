import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root / "cast.json").read_text(encoding="utf-8"))

for couple in data["couples"]:
    folder = root / f"{couple['id']}-{couple['groom']}-{couple['bride']}"
    folder.mkdir(exist_ok=True)
    moved = []
    for path in sorted(root.glob(f"couple-{couple['id']}-*.jpg")):
        dest = folder / path.name
        shutil.move(str(path), str(dest))
        moved.append(f"{folder.name}/{path.name}")
    hero_name = Path(couple["file"]).name
    couple["folder"] = folder.name
    couple["file"] = f"{folder.name}/{hero_name}"
    couple["shots"] = moved
    print(f"{folder.name}\t{len(moved)}")

for shot in data["shots"]:
    pattern = shot["file_pattern"]
    if not pattern.startswith("{folder}/"):
        shot["file_pattern"] = "{folder}/" + pattern

(root / "cast.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("root", [path.name for path in root.iterdir()])
