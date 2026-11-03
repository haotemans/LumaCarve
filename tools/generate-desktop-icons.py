#!/usr/bin/env python3
"""Generate functional app-icon sizes needed by the Tauri NSIS/deb/AppImage bundlers."""
from pathlib import Path
from PIL import Image, ImageDraw
from math import sin, cos, pi

dest = Path(__file__).resolve().parents[1] / "frontend" / "src-tauri" / "icons"
dest.mkdir(parents=True, exist_ok=True)

def make_icon(n: int):
    image = Image.new("RGBA", (n, n), (20, 30, 53, 255))
    draw = ImageDraw.Draw(image)
    p = n * .13
    draw.rounded_rectangle([p, p, n - p, n - p], radius=n * .22, fill=(105, 93, 222, 255))
    c = n / 2
    r = n * .225
    draw.ellipse([c-r, c-r, c+r, c+r], outline=(240, 237, 255, 255), width=max(2, int(n*.045)))
    for i in range(4):
        t = i * pi / 2
        x, y = c + cos(t) * r * .65, c + sin(t) * r * .65
        draw.ellipse([x-n*.045, y-n*.045, x+n*.045, y+n*.045], fill=(255, 255, 255, 255))
    return image

for size, name in [(32, "32x32.png"), (128, "128x128.png"), (256, "128x128@2x.png"), (256, "icon.png")]:
    make_icon(size).save(dest / name)
make_icon(256).save(dest / "icon.ico", format="ICO",
    sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("Generated Tauri desktop icons in", dest)
