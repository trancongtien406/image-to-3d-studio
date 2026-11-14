"""Round 5 chest presentation (system python3 + PIL): 1280x769 gallery comps + topology sheet.

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

def header(text, h=78, bg=(24, 24, 27)):
    """Separate header strip (never drawn over the model)."""
    g = Image.new("RGB", (GW, h), bg); d = ImageDraw.Draw(g); f = F("SemiBold", 34)
    w = d.textlength(text, font=f); d.text(((GW - w) / 2, (h - 46) / 2), text, font=f, fill=(242, 236, 226)); return g

def model_bbox(im):
    """Bounding box of the (saturated wood/brass) model on the grey studio backdrop."""
    import numpy as np
    s_ = np.asarray(im.convert("HSV"))[..., 1] > 70
    ys, xs = np.where(s_); return xs.min(), ys.min(), xs.max(), ys.max()

def fit_model(im, w, h, model_h, cx, cy=None):
    """Scale so the model is model_h px tall, centred at (cx, cy); extend the smooth backdrop by edge padding."""
    import numpy as np
    x0, y0, x1, y1 = model_bbox(im); k = model_h / (y1 - y0 + 1); cy = h / 2 if cy is None else cy
    P_ = 900; a = np.pad(np.asarray(im.convert("RGB")), ((P_, P_), (P_, P_), (0, 0)), mode="edge")
    big = Image.fromarray(a).resize((int(a.shape[1] * k), int(a.shape[0] * k)), Image.LANCZOS)
    mx, my = ((x0 + x1) / 2 + P_) * k, ((y0 + y1) / 2 + P_) * k
    ox, oy = int(mx - cx), int(my - cy); out = big.crop((ox, oy, ox + w, oy + h))
    bb = (x0 * k + P_ * k - ox, y0 * k + P_ * k - oy, x1 * k + P_ * k - ox, y1 * k + P_ * k - oy)
    print("model bbox in panel:", [int(v) for v in bb], "panel", (w, h)); return out

def compose(render, text, model_h, cx=GW / 2, h=78):
    g = Image.new("RGB", (GW, GH)); g.paste(header(text, h), (0, 0))
    g.paste(fit_model(render, GW, GH - h, model_h, cx), (0, h)); return g, h

def title_bar(g, text, y=0, h=92):
    d = ImageDraw.Draw(g, "RGBA"); d.rectangle([0, y, GW, y + h], fill=(18, 18, 20, 205))
    f = F("SemiBold", 40); w = d.textlength(text, font=f); d.text(((GW - w) / 2, y + (h - 52) / 2), text, font=f, fill=(242, 236, 226))

# 1) hero 3/4 + reference inset
INS = 225; side = arg("--inset", "right")
g, hh = compose(Image.open(os.path.join(REN, "chest_three_quarter.png")).convert("RGB"), "FROM REFERENCE TO DETAILED 3D MODEL",
                int(arg("--mh1", "600")), cx=float(arg("--cx1", "505")))
ref = Image.open(REF).convert("RGB"); ref = ref.resize((INS, INS), Image.LANCZOS)
x0 = GW - INS - 36 if side == "right" else 32; y0 = GH - INS - 32
d = ImageDraw.Draw(g); d.rectangle([x0 - 4, y0 - 4, x0 + INS + 4, y0 + INS + 4], fill=(240, 236, 228)); g.paste(ref, (x0, y0))
d.rectangle([x0 - 4, y0 - 34, x0 + 110, y0 - 4], fill=(24, 24, 27)); d.text((x0 + 4, y0 - 33), "Reference", font=F("Medium", 19), fill=(242, 236, 226))
g.save(os.path.join(OUT, "gallery_1_reference_to_3d.jpg"), quality=92)
# 2) open lid
g, hh = compose(Image.open(os.path.join(REN, "chest_open.png")).convert("RGB"), "OPEN LID, FULLY MODELLED INTERIOR",
                int(arg("--mh2", "620")))
g.save(os.path.join(OUT, "gallery_2_open_lid.jpg"), quality=92)

# topology sheet
names = [("chest_wire_full.png", "Full model"), ("chest_wire_lid_curve.png", "Lid curvature (side)"), ("chest_wire_corner.png", "Corner caps"),
         ("chest_wire_hinge.png", "Rear hinge"), ("chest_wire_latch.png", "Hasp + lock"), ("chest_topology.png", "Open lid / lining")]
TW, TH = 800, 450; pad = 24; cols = 3
sheet = Image.new("RGB", (cols * TW + (cols + 1) * pad + 760, 2 * TH + 3 * pad + 120), (28, 29, 32)); d = ImageDraw.Draw(sheet)
d.text((pad, 30), "TOPOLOGY, POLYCOUNT & WOOD UVs  -  wireframe over clay (Cycles)", font=DJ(38, True), fill=(240, 240, 240))
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
yn = y + 34 + 330 + 30
for l in ("UV maps shown are for the wood (body + lid), which uses", "image textures. Brass, velvet lining and coins are",
          "procedural materials, so they need no texture UVs."):
    d.text((X, yn), l, font=DJ(21), fill=(190, 190, 190)); yn += 30
sheet.save(os.path.join(OUT, "chest_topology_sheet.png")); print("present ok")
