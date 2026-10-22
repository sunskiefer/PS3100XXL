#!/usr/bin/env python3
"""Draws art/tile.png, the 270x110 picture MPC's Sounds > INSTRUMENTS browser shows for PS3100XXL."""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_skin as P  # noqa: E402

im = Image.new("RGBA", (270, 110), P.PANEL + (255,))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 269, 109], outline=(110, 110, 110), width=2)
for i, a in enumerate((-120, -30, 60)):
    k = P.knob_frame(26, a)
    im.alpha_composite(k, (14 + i * 52, 46))
sw = P.switch_image(True, 54, 26)
im.alpha_composite(sw, (200, 64))
d.text((14, 22), "PS3100XXL", font=P.font(30), fill=P.INK, anchor="lm")
d.text((256, 24), "L'Cronx", font=P.font(16), fill=P.ORANGE, anchor="rm")
im.convert("RGB").save(os.path.join(P.ROOT, "art", "tile.png"))
print("tile: art/tile.png")
