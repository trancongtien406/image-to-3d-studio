"""Side-by-side: reference photo vs Blender render from a matched camera (system python3 + PIL + numpy).
Round 4: both images are cropped to the object's bounding box (background = median of the border pixels) and scaled
so the chest has the SAME height and is centred in both panels -> size / framing normalised.

    python3 compare_reference.py ref.png render.png out.png [--gallery out_1280x769.jpg]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ref, ren, out = sys.argv[1:4]
GAL = sys.argv[sys.argv.index("--gallery") + 1] if "--gallery" in sys.argv else None

def bbox(im, thr=38):
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    border = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    m = np.abs(a - bg).sum(axis=2) > thr
    # ignore isolated noise: keep rows/cols with a meaningful fraction of object pixels
    rows = np.where(m.sum(axis=1) > m.shape[1] * 0.01)[0]; cols = np.where(m.sum(axis=0) > m.shape[0] * 0.01)[0]
    return cols[0], rows[0], cols[-1], rows[-1], tuple(int(c) for c in bg)

def normalised(path, S, obj_h, bgfill):
    im = Image.open(path).convert("RGB"); x0, y0, x1, y1, bg = bbox(im)
    crop = im.crop((x0, y0, x1 + 1, y1 + 1)); k = obj_h / crop.height
    crop = crop.resize((max(1, int(crop.width * k)), int(obj_h)), Image.LANCZOS)
    if crop.width > S * 0.92:   # very wide object: fit width instead
        k2 = S * 0.92 / crop.width; crop = crop.resize((int(crop.width * k2), int(crop.height * k2)), Image.LANCZOS)
    pan = Image.new("RGB", (S, S), bg); pan.paste(crop, ((S - crop.width) // 2, (S - crop.height) // 2))
    return pan, (x1 - x0, y1 - y0)

S = 1200
a, ba = normalised(ref, S, S * 0.70, None); b, bb = normalised(ren, S, S * 0.70, None)
im = Image.new("RGB", (2 * S + 60, S + 120), (30, 31, 34)); im.paste(a, (20, 100)); im.paste(b, (S + 40, 100))
d = ImageDraw.Draw(im); f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
d.text((20, 30), "Reference (input image)", font=f, fill=(235, 235, 235)); d.text((S + 40, 30), "Blender model, matched camera (Cycles)", font=f, fill=(235, 235, 235))
fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
d.text((20, S + 106 - 30), "Both panels cropped to the object and scaled to the same chest height (70 % of panel).", font=fs, fill=(170, 170, 170))
im.save(out); print(out, "ref bbox", ba, "render bbox", bb)
if GAL:   # 1280x769 gallery comp, minimal text
    from PIL import ImageFont as IF
    P = "/usr/share/fonts/truetype/sand-box/google/Poppins/"
    g = Image.new("RGB", (1280, 769), (24, 25, 28)); s2 = 600
    g.paste(a.resize((s2, s2), Image.LANCZOS), (27, 120)); g.paste(b.resize((s2, s2), Image.LANCZOS), (1280 - 27 - s2, 120))
    dg = ImageDraw.Draw(g)
    try: ft = IF.truetype(P + "Poppins-SemiBold.ttf", 40); fl = IF.truetype(P + "Poppins-Medium.ttf", 22)
    except Exception: ft = fl = f
    t = "REFERENCE VS 3D RESULT"; w = dg.textlength(t, font=ft); dg.text(((1280 - w) / 2, 34), t, font=ft, fill=(240, 236, 228))
    for x, lab in ((27, "Reference"), (1280 - 27 - s2, "3D model")):
        dg.text((x + 12, 120 + s2 - 40), lab, font=fl, fill=(240, 236, 228))
    g.save(GAL, quality=92); print(GAL)
