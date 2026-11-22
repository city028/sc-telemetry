"""Draws the program icon: a telemetry trace across a gauge ring, in the
dashboard's colours.

    python make_icon.py icon.ico [preview.png]

Each size is scaled down from one large drawing; 32 px and under from a
plainer one without the tile's border.
"""
import sys
from PIL import Image, ImageDraw

S = 1024                                   # drawn at this size, then scaled
BG, EDGE, ACCENT, OK = "#0b0f14", "#1f2a37", "#4cc3ff", "#3ddc84"


def draw(small):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, S - 16, S - 16), radius=200, fill=BG,
                        outline=EDGE, width=0 if small else 20)
    # Gauge ring: three quarters, open at the bottom.
    r, w = 330, 70 if small else 56
    d.arc((512 - r, 512 - r, 512 + r, 512 + r), start=135, end=405, fill=ACCENT, width=w)
    # Telemetry trace across the middle.
    pts = [(150, 560), (330, 560), (400, 400), (480, 700), (560, 330), (630, 560), (874, 560)]
    d.line(pts, fill=OK, width=80 if small else 60, joint="curve")
    return im


big, small = draw(False), draw(True)
sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
frames = [(small if n <= 32 else big).resize((n, n), Image.LANCZOS) for n in sizes]
frames[-1].save(sys.argv[1], format="ICO", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
if len(sys.argv) > 2:                      # a preview strip
    strip = Image.new("RGBA", (sum(sizes) + 10 * len(sizes), 256), "#ffffff")
    x = 0
    for f in frames:
        strip.paste(f, (x, 0), f)
        x += f.width + 10
    strip.save(sys.argv[2])
