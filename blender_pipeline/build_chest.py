"""Parts-based treasure chest, modelled procedurally from the reference photo
(examples/models/chest/chest_input.png). Real-world size: 60 x 40 x 43 cm.

    blender -b -P build_chest.py -- --out OUTDIR [--renders RENDERDIR] [--samples 128] [--turntable]
"""
import math, os, sys, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
from common import *

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "output/chest"); REN = arg("--renders", OUT)
SAMPLES = int(arg("--samples", "128")); TT = "--turntable" in argv; SKIP = "--no-stills" in argv
PCT = int(arg("--pct", "100"))
os.makedirs(OUT, exist_ok=True); os.makedirs(REN, exist_ok=True)
rnd = random.Random(7)

sc = reset_scene()
C = bpy.data.collections.new("Chest"); sc.collection.children.link(C)

# ---------------------------------------------------------------- dimensions (metres)
W, D, HB = 0.60, 0.40, 0.27       # body width, depth, body height
S = 0.16                          # lid rise (sagitta)
T = 0.022                         # plank thickness
c = D / 2
R = (c * c + S * S) / (2 * S)     # lid arc radius
ZC = HB + S - R                   # arc centre height
AMAX = math.asin(c / R)
BAND_T, BAND_W = 0.007, 0.05     # metal strap thickness / width

# colour grade baked into real files (exporters cannot carry Hue/Sat nodes)
import shutil, subprocess
def grade(src, dst, h, s_, v):  # Blender's bundled Python has no Pillow -> run the baker with the system Python
    subprocess.run(["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bake_textures.py"), src, dst, str(h), str(s_), str(v)], check=True)
TEXD = os.path.join(OUT, "textures"); os.makedirs(TEXD, exist_ok=True)
grade(tex_path("dark_wood", "Diffuse"), os.path.join(TEXD, "chest_wood_Diffuse_2k.jpg"), 0.52, 0.95, 0.72)
grade(tex_path("dark_wood", "Diffuse"), os.path.join(TEXD, "chest_woodend_Diffuse_2k.jpg"), 0.515, 0.85, 0.35)
for k in ("nor_gl", "Rough"):
    shutil.copy(tex_path("dark_wood", k), os.path.join(TEXD, f"chest_wood_{k}_2k.jpg"))
    shutil.copy(tex_path("dark_wood", k), os.path.join(TEXD, f"chest_woodend_{k}_2k.jpg"))
import common
common.ASSETS_TEX_OVERRIDE = TEXD
wood = pbr_material("Wood_Oak_Aged", tex="chest_wood", rough=0.6, normal_strength=1.0)
wood_end = pbr_material("Wood_EndGrain", tex="chest_woodend", rough=0.7)
brass = pbr_material("Brass_Hammered", color=(0.78, 0.53, 0.17), rough=0.36, metal=1.0, bump=0.35)
dark = pbr_material("Keyhole_Dark", color=(0.02, 0.015, 0.01), rough=0.8)
parts = []

def P(o, mat, bev=0.0025, segs=2, long_axis=0, uv=True):
    if uv: uv_box(o, scale=1.4, long_axis=long_axis, rnd=rnd)
    set_mat(o, mat)
    if bev: bevel(o, bev, segs)
    o.parent = None
    if o.name not in C.objects:
        for col in o.users_collection: col.objects.unlink(o)
        C.objects.link(o)
    parts.append(o); return o

# ---------------------------------------------------------------- body planks
n_front = 4; ph = HB / n_front; gap = 0.0025
for i in range(n_front):
    z = ph * (i + 0.5)
    jit = lambda: rnd.uniform(-0.0012, 0.0012)
    # front/back are made of two staggered planks per row (as in the photo)
    split = rnd.uniform(-0.12, 0.12)
    for side, y in (("F", -D / 2 + T / 2), ("B", D / 2 - T / 2)):
        xa, xb = -W / 2 + T, W / 2 - T
        for k, (a, b) in enumerate(((xa, split - gap / 2), (split + gap / 2, xb))):
            P(box(f"Plank_{side}{i}{k}", (b - a, T + jit(), ph - gap), ((a + b) / 2, y + jit(), z)), wood)
    for side, x in (("L", -W / 2 + T / 2), ("R", W / 2 - T / 2)):
        P(box(f"Plank_{side}{i}", (T, D, ph - gap), (x, 0, z)), wood, long_axis=1)
P(box("Bottom", (W - 0.004, D - 0.004, T), (0, 0, T / 2)), wood)
P(box("Core", (W - 2 * T + 0.002, D - 2 * T + 0.002, HB - 0.004), (0, 0, HB / 2)), wood_end, bev=0)

# ---------------------------------------------------------------- lid: curved staves + end caps
def arc_stave(name, a0, a1, r_in, r_out, x0, x1, segs=6):
    v, f = [], []
    for j in range(segs + 1):
        a = a0 + (a1 - a0) * j / segs
        for r in (r_in, r_out):
            for x in (x0, x1):
                v.append((x, -r * math.sin(a), ZC + r * math.cos(a)))
    # vertex index helper
    idx = lambda j, ri, xi: j * 4 + ri * 2 + xi
    for j in range(segs):
        f.append((idx(j, 1, 0), idx(j + 1, 1, 0), idx(j + 1, 1, 1), idx(j, 1, 1)))  # outer
        f.append((idx(j, 0, 1), idx(j + 1, 0, 1), idx(j + 1, 0, 0), idx(j, 0, 0)))  # inner
        f.append((idx(j, 0, 0), idx(j + 1, 0, 0), idx(j + 1, 1, 0), idx(j, 1, 0)))  # x0 side
        f.append((idx(j, 1, 1), idx(j + 1, 1, 1), idx(j + 1, 0, 1), idx(j, 0, 1)))  # x1 side
    f.append((idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)))
    f.append((idx(segs, 0, 1), idx(segs, 1, 1), idx(segs, 1, 0), idx(segs, 0, 0)))
    o = mesh_obj(name, v, f)
    o.data.flip_normals() if False else None
    return o

ns = 5; ga = math.radians(0.35)
for i in range(ns):
    a0 = -AMAX + 2 * AMAX * i / ns + ga; a1 = -AMAX + 2 * AMAX * (i + 1) / ns - ga
    o = arc_stave(f"LidStave{i}", a0, a1, R - T, R, -W / 2 + T, W / 2 - T)
    P(o, wood)

def lid_cap(name, x0, x1, r):
    v, f = [], []
    segs = 24
    for j in range(segs + 1):
        a = -AMAX + 2 * AMAX * j / segs
        v.append((x0, -r * math.sin(a), ZC + r * math.cos(a)))
    n = len(v)
    for p in list(v): v.append((x1, p[1], p[2]))
    f.append(tuple(range(n)))[::-1] if False else None
    f.append(tuple(reversed(range(n))))
    f.append(tuple(range(n, 2 * n)))
    for j in range(n - 1):
        f.append((j, j + 1, n + j + 1, n + j))
    f.append((n - 1, 0, n, 2 * n - 1))
    o = mesh_obj(name, v, f)
    return o

def clip(poly, z0, z1):
    def cut(pts, keep, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ka, kb = keep(a), keep(b)
            if kb:
                if not ka: out.append(inter(a, b))
                out.append(b)
            elif ka: out.append(inter(a, b))
        return out
    def iz(zc):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (zc - a[1]) / (b[1] - a[1]), zc)
    p = cut(poly, lambda q: q[1] >= z0, iz(z0))
    return cut(p, lambda q: q[1] <= z1, iz(z1)) if p else p

def cap_boards(prefix, x0, x1, r, nb=3, gapz=0.0025):
    prof = [(-r * math.sin(-AMAX + 2 * AMAX * j / 32), ZC + r * math.cos(-AMAX + 2 * AMAX * j / 32)) for j in range(33)]
    top = ZC + r
    for b in range(nb):
        z0 = HB + (top - HB) * b / nb + (gapz / 2 if b else 0); z1 = HB + (top - HB) * (b + 1) / nb - (gapz / 2 if b < nb - 1 else 0)
        pl = clip(prof, z0, z1)
        if len(pl) < 3: continue
        n = len(pl)
        v = [(x0, y, z) for y, z in pl] + [(x1, y, z) for y, z in pl]
        f = [tuple(reversed(range(n))), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        o = mesh_obj(f"{prefix}{b}", v, f)
        o.data.validate(); o.data.update()
        # make normals consistent (outward)
        import bmesh
        bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(o.data); bm.free()
        P(o, wood, long_axis=1)

cap_boards("LidCapL", -W / 2, -W / 2 + T, R - 0.0005)
cap_boards("LidCapR", W / 2 - T, W / 2, R - 0.0005)
# fix cap normals if inverted
for o in parts[-2:]:
    bpy.context.view_layer.objects.active = o
P(lid_cap("LidCore", -W / 2 + T, W / 2 - T, R - T + 0.001), wood_end, bev=0)

# ---------------------------------------------------------------- metal: straps, rims, corners, rivets
rivets = []
def rivet(x, y, z, normal, r=0.0062, h=0.0045):
    o = dome(f"Rivet{len(rivets)}", r, h, (0, 0, 0), segs=20, rings=6)
    o.rotation_euler = Vector(normal).to_track_quat("Z", "Y").to_euler()
    o.location = (x, y, z)
    rivets.append(o); P(o, brass, bev=0, uv=False)
    shade_smooth(o, 80)

def lid_strap(name, x, w=BAND_W, segs=40):
    a0, a1 = -AMAX - 0.0, AMAX + 0.0
    o = arc_stave(name, a0, a1, R - 0.0005, R + BAND_T, x - w / 2, x + w / 2, segs=segs)
    P(o, brass, bev=0.0016, uv=False); shade_smooth(o, 30)
    for k in range(5):
        a = -AMAX + 2 * AMAX * (k + 0.5) / 5
        rivet(x, -(R + BAND_T) * math.sin(a), ZC + (R + BAND_T) * math.cos(a), (0, -math.sin(a), math.cos(a)))

for x in (-W / 2 + 0.035, 0.0, W / 2 - 0.035):
    lid_strap(f"LidStrap{x:+.2f}", x)

def ring(name, z, h, out=BAND_T):
    """Rectangular band wrapped around the body at height z (four plates)."""
    o = []
    o.append(box(name + "F", (W + 2 * out, out, h), (0, -D / 2 - out / 2, z)))
    o.append(box(name + "B", (W + 2 * out, out, h), (0, D / 2 + out / 2, z)))
    o.append(box(name + "L", (out, D, h), (-W / 2 - out / 2, 0, z)))
    o.append(box(name + "R", (out, D, h), (W / 2 + out / 2, 0, z)))
    for p in o: P(p, brass, bev=0.0015, uv=False)
    return o

ring("RimBand", HB - 0.022, 0.044)    # lid seam band (on body top)
ring("BaseBand", 0.022, 0.044)        # foot band
# vertical corner straps (L-shaped: two plates per corner) + rivets
for sx in (-1, 1):
    for sy in (-1, 1):
        xo = sx * (W / 2 + BAND_T / 2); yo = sy * (D / 2 + BAND_T / 2)
        P(box(f"CornerA{sx}{sy}", (BAND_W, BAND_T * 1.6, HB), (sx * (W / 2 - BAND_W / 2 + BAND_T), sy * (D / 2 + BAND_T * 0.8), HB / 2)), brass, bev=0.0015, uv=False)
        P(box(f"CornerB{sx}{sy}", (BAND_T * 1.6, BAND_W, HB), (sx * (W / 2 + BAND_T * 0.8), sy * (D / 2 - BAND_W / 2 + BAND_T), HB / 2)), brass, bev=0.0015, uv=False)
        for z in (0.022, HB / 2, HB - 0.022):
            rivet(sx * (W / 2 - BAND_W / 2 + BAND_T), sy * (D / 2 + BAND_T * 1.6), z, (0, sy, 0))
            rivet(sx * (W / 2 + BAND_T * 1.6), sy * (D / 2 - BAND_W / 2 + BAND_T), z, (sx, 0, 0))
# rivets along rim & base bands (front/back)
for z in (0.022, HB - 0.022):
    for x in (-0.15, 0.15):
        for sy in (-1, 1):
            rivet(x, sy * (D / 2 + BAND_T), z, (0, sy, 0))
    for y in (-0.08, 0.08):
        for sx in (-1, 1):
            rivet(sx * (W / 2 + BAND_T), y, z, (sx, 0, 0))
# front vertical strap under the lock (wood backing strip like the photo) -> brass strip
P(box("FrontStrap", (0.05, BAND_T, HB - 0.09), (0, -D / 2 - BAND_T / 2, (HB - 0.09) / 2 + 0.045)), brass, bev=0.0015, uv=False)

# ---------------------------------------------------------------- lock: shield plate + keyhole, hasp from lid
def shield(name, w, h, t, y, zc):
    pts = [(-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h * 0.1), (0, -h / 2), (-w / 2, -h * 0.1)]
    v = [(x, y, zc + z) for x, z in pts] + [(x, y - t, zc + z) for x, z in pts]
    n = len(pts)
    f = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_obj(name, v, f)

lock_z = HB - 0.075
lk = shield("LockPlate", 0.105, 0.135, 0.012, -D / 2 - BAND_T, lock_z)
P(lk, brass, bev=0.003, uv=False)
# keyhole: dark inset cylinder + slot, slightly proud of the plate face so it reads on the print too
kh = cylinder("KeyholeTop", 0.009, 0.004, (0, -D / 2 - BAND_T - 0.012 - 0.0005, lock_z + 0.012), segs=24, axis="Y")
P(kh, dark, bev=0, uv=False)
P(box("KeyholeSlot", (0.008, 0.004, 0.022), (0, -D / 2 - BAND_T - 0.012 - 0.0005, lock_z - 0.004)), dark, bev=0, uv=False)
for (x, z) in ((-0.038, lock_z + 0.05), (0.038, lock_z + 0.05), (-0.038, lock_z - 0.012), (0.038, lock_z - 0.012)):
    rivet(x, -D / 2 - BAND_T - 0.012, z, (0, -1, 0), r=0.005)
# hasp: plate hanging from the lid front edge over the lock top
hz = HB + 0.01
P(box("Hasp", (0.05, 0.01, 0.06), (0, -D / 2 - BAND_T - 0.017, hz)), brass, bev=0.0025, uv=False)
rivet(0, -D / 2 - BAND_T - 0.022, hz + 0.015, (0, -1, 0), r=0.0055)

# ---------------------------------------------------------------- hinges (back) + side handles
for x in (-0.17, 0.17):
    P(box(f"HingeStrapLid{x:+.2f}", (0.04, BAND_T, 0.08), (x, D / 2 + BAND_T / 2 + 0.002, HB + 0.035), rot=(math.radians(-18), 0, 0)), brass, bev=0.0015, uv=False)
    P(box(f"HingeStrapBody{x:+.2f}", (0.04, BAND_T, 0.08), (x, D / 2 + BAND_T * 1.5, HB - 0.07)), brass, bev=0.0015, uv=False)
    kn = cylinder(f"HingeKnuckle{x:+.2f}", 0.008, 0.05, (x, D / 2 + 0.012, HB + 0.002), segs=24, axis="X")
    P(kn, brass, bev=0.001, uv=False); shade_smooth(kn, 60)
    for z in (HB - 0.05, HB - 0.09):
        rivet(x, D / 2 + BAND_T * 2, z, (0, 1, 0), r=0.005)
for sx in (-1, 1):
    P(box(f"HandlePlate{sx}", (BAND_T, 0.07, 0.05), (sx * (W / 2 + BAND_T * 0.5), 0, HB - 0.08)), brass, bev=0.002, uv=False)
    hd = bpy.data.meshes.new("h")
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.0, radius2=0.0, depth=0.0) if False else None
    tor = None
    bpy.ops.mesh.primitive_torus_add(major_radius=0.03, minor_radius=0.0045, major_segments=32, minor_segments=12,
                                     location=(sx * (W / 2 + BAND_T + 0.002), 0, HB - 0.105), rotation=(0, math.radians(90 * sx), 0))
    tor = bpy.context.active_object; tor.name = f"Handle{sx}"; tor.scale = (1, 1, 0.75) if False else (1, 1, 1)
    tor.rotation_euler = (math.radians(90), 0, math.radians(90))
    P(tor, brass, bev=0, uv=False); shade_smooth(tor, 80)

# ---------------------------------------------------------------- apply modifiers / join into named groups
for o in parts:
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    o.select_set(False)
    apply_transform(o)

def join(name, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); j = bpy.context.active_object; j.name = name; return j

wood_parts = [o for o in parts if o.data.materials[0] in (wood, wood_end)]
metal_parts = [o for o in parts if o.data.materials[0] in (brass, dark)]
chest_wood = join("Chest_Wood", wood_parts)
chest_metal = join("Chest_Metal", metal_parts)
for o in (chest_wood, chest_metal):
    for p in o.data.polygons:
        pass
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.shade_auto_smooth(angle=math.radians(35)) if hasattr(bpy.ops.object, "shade_auto_smooth") else None
bpy.ops.object.select_all(action="DESELECT")
model = [chest_wood, chest_metal]

# ---------------------------------------------------------------- exports
def sel(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

sel(model)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "chest.glb"), use_selection=True, export_format="GLB", export_apply=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "chest.fbx"), use_selection=True, apply_unit_scale=True, object_types={"MESH"}, path_mode="COPY", embed_textures=True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "chest.obj"), export_selected_objects=True, export_materials=True, path_mode="COPY")
# print STL: union of all parts via voxel remesh -> single watertight shell, in millimetres
dup = [o.copy() for o in model]
for d_ in dup:
    d_.data = d_.data.copy(); sc.collection.objects.link(d_)
pr = join("Chest_Print", dup)
m = pr.modifiers.new("Remesh", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.0014; m.adaptivity = 0.0
sel([pr]); bpy.ops.object.modifier_apply(modifier="Remesh")
m = pr.modifiers.new("Dec", "DECIMATE"); m.ratio = 0.12; bpy.ops.object.modifier_apply(modifier="Dec")
bpy.ops.wm.stl_export(filepath=os.path.join(OUT, "chest_print_mm.stl"), export_selected_objects=True, global_scale=1000.0, apply_modifiers=True, up_axis="Z", forward_axis="Y")
pr.hide_render = True; pr.hide_viewport = True

# ---------------------------------------------------------------- studio
world_hdri(os.path.join(ASSETS, "hdris/studio_small_09/studio_small_09_2k.hdr"), strength=0.35, rot_z=math.radians(40),
           bg_color=(0.30, 0.30, 0.31), bg_strength=1.0)
# rotationally symmetric cyclorama (no visible edges from any camera angle)
prof = [(0.0, 0.0), (2.2, 0.0)]
for j in range(1, 13):
    a = (math.pi / 2) * j / 12
    prof.append((2.2 + 1.5 * math.sin(a), 1.5 - 1.5 * math.cos(a)))
prof.append((3.7, 8.0))
segs = 96; v, f = [], []
for i in range(segs):
    a = 2 * math.pi * i / segs
    for (r, z) in prof: v.append((r * math.cos(a), r * math.sin(a), z))
npf = len(prof)
for i in range(segs):
    i2 = (i + 1) % segs
    for k in range(npf - 1):
        f.append((i * npf + k, i * npf + k + 1, i2 * npf + k + 1, i2 * npf + k))
bd = mesh_obj("Backdrop", v, f); shade_smooth(bd, 80)
import bmesh
bm = bmesh.new(); bm.from_mesh(bd.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.to_mesh(bd.data); bm.free()
bgm = pbr_material("Backdrop", color=(0.30, 0.30, 0.31), rough=0.9); set_mat(bd, bgm)
# key / rim area lights
def area(name, loc, target, size, power, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA"); ld.size = size; ld.energy = power; ld.color = color
    lo = link(bpy.data.objects.new(name, ld)); lo.location = loc; look_at(lo, target); return lo
area("Key", (-1.1, -1.3, 1.5), (0, 0, 0.2), 1.0, 55, (1.0, 0.95, 0.88))
area("Fill", (1.4, -0.9, 0.7), (0, 0, 0.2), 1.5, 14, (0.9, 0.95, 1.0))
area("Rim", (0.6, 1.4, 1.3), (0, 0, 0.25), 0.8, 45)

cycles(sc, samples=SAMPLES, res=(1920, 1080), pct=PCT)
tgt = (0, 0, 0.2)
cams = {
    "front": camera("CamFront", (0, -1.75, 0.42), tgt, lens=55),
    "three_quarter": camera("Cam34", (-1.25, -1.3, 0.75), tgt, lens=55),
    "side": camera("CamSide", (1.75, 0.0, 0.42), tgt, lens=55),
    "back": camera("CamBack", (0.5, 1.7, 0.55), tgt, lens=55),
}
times = {}
if not SKIP:
    for k, cam in cams.items():
        times[k] = render_to(sc, cam, os.path.join(REN, f"chest_{k}.png"))
    # clay
    clay = pbr_material("Clay", color=(0.55, 0.53, 0.50), rough=0.55)
    saved = {o.name: list(o.data.materials) for o in model}
    for o in model:
        for i in range(len(o.data.materials)): o.data.materials[i] = clay
    times["clay"] = render_to(sc, cams["three_quarter"], os.path.join(REN, "chest_clay.png"))
    # wireframe over clay
    wires = []
    for o in model:
        w_ = o.copy(); w_.data = o.data.copy(); sc.collection.objects.link(w_)
        mw = w_.modifiers.new("Wire", "WIREFRAME"); mw.thickness = 0.0006; mw.use_replace = True; mw.use_even_offset = False
        wm = pbr_material("Wire", color=(0.03, 0.05, 0.08), rough=0.6)
        w_.data.materials.clear(); w_.data.materials.append(wm); wires.append(w_)
    times["wireframe"] = render_to(sc, cams["three_quarter"], os.path.join(REN, "chest_wireframe.png"))
    for w_ in wires: bpy.data.objects.remove(w_)
    for o in model:
        for i, mm in enumerate(saved[o.name]): o.data.materials[i] = mm

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "chest.blend"), compress=True)

if TT:
    pivot = link(bpy.data.objects.new("Pivot", None))
    for o in model: o.parent = pivot
    nF = int(arg("--tt-frames", "96"))
    sc.frame_start, sc.frame_end = 1, nF
    pivot.rotation_euler = (0, 0, 0); pivot.keyframe_insert("rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, 2 * math.pi * nF / (nF + 0)); pivot.keyframe_insert("rotation_euler", frame=nF + 1)
    for fc in pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    sc.cycles.samples = 16; sc.render.resolution_x, sc.render.resolution_y = 1280, 720; sc.render.resolution_percentage = 75
    sc.camera = camera("CamTT", (-1.2, -1.4, 0.65), tgt, lens=50)
    fr_dir = os.path.join(OUT, "tt_frames"); os.makedirs(fr_dir, exist_ok=True)
    sc.render.filepath = os.path.join(fr_dir, "f_")
    t = time.time(); bpy.ops.render.render(animation=True); times["turntable_total"] = time.time() - t
    print("TURNTABLE", times["turntable_total"], flush=True)

json.dump(times, open(os.path.join(REN, "chest_render_times.json"), "w"), indent=2)
print("DONE", times)
