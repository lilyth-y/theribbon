import sys
sys.path.insert(0, r"c:\startingup\theribbon\content\oled")
import render_oled as r

couples = r.load_cast()
r.save(r.render_halls(couples), r.ROOT / "lobby" / "halls.png")
print(r.measure(r.ROOT / "lobby" / "halls.png"))
