"""Texture-maps sheet for the chest delivery (system python3 + PIL).

    python3 texture_sheet.py output/chest/textures out.png
"""
import os, sys, textwrap
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
DJ = "/usr/share/fonts/truetype/dejavu/"
F = ImageFont.truetype(DJ + "DejaVuSans.ttf", 24); FB = ImageFont.truetype(DJ + "DejaVuSans-Bold.ttf", 34); FS = ImageFont.truetype(DJ + "DejaVuSans.ttf", 22)
rows = [("chest_wood", "Wood (planks, staves)"), ("chest_woodend", "End grain (growth rings)")]
kinds = [("Diffuse", "Base colour (graded, baked)"), ("nor_gl", "Normal (OpenGL)"), ("Rough", "Roughness")]
T = 560; pad = 45; RC = 640                      # right column width
W = pad + len(kinds) * (T + pad) + RC + pad; H = 130 + len(rows) * (T + 110) + 120
im = Image.new("RGB", (W, H), (30, 31, 34)); d = ImageDraw.Draw(im)
d.text((pad, 34), "Treasure chest - texture maps (2048 px, PBR metal/rough)", font=FB, fill=(235, 235, 235))
for r, (pre, label) in enumerate(rows):
    y = 120 + r * (T + 110)
    for c, (k, kl) in enumerate(kinds):
        p = os.path.join(src, f"{pre}_{k}_2k.jpg"); x = pad + c * (T + pad)
        tile = Image.open(p).convert("RGB").resize((T, T), Image.LANCZOS); im.paste(tile, (x, y))
        d.text((x, y + T + 12), f"{pre}_{k}_2k.jpg", font=F, fill=(220, 220, 220)); d.text((x, y + T + 44), kl, font=F, fill=(150, 150, 150))
x0 = pad + len(kinds) * (T + pad)
def para(y, head, lines, width=40):
    d.text((x0, y), head, font=ImageFont.truetype(DJ + "DejaVuSans-Bold.ttf", 28), fill=(235, 235, 235)); y += 44
    for l in lines:
        for w_ in textwrap.wrap(l, width) or [""]:
            d.text((x0, y), w_, font=FS, fill=(195, 195, 195)); y += 31
        y += 6
    return y + 18
y = para(120, "Wood (planks, staves)", ["CC0 photo-scanned wood, colour-graded and baked into the base colour map.",
                                         "Normal strength 2.0; per-plank tone / roughness variation in the shader."])
y = para(120 + T + 110, "End grain (growth rings)", ["Procedural (make_endgrain.py): growth rings, rays and pores; used on plank end faces."])
y = para(y, "Procedural materials (no maps)", ["Aged brass: metallic 1.0, tarnish + patina noise, roughness 0.52-0.74, bump 0.5, polished edge wear (pointiness), cavity darkening (AO).",
                                                "Velvet lining: CC0 velour normal + roughness, micro-fibre sheen, piping cords, stitch line.",
                                                "Gold coins: metallic 1.0, roughness 0.22 (render only)."])
d.line([pad, H - 100, W - pad, H - 100], fill=(70, 70, 74))
d.text((pad, H - 82), "Attribution: 'Dark Wood' by Dario Barresi, Dimitrios Savva, Rico Cilliers and 'Velour Velvet' by colormass, Rico Cilliers - "
                      "Poly Haven (polyhaven.com), licensed CC0 (public domain).", font=FS, fill=(175, 175, 175))
im.save(out); print(out)
