"""Texture-maps sheet for the chest delivery (system python3 + PIL).

    python3 texture_sheet.py output/chest/textures out.png
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24); FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
rows = [("chest_wood", "Wood (planks, staves)"), ("chest_woodend", "End grain: growth rings (plank ends, cores)")]
kinds = [("Diffuse", "Base colour (graded, baked)"), ("nor_gl", "Normal (OpenGL)"), ("Rough", "Roughness")]
T = 560; pad = 40; W = pad + len(kinds) * (T + pad) + 520; H = 130 + len(rows) * (T + 110)
im = Image.new("RGB", (W, H), (30, 31, 34)); d = ImageDraw.Draw(im)
d.text((pad, 34), "Treasure chest - texture maps (2048 px, PBR metal/rough, CC0: Poly Haven 'Dark Wood' + procedural end grain)", font=FB, fill=(235, 235, 235))
for r, (pre, label) in enumerate(rows):
    y = 120 + r * (T + 110)
    for c, (k, kl) in enumerate(kinds):
        p = os.path.join(src, f"{pre}_{k}_2k.jpg"); x = pad + c * (T + pad)
        tile = Image.open(p).convert("RGB"); tile = tile.resize((T, T), Image.LANCZOS); im.paste(tile, (x, y))
        d.text((x, y + T + 12), f"{pre}_{k}_2k.jpg", font=F, fill=(220, 220, 220)); d.text((x, y + T + 44), kl, font=F, fill=(150, 150, 150))
    d.text((pad + len(kinds) * (T + pad), y + 10), label, font=FB, fill=(235, 235, 235))
x0 = pad + len(kinds) * (T + pad); y0 = 120 + 2 * 60
notes = ["Brass / gold / velvet are procedural", "PBR values (no maps needed):", "", "Aged brass: metallic 1.0, base #B8872B,",
         "  roughness 0.40-0.66 + bump 0.5, edge wear", "  (pointiness) + cavity tarnish (AO)", "Velvet: CC0 velour normal/rough + sheen,", "  piping cords, stitch line", "Gold coins: metallic 1.0, rough 0.22", "",
         "Render-only shader detail:", "  wood normal strength 2.0,", "  per-plank tone/roughness ('var'", "  face attribute), AO grime,", "  fine scratches"]
for i, l in enumerate(notes): d.text((x0, y0 + 60 + T + i * 34), l, font=F, fill=(190, 190, 190))
im.save(out); print(out)
