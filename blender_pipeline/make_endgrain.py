"""Procedural end-grain texture set (growth rings + medullary rays + pores), tileable enough for plank ends.
Writes <prefix>_Diffuse_2k.jpg, _nor_gl_2k.jpg, _Rough_2k.jpg.   python3 make_endgrain.py OUTDIR PREFIX"""
import sys, os, numpy as np
from PIL import Image, ImageFilter
out, pre = sys.argv[1], sys.argv[2]; N = 2048
rng = np.random.default_rng(11)
y, x = np.mgrid[0:N, 0:N].astype(np.float32) / N

def fbm(n_oct=5, base=4):
    acc = np.zeros((N, N), np.float32); amp = 1.0
    for o in range(n_oct):
        f = base * 2 ** o; g = rng.standard_normal((f + 1, f + 1)).astype(np.float32)
        im = Image.fromarray(g).resize((N, N), Image.BICUBIC)
        acc += amp * np.asarray(im); amp *= 0.5
    return acc / 2.0

# pith off the tile (boards are cut from the outer part of the log) -> gently curved rings
cx, cy = -0.12, 1.08
r = np.hypot(x - cx, y - cy) * 34.0 + fbm(4, 3) * 0.3
ring = r - np.floor(r)
late = np.clip((ring - 0.62) / 0.3, 0, 1) ** 1.6           # dark latewood band
ang = np.arctan2(y - cy, x - cx)
rays = (np.abs(np.sin(ang * 340 + fbm(3, 8) * 2)) > 0.985).astype(np.float32) * 0.5
pores = (rng.random((N, N)) > 0.985).astype(np.float32) * (1 - late)
pores = np.asarray(Image.fromarray((pores * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
tone = 0.62 + 0.25 * fbm(5, 6)
v = np.clip(tone - 0.42 * late - 0.25 * pores + 0.08 * rays, 0, 1)
base_light = np.array([0.36, 0.25, 0.15]); base_dark = np.array([0.10, 0.065, 0.04])
rgb = base_dark + (base_light - base_dark) * v[..., None]
Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, f"{pre}_Diffuse_2k.jpg"), quality=92)
h = 0.6 * late + 0.8 * pores - 0.2 * rays + 0.15 * fbm(3, 30)
hk = np.array([1, 4, 6, 4, 1], np.float32); hk /= hk.sum()
for ax in (0, 1): h = np.apply_along_axis(lambda m: np.convolve(m, hk, mode="same"), ax, h)
gy, gx = np.gradient(h); s = 18.0
n = np.dstack([-gx * s, gy * s, np.ones_like(h)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(out, f"{pre}_nor_gl_2k.jpg"), quality=92)
rough = np.clip(0.72 + 0.18 * late + 0.1 * pores, 0, 1)
Image.fromarray((rough * 255).astype(np.uint8)).save(os.path.join(out, f"{pre}_Rough_2k.jpg"), quality=92)
print("endgrain ok")
