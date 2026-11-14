"""Rasterise Blender's UV-layout SVG (polygons) to PNG with PIL (headless Blender cannot export PNG layouts without a GPU).
    python3 uv_svg2png.py in.svg out.png"""
import re, sys
from PIL import Image, ImageDraw
src, out = sys.argv[1:3]; s = open(src).read()
W = int(re.search(r'width="(\d+)"', s).group(1)); H = int(re.search(r'height="(\d+)"', s).group(1))
# wood uses tiling box-projected UVs (texel density fixed in metres), so islands extend over several 0-1 tiles:
# fit the whole layout and draw the 0-1 tile grid
polys = [[tuple(float(c) for c in p.split(",")) for p in m.group(1).split()] for m in re.finditer(r'points="([^"]+)"', s)]
polys = [q for q in polys if len(q) >= 3]
xs = [x for q in polys for x, _ in q]; ys = [y for q in polys for _, y in q]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); k = 0.94 * min(W / (x1 - x0), H / (y1 - y0))
ox, oy = (W - (x1 - x0) * k) / 2 - x0 * k, (H - (y1 - y0) * k) / 2 - y0 * k
im = Image.new("RGB", (W, H), (245, 245, 245)); d = ImageDraw.Draw(im)
import math
for t in range(math.floor(x0 / W), math.ceil(x1 / W) + 1): d.line([(ox + t * W * k, 0), (ox + t * W * k, H)], fill=(200, 120, 60), width=2)
for t in range(math.floor(y0 / H), math.ceil(y1 / H) + 1): d.line([(0, oy + t * H * k), (W, oy + t * H * k)], fill=(200, 120, 60), width=2)
n = 0
for q in polys:
    d.polygon([(ox + x * k, oy + y * k) for x, y in q], fill=(205, 215, 230), outline=(40, 50, 70)); n += 1
d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0), width=3)
im.save(out); print(out, n, "faces")
