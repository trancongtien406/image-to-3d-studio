"""Parts-based treasure chest, modelled procedurally from the reference photo
(examples/models/chest/chest_input.png). Real-world size: 60 x 40 x 43 cm.

Round 3: real rear hinges (alternating knuckles on a pin, leaves riveted to body and lid), a working hasp +
staple latch, lid as its own object pivoting on the hinge axis (open-lid render with velvet lining + coins),
lid edge bands aligned with the rim band, per-plank colour/roughness variation, scratches, brass edge wear.

    blender -b -P build_chest.py -- --out OUTDIR [--renders RENDERDIR] [--samples 64] [--views a,b,...] [--turntable]
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
velvet = pbr_material("Lining_Velvet", color=(0.16, 0.012, 0.02), rough=0.9, bump=0.15)
gold = pbr_material("Coin_Gold", color=(0.95, 0.68, 0.25), rough=0.22, metal=1.0, bump=0.1)


def _n(nt, t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items(): n.inputs[k].default_value = v
    return n


def wood_variation(m, scratches=True):
    """Render-only shader detail on top of the baked PBR maps: per-plank tone + roughness from the 'var' face
    attribute, AO grime in joints, fine scratches (lighter, rougher)."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    base = b.inputs["Base Color"].links[0].from_socket; rgh = b.inputs["Roughness"].links[0].from_socket
    at = N.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = "var"
    # tone: value 0.82..1.15, tiny hue shift
    mr = _n(nt, "ShaderNodeMapRange", **{"To Min": 0.8, "To Max": 1.16}); L.new(at.outputs["Fac"], mr.inputs["Value"])
    hh = _n(nt, "ShaderNodeMapRange", **{"To Min": 0.49, "To Max": 0.515}); L.new(at.outputs["Fac"], hh.inputs["Value"])
    hs = N.new("ShaderNodeHueSaturation"); L.new(base, hs.inputs["Color"]); L.new(mr.outputs["Result"], hs.inputs["Value"]); L.new(hh.outputs["Result"], hs.inputs["Hue"])
    col = hs.outputs["Color"]
    # AO grime
    ao = N.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.012; ao.samples = 8
    aor = N.new("ShaderNodeMapRange"); aor.inputs["To Min"].default_value = 0.55; L.new(ao.outputs["AO"], aor.inputs["Value"])
    mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
    L.new(col, mul.inputs[6]); L.new(aor.outputs["Result"], mul.inputs[7]); col = mul.outputs[2]
    rr = _n(nt, "ShaderNodeMapRange", **{"To Min": 0.85, "To Max": 1.2}); L.new(at.outputs["Fac"], rr.inputs["Value"])
    rm = N.new("ShaderNodeMath"); rm.operation = "MULTIPLY"; L.new(rgh, rm.inputs[0]); L.new(rr.outputs["Result"], rm.inputs[1]); rough = rm.outputs[0]
    if scratches:
        tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (3.0, 3.0, 90.0)
        mp.inputs["Rotation"].default_value = (0.4, 0.9, 0.3); L.new(tc.outputs["Object"], mp.inputs["Vector"])
        wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 6; wv.inputs["Distortion"].default_value = 9
        wv.inputs["Detail"].default_value = 3; L.new(mp.outputs["Vector"], wv.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements; e[0].position = 0.9; e[1].position = 0.97
        L.new(wv.outputs["Fac"], cr.inputs["Fac"])
        nz = _n(nt, "ShaderNodeTexNoise", Scale=4.0); L.new(tc.outputs["Object"], nz.inputs["Vector"])
        cr2 = N.new("ShaderNodeValToRGB"); e2 = cr2.color_ramp.elements; e2[0].position = 0.5; e2[1].position = 0.62
        L.new(nz.outputs["Fac"], cr2.inputs["Fac"])
        sm = N.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; L.new(cr.outputs["Color"], sm.inputs[0]); L.new(cr2.outputs["Color"], sm.inputs[1])
        sc_ = N.new("ShaderNodeMix"); sc_.data_type = "RGBA"; L.new(sm.outputs[0], sc_.inputs["Factor"])
        L.new(col, sc_.inputs[6]); sc_.inputs[7].default_value = (0.32, 0.22, 0.13, 1); col = sc_.outputs[2]
        ra = N.new("ShaderNodeMath"); ra.operation = "MULTIPLY_ADD"; L.new(sm.outputs[0], ra.inputs[0]); ra.inputs[1].default_value = 0.25
        L.new(rough, ra.inputs[2]); rough = ra.outputs[0]
    L.new(col, b.inputs["Base Color"]); L.new(rough, b.inputs["Roughness"])


def brass_wear(m):
    """Edge wear: polished bright brass on convex edges (pointiness), dark tarnish in cavities (AO) + patchy noise."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    geo = N.new("ShaderNodeNewGeometry")
    pr = N.new("ShaderNodeValToRGB"); e = pr.color_ramp.elements; e[0].position = 0.5; e[1].position = 0.56
    L.new(geo.outputs["Pointiness"], pr.inputs["Fac"])
    ao = N.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.006; ao.samples = 8
    tc = N.new("ShaderNodeTexCoord"); nz = _n(nt, "ShaderNodeTexNoise", Scale=18.0, Detail=6.0); L.new(tc.outputs["Object"], nz.inputs["Vector"])
    tr = N.new("ShaderNodeValToRGB"); e = tr.color_ramp.elements; e[0].position = 0.38; e[1].position = 0.58
    L.new(nz.outputs["Fac"], tr.inputs["Fac"])
    base = N.new("ShaderNodeMix"); base.data_type = "RGBA"; L.new(tr.outputs["Color"], base.inputs["Factor"])
    base.inputs[6].default_value = (0.26, 0.17, 0.06, 1); base.inputs[7].default_value = (0.56, 0.38, 0.13, 1)   # tarnished / brass
    cav = N.new("ShaderNodeMix"); cav.data_type = "RGBA"; L.new(ao.outputs["AO"], cav.inputs["Factor"])
    cav.inputs[6].default_value = (0.12, 0.085, 0.04, 1); L.new(base.outputs[2], cav.inputs[7])
    edge = N.new("ShaderNodeMix"); edge.data_type = "RGBA"; L.new(pr.outputs["Color"], edge.inputs["Factor"])
    L.new(cav.outputs[2], edge.inputs[6]); edge.inputs[7].default_value = (0.9, 0.7, 0.38, 1)
    L.new(edge.outputs[2], b.inputs["Base Color"])
    ro = N.new("ShaderNodeMapRange"); ro.inputs["To Min"].default_value = 0.58; ro.inputs["To Max"].default_value = 0.34
    L.new(tr.outputs["Color"], ro.inputs["Value"])
    re = N.new("ShaderNodeMix"); L.new(pr.outputs["Color"], re.inputs["Factor"]); L.new(ro.outputs["Result"], re.inputs[2]); re.inputs[3].default_value = 0.2
    L.new(re.outputs[0], b.inputs["Roughness"])
    m.cycles.displacement_method = "BUMP"
parts = []

GRP = ["body"]   # current part group: body / lid / core / lining

def P(o, mat, bev=0.0025, segs=2, long_axis=0, uv=True, grp=None):
    if uv: uv_box(o, scale=1.4, long_axis=long_axis, rnd=rnd)
    set_mat(o, mat); o["grp"] = grp or GRP[0]
    # per-part random value -> shader colour / roughness variation (survives joining as a face attribute)
    at = o.data.attributes.new("var", "FLOAT", "FACE"); v_ = rnd.random()
    for d_ in at.data: d_.value = v_
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
P(box("Core", (W - 2 * T + 0.002, D - 2 * T + 0.002, HB - 0.004), (0, 0, HB / 2)), wood_end, bev=0, grp="core")
GRP[0] = "lid"

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
P(lid_cap("LidCore", -W / 2 + T, W / 2 - T, R - T + 0.001), wood_end, bev=0, grp="core")

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
# lid edge bands (front + back) - same 7 mm projection as the rim band below, so lid and body read as one box
EB = 0.028 / R   # 28 mm along the arc
for nm, (a0, a1) in (("LidEdgeF", (AMAX - EB, AMAX)), ("LidEdgeB", (-AMAX, -AMAX + EB))):
    o = arc_stave(nm, a0, a1, R - 0.0005, R + BAND_T, -W / 2 - BAND_T, W / 2 + BAND_T, segs=4)
    P(o, brass, bev=0.0015, uv=False)
    for x in (-0.15, 0.15):
        a = (a0 + a1) / 2; rivet(x, -(R + BAND_T) * math.sin(a), ZC + (R + BAND_T) * math.cos(a), (0, -math.sin(a), math.cos(a)), r=0.005)
GRP[0] = "body"

def ring(name, z, h, out=BAND_T):
    """Rectangular band wrapped around the body at height z (four plates)."""
    o = []
    o.append(box(name + "F", (W + 2 * out, out, h), (0, -D / 2 - out / 2, z)))
    o.append(box(name + "B", (W + 2 * out, out, h), (0, D / 2 + out / 2, z)))
    o.append(box(name + "L", (out, D, h), (-W / 2 - out / 2, 0, z)))
    o.append(box(name + "R", (out, D, h), (W / 2 + out / 2, 0, z)))
    for p in o: P(p, brass, bev=0.0015, uv=False)
    return o

SEAM = 0.0015                           # visible lid / body seam
ring("RimBand", HB - 0.022 - SEAM, 0.044)
ring("BaseBand", 0.022, 0.044)
for sx in (-1, 1):
    for sy in (-1, 1):
        P(box(f"CornerA{sx}{sy}", (BAND_W, BAND_T * 1.6, HB - SEAM), (sx * (W / 2 - BAND_W / 2 + BAND_T), sy * (D / 2 + BAND_T * 0.8), (HB - SEAM) / 2)), brass, bev=0.0015, uv=False)
        P(box(f"CornerB{sx}{sy}", (BAND_T * 1.6, BAND_W, HB - SEAM), (sx * (W / 2 + BAND_T * 0.8), sy * (D / 2 - BAND_W / 2 + BAND_T), (HB - SEAM) / 2)), brass, bev=0.0015, uv=False)
        for z in (0.022, HB / 2, HB - 0.024):
            rivet(sx * (W / 2 - BAND_W / 2 + BAND_T), sy * (D / 2 + BAND_T * 1.6), z, (0, sy, 0))
            rivet(sx * (W / 2 + BAND_T * 1.6), sy * (D / 2 - BAND_W / 2 + BAND_T), z, (sx, 0, 0))
for z in (0.022, HB - 0.024):
    for x in (-0.25 + 0.0, 0.25):
        rivet(x, -(D / 2 + BAND_T), z, (0, -1, 0))
    for y in (-0.08, 0.08):
        for sx in (-1, 1):
            rivet(sx * (W / 2 + BAND_T), y, z, (sx, 0, 0))
P(box("FrontStrap", (0.05, BAND_T, HB - 0.09), (0, -D / 2 - BAND_T / 2, (HB - 0.09) / 2 + 0.045)), brass, bev=0.0015, uv=False)

# ---------------------------------------------------------------- lock: shield plate + keyhole + staple; hasp on the lid
def shield(name, w, h, t, y, zc):
    pts = [(-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h * 0.1), (0, -h / 2), (-w / 2, -h * 0.1)]
    v = [(x, y, zc + z) for x, z in pts] + [(x, y - t, zc + z) for x, z in pts]
    n = len(pts)
    f = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_obj(name, v, f)

lock_z = HB - 0.075; LF = -D / 2 - BAND_T - 0.012          # lock plate front face (y)
P(shield("LockPlate", 0.105, 0.135, 0.012, -D / 2 - BAND_T, lock_z), brass, bev=0.003, uv=False)
P(cylinder("KeyholeTop", 0.008, 0.004, (0, LF - 0.0005, lock_z - 0.008), segs=24, axis="Y"), dark, bev=0, uv=False)
P(box("KeyholeSlot", (0.007, 0.004, 0.02), (0, LF - 0.0005, lock_z - 0.022)), dark, bev=0, uv=False)
P(cylinder("KeyEscutcheon", 0.013, 0.002, (0, LF - 0.001, lock_z - 0.008), segs=32, axis="Y"), brass, bev=0.0006, uv=False)
for (x, z) in ((-0.038, lock_z + 0.045), (0.038, lock_z + 0.045), (-0.038, lock_z - 0.02), (0.038, lock_z - 0.02)):
    rivet(x, LF, z, (0, -1, 0), r=0.005)
# staple: a U-loop standing out of the lock plate; the hasp slot drops over it and a padlock pin passes through
SZ = HB - 0.034
for dz in (-0.0075, 0.0075):
    P(box(f"StaplePost{dz:+.3f}", (0.005, 0.015, 0.004), (0, LF - 0.0075 + 0.001, SZ + dz)), brass, bev=0.001, uv=False)
P(box("StapleBar", (0.005, 0.004, 0.019), (0, LF - 0.0155, SZ)), brass, bev=0.0012, uv=False)

GRP[0] = "lid"
HY0 = -(D / 2 + BAND_T)                 # lid edge band outer face (front)
P(box("HaspLeaf", (0.036, 0.004, 0.022), (0, HY0 - 0.002, HB + 0.022)), brass, bev=0.001, uv=False)
P(cylinder("HaspKnuckle", 0.0045, 0.04, (0, HY0 - 0.0045, HB + 0.009), segs=20, axis="X"), brass, bev=0.0006, uv=False)
# hasp plate with a real slot (frame of 4 bars) hanging in front of the lock plate
HP_Y = LF - 0.0035; ht, hb = HB + 0.006, HB - 0.06; sl0, sl1 = SZ - 0.0125, SZ + 0.0125
P(box("HaspTop", (0.042, 0.004, ht - sl1), (0, HP_Y, (ht + sl1) / 2)), brass, bev=0.0012, uv=False)
P(box("HaspBottom", (0.042, 0.004, sl0 - hb), (0, HP_Y, (sl0 + hb) / 2)), brass, bev=0.0012, uv=False)
for sx in (-1, 1):
    P(box(f"HaspRail{sx}", (0.0155, 0.004, sl1 - sl0), (sx * (0.0055 + 0.0155 / 2), HP_Y, SZ)), brass, bev=0.0008, uv=False)
P(box("HaspLink", (0.012, 0.012, 0.008), (0, HY0 - 0.0055, HB + 0.004)), brass, bev=0.001, uv=False)
P(box("HaspLink2", (0.012, (HY0 - 0.0055) - HP_Y + 0.004, 0.006), (0, (HY0 - 0.0055 + HP_Y) / 2, HB + 0.004)), brass, bev=0.001, uv=False)
rivet(0, HY0 - 0.004, HB + 0.026, (0, -1, 0), r=0.004)

GRP[0] = "body"
# ---------------------------------------------------------------- rear hinges: alternating knuckles on a pin
RK, LK, NK, KG = 0.0085, 0.066, 5, 0.0012       # knuckle radius, hinge length, knuckles, gap between knuckles
HY = D / 2 + BAND_T + 0.0075; HZ = HB + 0.0005  # hinge (lid rotation) axis
lk = (LK - (NK - 1) * KG) / NK
HINGE_X = (-0.17, 0.17)
for x in HINGE_X:
    for i in range(NK):
        g = "body" if i % 2 == 0 else "lid"
        kx = x - LK / 2 + lk / 2 + i * (lk + KG)
        kn = cylinder(f"Knuckle{x:+.2f}_{i}", RK, lk, (kx, HY, HZ), segs=28, axis="X")
        P(kn, brass, bev=0.0008, uv=False, grp=g); shade_smooth(kn, 50)
        if g == "lid":   # web from the lid knuckle up onto the lid leaf
            P(box(f"KnWeb{x:+.2f}_{i}", (lk, 0.012, 0.01), (kx, HY - 0.006, HZ + 0.006)), brass, bev=0.001, uv=False, grp="lid")
    pin = cylinder(f"HingePin{x:+.2f}", 0.0034, LK + 0.006, (x, HY, HZ), segs=16, axis="X"); P(pin, brass, bev=0, uv=False, grp="body")
    for sx in (-1, 1):
        cap = dome(f"PinCap{x:+.2f}{sx}", 0.0052, 0.003, (0, 0, 0), segs=16, rings=4)
        cap.rotation_euler = Vector((sx, 0, 0)).to_track_quat("Z", "Y").to_euler(); cap.location = (x + sx * (LK / 2 + 0.003), HY, HZ)
        P(cap, brass, bev=0, uv=False, grp="body")
    # body leaf: strap down the back (on the rim band) with a spacer below the band, spear-shaped end
    P(box(f"HingeLeafBody{x:+.2f}", (LK, 0.004, 0.11), (x, D / 2 + BAND_T + 0.002, HB - 0.055)), brass, bev=0.0012, uv=False, grp="body")
    P(box(f"HingeSpacer{x:+.2f}", (LK - 0.006, BAND_T, 0.066), (x, D / 2 + BAND_T / 2, HB - 0.11 + 0.033)), brass, bev=0.0008, uv=False, grp="body")
    tip = mesh_obj(f"HingeTip{x:+.2f}", [(x - LK / 2, D / 2, HB - 0.11), (x + LK / 2, D / 2, HB - 0.11), (x, D / 2, HB - 0.145),
                                          (x - LK / 2, D / 2 + BAND_T + 0.004, HB - 0.11), (x + LK / 2, D / 2 + BAND_T + 0.004, HB - 0.11), (x, D / 2 + BAND_T + 0.004, HB - 0.145)],
                   [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)])
    P(tip, brass, bev=0.001, uv=False, grp="body")
    for z in (HB - 0.03, HB - 0.075, HB - 0.12):
        rivet(x, D / 2 + BAND_T + 0.004, z, (0, 1, 0), r=0.0048)
    # lid leaf: curved strap following the lid arc from the hinge up over the back
    a0 = -AMAX; a1 = -AMAX + 0.1 / R
    lf = arc_stave(f"HingeLeafLid{x:+.2f}", a0, a1, R - 0.0005, R + 0.0045, x - LK / 2, x + LK / 2, segs=10)
    P(lf, brass, bev=0.0012, uv=False, grp="lid"); shade_smooth(lf, 30)
    for k in (0.35, 0.8):
        a = a0 + (a1 - a0) * k; rr = R + 0.0045
        rivet(x, -rr * math.sin(a), ZC + rr * math.cos(a), (0, -math.sin(a), math.cos(a)), r=0.0048)
        rivets[-1]["grp"] = "lid"

# side handles: plate + bail ring through an eye
for sx in (-1, 1):
    P(box(f"HandlePlate{sx}", (BAND_T, 0.07, 0.05), (sx * (W / 2 + BAND_T * 0.5), 0, HB - 0.08)), brass, bev=0.002, uv=False)
    P(cylinder(f"HandleEye{sx}", 0.007, 0.012, (sx * (W / 2 + BAND_T + 0.006), 0, HB - 0.08), segs=16, axis="X"), brass, bev=0.001, uv=False)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.03, minor_radius=0.0045, major_segments=32, minor_segments=12,
                                     location=(sx * (W / 2 + BAND_T + 0.002), 0, HB - 0.105))
    tor = bpy.context.active_object; tor.name = f"Handle{sx}"; tor.rotation_euler = (math.radians(90), 0, math.radians(90))
    P(tor, brass, bev=0, uv=False); shade_smooth(tor, 80)

# ---------------------------------------------------------------- interior: velvet lining + coins (open-lid version)
GRP[0] = "lining"
LT = 0.004; ih = HB - T - 0.012
for nm, sz, loc in (("LinF", (W - 2 * T - 0.002, LT, ih), (0, -D / 2 + T + LT / 2 + 0.0005, T + ih / 2 + 0.006)),
                    ("LinB", (W - 2 * T - 0.002, LT, ih), (0, D / 2 - T - LT / 2 - 0.0005, T + ih / 2 + 0.006)),
                    ("LinL", (LT, D - 2 * T - 2 * LT - 0.002, ih), (-W / 2 + T + LT / 2 + 0.0005, 0, T + ih / 2 + 0.006)),
                    ("LinR", (LT, D - 2 * T - 2 * LT - 0.002, ih), (W / 2 - T - LT / 2 - 0.0005, 0, T + ih / 2 + 0.006)),
                    ("LinBottom", (W - 2 * T - 2 * LT - 0.002, D - 2 * T - 2 * LT - 0.002, 0.008), (0, 0, T + 0.004))):
    P(box(nm, sz, loc), velvet, bev=0.0018, segs=3, uv=False)
P(arc_stave("LinLid", -AMAX + 0.03, AMAX - 0.03, R - T - LT - 0.0008, R - T - 0.0008, -W / 2 + T + 0.001, W / 2 - T - 0.001, segs=24), velvet, bev=0.0015, uv=False, grp="lining_lid")
# pile of coins on the lining
crnd = random.Random(3)
for i in range(90):
    a = crnd.uniform(0, 2 * math.pi); r_ = abs(crnd.gauss(0, 0.055)); x, y = -0.07 + r_ * math.cos(a) * 1.5, 0.02 + r_ * math.sin(a)
    z = T + 0.0105 + 0.04 * math.exp(-(r_ / 0.05) ** 2) * crnd.uniform(0.6, 1.0)
    cn = cylinder(f"Coin{i}", 0.0125, 0.0022, (x, y, z), segs=28)
    cn.rotation_euler = (crnd.uniform(-0.35, 0.35), crnd.uniform(-0.35, 0.35), crnd.uniform(0, 6.3))
    P(cn, gold, bev=0.0005, uv=False, grp="coins")

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

_groups = {}
for o in parts:
    _groups.setdefault((o.get("grp"), o.data.materials[0].name), []).append(o)
G = lambda g, mats: [o for m_ in mats for o in _groups.get((g, m_.name), [])]
core_b = _groups[("core", wood_end.name)][0]; core_l = _groups[("core", wood_end.name)][1]
body_wood = join("Chest_Body_Wood", G("body", (wood, wood_end)))
body_metal = join("Chest_Body_Metal", G("body", (brass, dark)))
lid_wood = join("Chest_Lid_Wood", G("lid", (wood, wood_end)))
lid_metal = join("Chest_Lid_Metal", G("lid", (brass, dark)))
lining = join("Chest_Lining", G("lining", (velvet,)))
lining_lid = join("Chest_Lid_Lining", G("lining_lid", (velvet,)))
coins = join("Coins", G("coins", (gold,)))
core_b.name = "Core_Body"; core_l.name = "Core_Lid"
# lid objects pivot on the hinge axis -> lid can be opened/animated in any DCC/game engine
for o in (lid_wood, lid_metal, lining_lid, core_l):
    o.data.transform(Matrix.Translation((0, -HY, -HZ))); o.location = (0, HY, HZ)
lid_objs = [lid_wood, lid_metal, lining_lid]
for o in (body_wood, body_metal, lid_wood, lid_metal, lining, lining_lid, coins):
    for p in o.data.polygons: p.use_smooth = p.use_smooth
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.shade_auto_smooth(angle=math.radians(35)) if hasattr(bpy.ops.object, "shade_auto_smooth") else None
bpy.ops.object.select_all(action="DESELECT")
model = [body_wood, body_metal, lid_wood, lid_metal, lining, lining_lid]
for o in (core_b, core_l, coins): o.hide_render = True
wood_variation(wood); wood_variation(wood_end, scratches=False); brass_wear(brass)

def set_lid(deg):
    for o in lid_objs + [core_l]: o.rotation_euler = (math.radians(-deg), 0, 0)
    bpy.context.view_layer.update()

# ---------------------------------------------------------------- exports (hollow, lined, lid as separate pivoting objects)
def sel(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

sel(model)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "chest.glb"), use_selection=True, export_format="GLB", export_apply=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "chest.fbx"), use_selection=True, apply_unit_scale=True, object_types={"MESH"}, path_mode="COPY", embed_textures=True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "chest.obj"), export_selected_objects=True, export_materials=True, path_mode="COPY")
# print STL: closed lid + solid cores, union via voxel remesh -> single watertight shell, millimetres, Z up
dup = []
for o_ in [body_wood, body_metal, lid_wood, lid_metal, core_b, core_l]:
    d_ = o_.copy(); d_.data = o_.data.copy(); sc.collection.objects.link(d_); d_.hide_render = False
    d_.data.transform(d_.matrix_basis); d_.matrix_basis = Matrix.Identity(4); dup.append(d_)
pr = join("Chest_Print", dup)
m = pr.modifiers.new("Remesh", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.0012; m.adaptivity = 0.0
sel([pr]); bpy.ops.object.modifier_apply(modifier="Remesh")
m = pr.modifiers.new("Dec", "DECIMATE"); m.ratio = 0.1; bpy.ops.object.modifier_apply(modifier="Dec")
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
CAMS = {
    "front": dict(loc=(0, -1.75, 0.42), tgt=tgt, lens=55),
    "three_quarter": dict(loc=(-1.25, -1.3, 0.75), tgt=tgt, lens=55),
    "side": dict(loc=(1.75, 0.0, 0.42), tgt=tgt, lens=55),
    "back": dict(loc=(0.75, 1.6, 0.6), tgt=(0, 0.05, 0.2), lens=55),
    "reference_match": dict(loc=(0.98, -1.52, 0.82), tgt=(0.0, 0.0, 0.21), lens=50, square=True),
    "open": dict(loc=(-1.05, -1.45, 1.2), tgt=(0, 0.02, 0.3), lens=50, lid=100, coins=True),
    "closeup_latch": dict(loc=(-0.16, -0.62, 0.36), tgt=(0, -0.215, 0.235), lens=90, dof=(0.35, 3.2)),
    "closeup_hinge": dict(loc=(0.42, 0.62, 0.42), tgt=(0.17, 0.215, 0.255), lens=90, dof=(0.48, 3.2)),
}
VIEWS = arg("--views", "three_quarter,front,back,side,open,closeup_latch,closeup_hinge,topology").split(",")
times = {}

def cam_for(k):
    s = CAMS[k]; c = camera(f"Cam_{k}", s["loc"], s["tgt"], lens=s["lens"])
    if "dof" in s:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = (Vector(s["loc"]) - Vector(s["tgt"])).length; c.data.dof.aperture_fstop = s["dof"][1]
    return c

if not SKIP:
    for k in VIEWS:
        if k == "topology":
            continue
        s = CAMS[k]; set_lid(s.get("lid", 0)); coins.hide_render = not s.get("coins")
        sc.render.resolution_x, sc.render.resolution_y = (1440, 1440) if s.get("square") else (1920, 1080)
        times[k] = render_to(sc, cam_for(k), os.path.join(REN, f"chest_{k}.png"))
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    set_lid(0); coins.hide_render = True
    if "topology" in VIEWS:
        # clay + wireframe overlay (topology view) with the lid open, so hinge / latch / lining topology is visible
        clay = pbr_material("Clay", color=(0.55, 0.53, 0.50), rough=0.55)
        saved = {o.name: list(o.data.materials) for o in model}
        for o in model:
            for i in range(len(o.data.materials)): o.data.materials[i] = clay
        times["clay"] = render_to(sc, cam_for("three_quarter"), os.path.join(REN, "chest_clay.png"))
        wires = []
        wm = pbr_material("Wire", color=(0.03, 0.05, 0.08), rough=0.6)
        for o in model:
            w_ = o.copy(); w_.data = o.data.copy(); sc.collection.objects.link(w_)
            mw = w_.modifiers.new("Wire", "WIREFRAME"); mw.thickness = 0.0005; mw.use_replace = True; mw.use_even_offset = False
            w_.data.materials.clear(); w_.data.materials.append(wm); wires.append(w_)
        lid_objs += [w for w in wires if w.name.startswith(("Chest_Lid", "Chest_Lid_Lining"))]
        set_lid(65)
        times["topology"] = render_to(sc, cam_for("open"), os.path.join(REN, "chest_topology.png"))
        set_lid(0)
        for w_ in wires: bpy.data.objects.remove(w_)
        lid_objs[:] = [lid_wood, lid_metal, lining_lid]
        for o in model:
            for i, mm in enumerate(saved[o.name]): o.data.materials[i] = mm

stats = {o.name: {"tris": sum(len(p.vertices) - 2 for p in o.data.polygons), "verts": len(o.data.vertices)} for o in model}
FEATURES = {"strap_projection": BAND_T * 1000, "strap_width": BAND_W * 1000, "rivet_head_height": 4.5, "rivet_head_diameter": 12.4,
            "hinge_knuckle_diameter": RK * 2000, "hinge_knuckle_gap": KG * 1000, "hasp_plate_thickness": 4.0, "staple_bar": 4.0,
            "handle_ring_wire_diameter": 9.0, "plank_gap": 2.5, "lid_seam": SEAM * 1000, "keyhole_slot_width": 7.0}
json.dump(FEATURES, open(os.path.join(OUT, "print_features_mm.json"), "w"), indent=2)
json.dump({"objects": stats, "total_tris": sum(v["tris"] for v in stats.values()), "hinge_axis_m": [0, HY, HZ],
           "lid_pivot": "Chest_Lid_* origins sit on the hinge axis; rotate -X to open"}, open(os.path.join(OUT, "model_stats.json"), "w"), indent=2)
try:
    bpy.ops.file.pack_all()    # textures packed into the .blend
except Exception as e:
    print("pack failed", e)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "chest.blend"), compress=True)

if TT:
    pivot = link(bpy.data.objects.new("Pivot", None))
    for o in model: o.parent = pivot
    nF = int(arg("--tt-frames", "96"))
    sc.frame_start, sc.frame_end = 1, nF
    pivot.rotation_euler = (0, 0, 0); pivot.keyframe_insert("rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, 2 * math.pi); pivot.keyframe_insert("rotation_euler", frame=nF + 1)
    for fc in pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    sc.cycles.samples = 16; sc.render.resolution_x, sc.render.resolution_y = 1280, 720; sc.render.resolution_percentage = 75
    sc.camera = camera("CamTT", (-1.2, -1.4, 0.65), tgt, lens=50)
    fr_dir = os.path.join(OUT, "tt_frames"); os.makedirs(fr_dir, exist_ok=True)
    sc.render.filepath = os.path.join(fr_dir, "f_")
    t = time.time(); bpy.ops.render.render(animation=True); times["turntable_total"] = time.time() - t

json.dump(times, open(os.path.join(REN, "chest_render_times.json"), "w"), indent=2)
print("DONE", times)
