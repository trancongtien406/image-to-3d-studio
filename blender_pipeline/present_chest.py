"""Round 4 chest presentation (system python3 + PIL): 1280x769 gallery comps + topology sheet.

    python3 present_chest.py --ren RENDERDIR --out OUTDIR --ref chest_input.png --stats model_stats.json --uv DIR
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont
argv = sys.argv[1:]
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
REN, OUT, REF, ST, UV = arg("--ren"), arg("--out"), arg("--ref"), arg("--stats"), arg("--uv")
os.makedirs(OUT, exist_ok=True)
P = "/usr/share/fonts/truetype/sand-box/google/Poppins/"
F = lambda w, s: ImageFont.truetype(P + f"Poppins-{w}.ttf", s)
DJ = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if b else ""), s)
GW, GH = 1280, 769

def cover(im, w, h, fx=0.5, fy=0.5):
    k = max(w / im.width, h / im.height); im = im.resize((int(im.width * k + 0.5), int(im.height * k + 0.5)), Image.LANCZOS)
    x = int((im.width - w) * fx); y = int((im.height - h) * fy); return im.crop((x, y, x + w, y + h))

def title_bar(g, text, y=0, h=92):
    d = ImageDraw.Draw(g, "RGBA"); d.rectangle([0, y, GW, y + h], fill=(18, 18, 20, 205))
    f = F("SemiBold", 40); w = d.textlength(text, font=f); d.text(((GW - w) / 2, y + (h - 52) / 2), text, font=f, fill=(242, 236, 226))

# 1) hero 3/4 + reference inset
g = cover(Image.open(os.path.join(REN, "chest_three_quarter.png")).convert("RGB"), GW, GH, 0.5, 0.55)
title_bar(g, "REFERENCE TO DETAILED 3D MODEL")
ref = Image.open(REF).convert("RGB"); ref = ref.resize((250, 250), Image.LANCZOS)
d = ImageDraw.Draw(g); d.rectangle([GW - 290, GH - 290, GW - 30, GH - 30], fill=(240, 236, 228)); g.paste(ref, (GW - 285, GH - 285))
d.text((GW - 285, GH - 325), "Reference", font=F("Medium", 22), fill=(242, 236, 226))
g.save(os.path.join(OUT, "gallery_1_reference_to_3d.jpg"), quality=92)
# 2) open lid
g = cover(Image.open(os.path.join(REN, "chest_open.png")).convert("RGB"), GW, GH, 0.5, 0.5)
title_bar(g, "OPEN LID, FULLY MODELLED INTERIOR", y=GH - 92)
g.save(os.path.join(OUT, "gallery_2_open_lid.jpg"), quality=92)

# topology sheet
names = [("chest_wire_full.png", "Full model"), ("chest_wire_lid_curve.png", "Lid curvature (side)"), ("chest_wire_corner.png", "Corner caps"),
         ("chest_wire_hinge.png", "Rear hinge"), ("chest_wire_latch.png", "Hasp + lock"), ("chest_topology.png", "Open lid / lining")]
TW, TH = 800, 450; pad = 24; cols = 3
sheet = Image.new("RGB", (cols * TW + (cols + 1) * pad + 760, 2 * TH + 3 * pad + 120), (28, 29, 32)); d = ImageDraw.Draw(sheet)
d.text((pad, 30), "Topology, polycount and UVs  -  wireframe over clay (Cycles)", font=DJ(38, True), fill=(240, 240, 240))
for i, (fn, lab) in enumerate(names):
    p = os.path.join(REN, fn)
    if not os.path.exists(p): continue
    t = cover(Image.open(p).convert("RGB"), TW, TH); x = pad + (i % cols) * (TW + pad); y = 110 + (i // cols) * (TH + pad)
    sheet.paste(t, (x, y)); d.rectangle([x, y + TH - 44, x + TW, y + TH], fill=(20, 20, 22)); d.text((x + 14, y + TH - 38), lab, font=DJ(24), fill=(235, 235, 235))
X = cols * (TW + pad) + pad + 10
st = json.load(open(ST)); y = 110
d.text((X, y), "Polycount (triangles)", font=DJ(28, True), fill=(240, 240, 240)); y += 44
for k, v in st["objects"].items():
    d.text((X, y), k, font=DJ(21), fill=(210, 210, 210)); d.text((X + 470, y), f"{v['tris']:>8,}", font=DJ(21), fill=(210, 210, 210)); y += 30
d.line([X, y + 4, X + 700, y + 4], fill=(90, 90, 90)); y += 12
d.text((X, y), "Total", font=DJ(22, True), fill=(240, 240, 240)); d.text((X + 470, y), f"{st['total_tris']:>8,}", font=DJ(22, True), fill=(240, 240, 240)); y += 50
uvs = [f for f in ("uv_body_wood.png", "uv_lid_wood.png") if UV and os.path.exists(os.path.join(UV, f))]
for fn in uvs:
    u = Image.open(os.path.join(UV, fn)).convert("RGBA"); bgc = Image.new("RGBA", u.size, (238, 238, 238, 255)); bgc.alpha_composite(u)
    u = bgc.convert("RGB").resize((330, 330), Image.LANCZOS); sheet.paste(u, (X + (uvs.index(fn)) * 350, y + 34))
    d.text((X + uvs.index(fn) * 350, y), fn.replace(".png", "").replace("uv_", "UV: ").replace("_", " "), font=DJ(21), fill=(210, 210, 210))
sheet.save(os.path.join(OUT, "chest_topology_sheet.png")); print("present ok")
