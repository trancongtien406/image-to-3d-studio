"""Side-by-side: reference photo vs Blender render from a matched camera (system python3 + PIL).

    python3 compare_reference.py ref.png render.png out.png
"""
import sys
from PIL import Image, ImageDraw, ImageFont
ref, ren, out = sys.argv[1:4]
S = 1200
a = Image.open(ref).convert("RGB").resize((S, S)); b = Image.open(ren).convert("RGB").resize((S, S))
im = Image.new("RGB", (2 * S + 60, S + 120), (30, 31, 34)); im.paste(a, (20, 100)); im.paste(b, (S + 40, 100))
d = ImageDraw.Draw(im); f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
d.text((20, 30), "Reference (input image)", font=f, fill=(235, 235, 235)); d.text((S + 40, 30), "Blender model, matched camera (Cycles)", font=f, fill=(235, 235, 235))
im.save(out); print(out)
