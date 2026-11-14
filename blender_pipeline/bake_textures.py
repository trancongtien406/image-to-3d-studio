"""Bake the colour grade (hue/sat/value, same maths as Blender's Hue/Saturation node in linear space)
into real texture files, so GLB / FBX / OBJ exports carry the final look without node tricks."""
import colorsys, os, sys
import numpy as np
from PIL import Image

def srgb_to_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)

def grade(src, dst, hue, sat, val, size=2048):
    im = Image.open(src).convert("RGB").resize((size, size), Image.LANCZOS)
    a = srgb_to_lin(np.asarray(im).astype(np.float32) / 255.0)
    mx = a.max(-1); mn = a.min(-1); d = mx - mn
    h = np.zeros_like(mx); s = np.where(mx > 0, d / np.maximum(mx, 1e-8), 0); v = mx
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    nz = d > 1e-8
    hr = np.where(mx == r, ((g - b) / np.where(nz, d, 1)) % 6, 0)
    hg = np.where(mx == g, (b - r) / np.where(nz, d, 1) + 2, 0)
    hb = np.where(mx == b, (r - g) / np.where(nz, d, 1) + 4, 0)
    h = np.where(mx == r, hr, np.where(mx == g, hg, hb)) / 6.0
    h = np.where(nz, h, 0)
    h = (h + (hue - 0.5)) % 1.0; s = np.clip(s * sat, 0, 1); v = v * val
    i = np.floor(h * 6).astype(int) % 6; f = h * 6 - np.floor(h * 6)
    p = v * (1 - s); q = v * (1 - s * f); t = v * (1 - s * (1 - f))
    out = np.zeros_like(a)
    for k, (R, G, B) in enumerate(((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))):
        m = i == k
        out[..., 0][m], out[..., 1][m], out[..., 2][m] = R[m], G[m], B[m]
    Image.fromarray((np.clip(lin_to_srgb(out), 0, 1) * 255).astype(np.uint8)).save(dst, quality=92)

if __name__ == "__main__":
    src, dst, h, s, v = sys.argv[1:6]
    grade(src, dst, float(h), float(s), float(v))
