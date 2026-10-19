from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(r"c:\startingup\theribbon\content\oled\type\_specimen.png")
out.parent.mkdir(parents=True, exist_ok=True)
im = Image.new("RGB", (1080, 1400), (0, 0, 0))
d = ImageDraw.Draw(im)


def vfont(path, size, weight):
    f = ImageFont.truetype(path, size)
    f.set_variation_by_axes([weight])
    return f


rows = [
    ("NotoSerif 200 (before)", vfont(r"C:\Windows\Fonts\NotoSerifKR-VF.ttf", 72, 200), "끊이지 않는 인연  이서준 · 김하은"),
    ("NotoSerif 500", vfont(r"C:\Windows\Fonts\NotoSerifKR-VF.ttf", 72, 500), "끊이지 않는 인연  이서준 · 김하은"),
    ("NotoSerif 650", vfont(r"C:\Windows\Fonts\NotoSerifKR-VF.ttf", 72, 650), "끊이지 않는 인연  이서준 · 김하은"),
    ("GowunBatang Reg", ImageFont.truetype(r"c:\startingup\theribbon\content\oled\fonts\GowunBatang-Regular.ttf", 72), "끊이지 않는 인연  이서준 · 김하은"),
    ("GowunBatang Bold", ImageFont.truetype(r"c:\startingup\theribbon\content\oled\fonts\GowunBatang-Bold.ttf", 72), "끊이지 않는 인연  이서준 · 김하은"),
    ("HANBatang", ImageFont.truetype(r"C:\Windows\Fonts\HANBatang.ttf", 72), "끊이지 않는 인연  이서준 · 김하은"),
    ("HANBatangB", ImageFont.truetype(r"C:\Windows\Fonts\HANBatangB.ttf", 72), "끊이지 않는 인연  이서준 · 김하은"),
    ("Hoonminjeongeum", ImageFont.truetype(r"C:\Windows\Fonts\HancomHoonminjeongeumH.ttf", 72), "끊이지 않는 인연  이서준 · 김하은"),
    ("Cinzel 550", vfont(r"c:\startingup\theribbon\content\oled\fonts\Cinzel.ttf", 64, 550), "THEREBORN   RE:BORN"),
    ("Cormorant 600", vfont(r"c:\startingup\theribbon\content\oled\fonts\CormorantGaramond-Medium.ttf", 78, 600), "THEREBORN   RE:BORN"),
]
label_f = vfont(r"C:\Windows\Fonts\NotoSansKR-VF.ttf", 24, 500)
y = 40
for name, f, sample in rows:
    d.text((60, y), name, font=label_f, fill=(168, 142, 108))
    d.text((60, y + 32), sample, font=f, fill=(255, 248, 240))
    y += 130
im.save(out)
print("saved", out)
