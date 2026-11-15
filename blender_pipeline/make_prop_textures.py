"""Procedural texture maps for the prop samples (system python3 + numpy/scipy/PIL). Original work, MIT like this repo.

    python3 make_prop_textures.py            -> textures_generated/*.jpg|png
Maps: cork (Diffuse/Rough/nor_gl), label atlas (Diffuse/Rough, 4 labels), black enamel iron with wear (Diffuse/Rough/nor_gl/Metal).
"""
import os, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter, sobel
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures_generated"); os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)

def fbm(n, octaves=6, base=4, seed=0, persist=0.55):
    """Periodic (seamlessly tiling) fractal noise via spectral synthesis; base ~ lowest feature frequency."""
    r = np.random.default_rng(seed); fx = np.fft.fftfreq(n) * n; f = np.sqrt(fx[:, None] ** 2 + fx[None, :] ** 2)
    beta = -np.log2(persist) + 1.0
    amp = np.where(f >= base * 0.5, 1.0 / np.maximum(f, 1e-6) ** beta, 0.0); amp[f > base * 2 ** octaves] = 0
    spec = amp * np.exp(2j * np.pi * r.random((n, n))); a = np.real(np.fft.ifft2(spec))
    return (a - a.min()) / (np.ptp(a) + 1e-9)

def tile(a, k=None):
    return a   # all inputs are periodic already (spectral noise, wrap-mode filters)

def normal_from_height(h, strength=4.0):
    dx = sobel(h, 1, mode='wrap') * strength; dy = sobel(h, 0, mode='wrap') * strength
    nz = np.ones_like(h); l = np.sqrt(dx * dx + dy * dy + 1)
    n = np.stack([-dx / l, dy / l, nz / l], -1)                  # OpenGL (+Y up)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)

def save(a, name, mode="RGB"):
    p = os.path.join(OUT, name)
    a = np.clip(a, 0, 255).astype(np.uint8)
    Image.fromarray(a, mode if a.ndim == 3 else "L").save(p, quality=92); print(p)

N = 1024
# ---------------------------------------------------------------- cork
h = tile(fbm(N, 7, 8, 1) * 0.6 + gaussian_filter(rng.random((N, N)), 1.2, mode='wrap') * 0.4)
pits = gaussian_filter((rng.random((N, N)) > 0.985).astype(float), 1.5, mode='wrap'); pits = tile(pits / pits.max())
hh = h - pits * 0.8
c0 = np.array([0.50, 0.33, 0.18]); c1 = np.array([0.80, 0.62, 0.40])
col = c0 + (c1 - c0) * np.clip(hh, 0, 1)[..., None]
save(col * 255, "cork_Diffuse_1k.jpg"); save((0.75 + 0.2 * (1 - hh)) * 255, "cork_Rough_1k.jpg")
save(normal_from_height(hh, 3.0), "cork_nor_gl_1k.jpg")

# ---------------------------------------------------------------- black enamel iron (painted, worn to dark steel + rust)
paint = tile(fbm(N, 7, 3, 11))
wear = tile(fbm(N, 6, 14, 12)); rust = tile(fbm(N, 6, 10, 13))
scr = np.zeros((N, N)); im = Image.fromarray(scr.astype(np.uint8)); d = ImageDraw.Draw(im)
for _ in range(220):
    x, y = rng.integers(0, N, 2); L = rng.integers(10, 70); a = rng.uniform(0, np.pi)
    d.line([x, y, x + L * np.cos(a), y + L * np.sin(a)], fill=int(rng.integers(90, 200)), width=1)
scr = np.asarray(im, float) / 255  # scratches drawn inside the tile (not seam-critical)
chip = np.clip((wear - 0.74) * 7, 0, 1); rmask = np.clip((rust - 0.72) * 5, 0, 1) * (0.5 + chip)
blk = np.array([0.028, 0.026, 0.025]) * (0.8 + 0.4 * paint[..., None])
steel = np.array([0.20, 0.19, 0.18]); rustc = np.array([0.23, 0.10, 0.04])
col = blk * (1 - chip[..., None]) + steel * chip[..., None]
col = col * (1 - np.clip(scr, 0, 1)[..., None] * 0.5) + steel * np.clip(scr, 0, 1)[..., None] * 0.5
col = col * (1 - np.clip(rmask, 0, 1)[..., None]) + rustc * (0.7 + 0.6 * rust[..., None]) * np.clip(rmask, 0, 1)[..., None]
srgb = lambda x: np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.clip(x, 0, None), 1 / 2.4) - 0.055)
save(srgb(col) * 255, "iron_enamel_Diffuse_1k.jpg")
rough = 0.42 + 0.15 * paint - 0.1 * chip + 0.45 * np.clip(rmask, 0, 1); save(np.clip(rough, 0, 1) * 255, "iron_enamel_Rough_1k.jpg")
metal = np.clip(chip + np.clip(scr, 0, 1) * 0.6, 0, 1) * (1 - np.clip(rmask, 0, 1)); save(metal * 255, "iron_enamel_Metal_1k.jpg")
hgt = paint * 0.3 - chip * 0.6 + rmask * 0.5 + gaussian_filter(rng.random((N, N)), 0.8, mode='wrap') * 0.15
save(normal_from_height(tile(hgt), 2.5), "iron_enamel_nor_gl_1k.jpg")

# ---------------------------------------------------------------- label atlas: 2 x 2 labels, aged paper, own typography
W, H = 2048, 1024; atlas = Image.new("RGB", (W, H)); rough_a = Image.new("L", (W, H))
SER = "/usr/share/fonts/truetype/dejavu/DejaVuSerif%s.ttf"
F = lambda s, b=True: ImageFont.truetype(SER % ("-Bold" if b else ""), s)
labels = [("ELIXIR", "No. 1", "VITAE"), ("TONIC", "No. 2", "AMARA"), ("ANTIDOTE", "No. 3", "UNIVERSALIS"), ("MANA", "No. 4", "ESSENTIA")]
for i, (big, num, sub) in enumerate(labels):
    cw, ch = W // 2, H // 2; ox, oy = (i % 2) * cw, (i // 2) * ch
    p = fbm(512, 6, 4, 30 + i); stain = gaussian_filter(rng.random((512, 512)), 18); stain = (stain - stain.min()) / np.ptp(stain)
    base = np.array([0.93, 0.86, 0.70]) * (0.88 + 0.12 * p[..., None]) - np.array([0.10, 0.14, 0.20]) * np.clip(stain - 0.55, 0, 1)[..., None] * 2
    yy, xx = np.mgrid[0:512, 0:512] / 511.0; edge = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) * 9, 0, 1) ** 0.6
    base = base * (0.75 + 0.25 * edge[..., None])
    lab = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8)).resize((cw, ch), Image.BICUBIC)
    dd = ImageDraw.Draw(lab); ink = (58, 38, 22); m = 34
    dd.rectangle([m, m, cw - m, ch - m], outline=ink, width=6); dd.rectangle([m + 16, m + 16, cw - m - 16, ch - m - 16], outline=ink, width=2)
    def ctext(t, y, f):
        w = dd.textlength(t, font=f); dd.text(((cw - w) / 2, y), t, font=f, fill=ink)
    ctext(num, 80, F(44, False)); f = F(140)
    while dd.textlength(big, font=f) > cw - 150: f = F(f.size - 6)
    ctext(big, 185 - (f.size - 110) // 3, f); ctext("· " + sub + " ·", 365, F(48, False))
    dd.line([cw * 0.25, 160, cw * 0.75, 160], fill=ink, width=3); dd.line([cw * 0.25, 350, cw * 0.75, 350], fill=ink, width=3)
    lab = lab.filter(ImageFilter.GaussianBlur(0.6)); atlas.paste(lab, (ox, oy))
    r = Image.fromarray((np.clip(0.82 + 0.1 * p, 0, 1) * 255).astype(np.uint8)).resize((cw, ch)); rough_a.paste(r, (ox, oy))
atlas.save(os.path.join(OUT, "labels_Diffuse_2k.jpg"), quality=93); rough_a.save(os.path.join(OUT, "labels_Rough_2k.jpg"), quality=92)
print("labels atlas", atlas.size)
