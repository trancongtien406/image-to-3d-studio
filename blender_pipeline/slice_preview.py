"""Headless slicing proof: slice the print STL with PrusaSlicer CLI and draw a toolpath preview from the G-code
(system python3 + PIL; no GUI needed).

    python3 slice_preview.py --stl output/chest/chest_print_mm.stl --scale 25 --slicer /path/prusa-slicer \
        --out output/chest/slice   ->  chest_25pct.gcode, slice_preview.png, slice_report.json
"""
import json, math, os, re, subprocess, sys, time
from PIL import Image, ImageDraw, ImageFont

argv = sys.argv[1:]
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
STL, SCALE, SLICER, OUT = arg("--stl"), float(arg("--scale", "25")), arg("--slicer"), arg("--out")
os.makedirs(OUT, exist_ok=True)
G = os.path.join(OUT, f"chest_{SCALE:g}pct.gcode")
cfg = ["--layer-height", "0.2", "--first-layer-height", "0.2", "--nozzle-diameter", "0.4", "--filament-diameter", "1.75",
       "--bed-shape", "0x0,250x0,250x210,0x210", "--max-print-height", "210", "--center", "125,105",
       "--perimeters", "3", "--fill-density", "15%", "--fill-pattern", "gyroid", "--temperature", "215", "--bed-temperature", "60",
       "--support-material", "--support-material-threshold", "50", "--support-material-buildplate-only", "--skirts", "1",
       "--filament-type", "PLA", "--filament-density", "1.24"]
t = time.time()
if "--reuse" in argv and os.path.exists(G) and os.path.exists(G + ".secs"):
    slice_s = float(open(G + ".secs").read()); r = None
else:
  r = subprocess.run([SLICER, "--export-gcode", "--scale", f"{SCALE:g}%", *cfg, "--output", G, STL], capture_output=True, text=True)
  slice_s = time.time() - t; open(G + ".secs", "w").write(str(slice_s))
  print(r.stdout[-1500:], r.stderr[-1500:])
assert os.path.exists(G), "slicing failed"

# ---------------------------------------------------------------- parse
segs = []   # (z, x0, y0, x1, y1, type)
x = y = z = e = 0.0; typ = "?"; rel_e = False
stats = {}
for line in open(G):
    if line.startswith(";TYPE:"): typ = line[6:].strip(); continue
    if line.startswith(";"):
        mm = re.match(r"; (estimated printing time \(normal mode\)|filament used \[mm\]|filament used \[g\]|filament used \[cm3\]|total layers count|layer_height|fill_density|perimeters|nozzle_diameter|support_material) = (.*)", line)
        if mm: stats[mm.group(1)] = mm.group(2).strip()
        continue
    if line.startswith("M83"): rel_e = True
    if line.startswith("M82"): rel_e = False
    if not (line.startswith("G1") or line.startswith("G0")): continue
    p = dict((t_[0], float(t_[1:])) for t_ in line.split(";")[0].split()[1:] if t_[0] in "XYZE" and len(t_) > 1)
    nx, ny, nz = p.get("X", x), p.get("Y", y), p.get("Z", z)
    ext = ("E" in p) and ((p["E"] > 0) if rel_e else (p["E"] > e))
    if "E" in p and not rel_e: e = p["E"]
    if ext and (nx != x or ny != y): segs.append((nz, x, y, nx, ny, typ))
    x, y, z = nx, ny, nz
zs = sorted({s[0] for s in segs}); zmax = max(zs)
# layer accounting: PrusaSlicer prints support on its own (thicker, offset) layers; those Z levels are counted in
# "total layers" / ;LAYER_CHANGE but carry no object extrusion. Height must be checked on object layers only.
import collections
_isobj = lambda t_: not t_.startswith(("Support", "Skirt"))
ztypes = collections.defaultdict(set)
for s_ in segs: ztypes[round(s_[0], 3)].add(s_[5])
obj_z = sorted(q for q in ztypes if any(_isobj(t_) for t_ in ztypes[q])); sup_z = sorted(q for q in ztypes if q not in obj_z)
dz = collections.Counter(round(b - a, 3) for a, b in zip(obj_z, obj_z[1:]))
oxs = [v for s_ in segs if _isobj(s_[5]) for v in (s_[1], s_[3])]; oys = [v for s_ in segs if _isobj(s_[5]) for v in (s_[2], s_[4])]
EW = 0.45   # external perimeter extrusion width: toolpath centre lines sit EW/2 inside the true outline
layer_check = {"z_levels_total": len(zs), "object_layers": len(obj_z), "support_only_levels": len(sup_z),
               "object_layer_height_histogram_mm": {str(k): v for k, v in dz.most_common()},
               "first_support_only_z": sup_z[:6], "object_top_z_mm": max(obj_z),
               "object_xy_toolpath_mm": [round(max(oxs) - min(oxs), 2), round(max(oys) - min(oys), 2)],
               "object_xy_outline_mm": [round(max(oxs) - min(oxs) + EW, 2), round(max(oys) - min(oys) + EW, 2)],
               "explanation": ("%d Z levels = %d object layers x 0.2 mm (top at %.1f mm) + %d support-only levels interleaved at offset "
                               "heights (support is printed on its own layers because of the 0.2 mm contact distance). %d x 0.2 = %.1f mm is "
                               "therefore not the print height; the object height is %.1f mm." % (len(zs), len(obj_z), max(obj_z), len(sup_z), len(zs), len(zs) * 0.2, max(obj_z)))}
COL = {"Perimeter": (230, 160, 40), "External perimeter": (240, 110, 40), "Overhang perimeter": (40, 90, 230), "Internal infill": (170, 40, 40),
       "Solid infill": (150, 60, 160), "Top solid infill": (230, 60, 60), "Bridge infill": (70, 130, 200), "Gap fill": (250, 250, 250),
       "Skirt/Brim": (20, 160, 120), "Skirt": (20, 160, 120), "Support material": (40, 200, 60), "Support material interface": (30, 140, 40)}

# ---------------------------------------------------------------- draw: iso view (outer shell, coloured by height) + single layer
W, H = 2560, 1440
im = Image.new("RGB", (W, H), (34, 36, 40)); d = ImageDraw.Draw(im)
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26); fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
az, el = math.radians(35), math.radians(28)
xs = [s[1] for s in segs]; ys = [s[2] for s in segs]; cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
def iso(px, py, pz):
    X, Y = px - cx, py - cy
    u = X * math.cos(az) - Y * math.sin(az); v = X * math.sin(az) + Y * math.cos(az)
    return u, pz * math.cos(el) - v * math.sin(el), v
span = max(max(xs) - min(xs), max(ys) - min(ys), zmax) * 1.25; k = 1050 / span; ox, oy = 720, 1080
def heat(t_):
    stops = [(0, (40, 70, 200)), (0.5, (60, 200, 120)), (1, (250, 170, 40))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t_ <= b:
            q = (t_ - a) / (b - a); return tuple(int(ca[i] + (cb[i] - ca[i]) * q) for i in range(3))
    return stops[-1][1]
zi = {z_: i for i, z_ in enumerate(zs)}
shell = [s for s in segs if s[5] in ("External perimeter", "Overhang perimeter", "Support material", "Skirt/Brim", "Skirt", "Top solid infill")
         and (zi[s[0]] % 2 == 0 or s[5] == "Top solid infill")]
shell.sort(key=lambda s: s[0])
for (zz, x0, y0, x1, y1, ty) in shell:
    a = iso(x0, y0, zz); b = iso(x1, y1, zz)
    c = heat(zz / zmax) if ty not in ("Support material",) else (90, 220, 90)
    shade = 0.75 + 0.25 * math.cos(math.atan2(y1 - y0, x1 - x0) - az)
    d.line([(ox + a[0] * k, oy - a[1] * k), (ox + b[0] * k, oy - b[1] * k)], fill=tuple(int(ci * shade) for ci in c), width=2)
# single layer at ~45 % height, top-down, coloured by feature
zl = min(obj_z, key=lambda q: abs(q - zmax * 0.45))   # an object layer, not a support-only level
X0, Y1 = min(xs), max(ys)
lk = 1000 / max(max(xs) - min(xs), max(ys) - min(ys)); lx, ly = 1560, 260
d.rectangle([lx - 20, ly - 20, lx + 980, ly + 1000 * (max(ys) - min(ys)) / max(max(xs) - min(xs), max(ys) - min(ys)) + 20], fill=(24, 25, 28))
used = set()
for (zz, x0, y0, x1, y1, ty) in segs:
    if abs(zz - zl) > 1e-6: continue
    used.add(ty)
    d.line([(lx + (x0 - X0) * lk, ly + (Y1 - y0) * lk), (lx + (x1 - X0) * lk, ly + (Y1 - y1) * lk)], fill=COL.get(ty, (200, 200, 200)), width=2)
d.text((40, 30), f"PrusaSlicer {SCALE:g}% scale  -  sliced headless (CLI), toolpaths drawn from the exported G-code", font=fb, fill=(240, 240, 240))
info = [f"Model: {os.path.basename(STL)} at {SCALE:g}% (display / static one-piece print)",
        f"Object: {layer_check['object_layers']} layers x 0.2 mm = {layer_check['object_top_z_mm']:.1f} mm tall, "
        f"{layer_check['object_xy_outline_mm'][0]:.1f} x {layer_check['object_xy_outline_mm'][1]:.1f} mm footprint",
        f"(+{layer_check['support_only_levels']} support-only Z levels -> {len(zs)} G-code layers in total)",
        f"Perimeters {stats.get('perimeters', '3')}, gyroid infill {stats.get('fill_density', '15%')}", f"Print time: {stats.get('estimated printing time (normal mode)', '?')}",
        f"Filament: {stats.get('filament used [g]', '?')} g PLA ({float(stats.get('filament used [mm]', 0)) / 1000:.1f} m)", f"Slicing took {slice_s:.0f} s"]
for i, l in enumerate(info): d.text((40, 90 + i * 36), l, font=f, fill=(210, 210, 210))
d.text((lx, ly - 60), f"Layer at z = {zl:.1f} mm", font=f, fill=(220, 220, 220))
for i, ty in enumerate(sorted(used)):
    d.rectangle([lx + i % 3 * 330, H - 130 + i // 3 * 40, lx + i % 3 * 330 + 26, H - 110 + i // 3 * 40], fill=COL.get(ty, (200, 200, 200)))
    d.text((lx + i % 3 * 330 + 36, H - 134 + i // 3 * 40), ty, font=f, fill=(210, 210, 210))
d.text((40, H - 60), "Left: outer walls coloured by height (blue = bed, orange = top). Right: one layer by feature type.", font=f, fill=(170, 170, 170))
im.save(os.path.join(OUT, "slice_preview.png"))
rep = {"slicer": "PrusaSlicer 2.8.1 CLI (AppImage, headless)", "scale_pct": SCALE, "slice_seconds": round(slice_s, 1), "gcode": os.path.basename(G),
       "layers": len(zs), "layer_check": layer_check, "segments": len(segs), "gcode_stats": stats, "config": cfg}
json.dump(rep, open(os.path.join(OUT, "slice_report.json"), "w"), indent=2); print(json.dumps(rep["gcode_stats"], indent=1))
