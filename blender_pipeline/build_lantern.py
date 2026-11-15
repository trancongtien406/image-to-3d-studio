"""Black-iron carriage / candle lantern game prop, modelled from a CC0 reference photo:
examples/models/lantern/lantern_reference_cc0.jpg (Wikimedia Commons, Syced, CC0 1.0 - see CREDITS.md).

    blender -b -P build_lantern.py -- [--out output/lantern] [--samples 128] [--door 22] [--no-renders]
Square frame with corner posts + rails, 3 fixed glass panes, hinged front door (own object, origin on the hinge axis),
stepped roof, chimney with vent slots, brass cap + hanging ring, wire bail on chimney lugs with a turned-wood grip, candle + flame.
"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import reset_scene, camera, box, cylinder, uv_box, tex_path, link, shade_smooth, apply_transform
import prop_kit as K
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d): return argv[argv.index(k) + 1] if k in argv else d
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, arg("--out", "output/lantern")); SAMPLES = int(arg("--samples", "128")); DOOR = float(arg("--door", "0"))
sc = reset_scene()

iron = K.tex_material("Iron_Enamel", diffuse=K.gen("iron_enamel_Diffuse_1k.jpg"), rough=K.gen("iron_enamel_Rough_1k.jpg"),
                      normal=K.gen("iron_enamel_nor_gl_1k.jpg"), metal=K.gen("iron_enamel_Metal_1k.jpg"), normal_strength=0.6)
glass = K.tex_material("Glass_Clear", color=(0.92, 0.93, 0.88), rough_v=0.04, transmission=1.0, ior=1.5)
wood = K.tex_material("Wood_Grip", diffuse=K.gen("grip_wood_Diffuse_1k.jpg"),  # dark_wood (Poly Haven CC0), darkened/desaturated
                       rough=tex_path("dark_wood", "Rough"), normal=tex_path("dark_wood", "nor_gl"), normal_strength=0.7)
brass = K.tex_material("Brass_Cap", color=(0.45, 0.30, 0.12), rough_v=0.38, metal_v=1.0)
dark = K.tex_material("Vent_Dark", color=(0.008, 0.007, 0.006), rough_v=0.8)
wax = K.tex_material("Candle_Wax", color=(0.86, 0.79, 0.64), rough_v=0.45)
flame = K.tex_material("Flame", color=(1.0, 0.6, 0.25), rough_v=0.5, emission=(1.0, 0.55, 0.18), emission_strength=25.0)
UVS = 5.0   # iron texture: one 1k tile per 0.2 m

def ibox(name, size, loc, bev=0.0012, mat=None):
    o = box(name, size, loc); o = K.bevel_apply(o, bev, 2) if bev else (apply_transform(o) or o)
    uv_box(o, scale=UVS); return K.set_mat(o, mat or iron)

def tube(name, pts, r, segs=10, mat=None):
    """Swept tube along a polyline (parallel-transport frames), UV: U around, V = length."""
    pts = [Vector(p) for p in pts]
    if len(pts) > 2:   # Catmull-Rom smoothing (6 sub-steps per span) -> round wire bends
        ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]; sm = []
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            for k in range(6):
                t = k / 6; sm.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        pts = sm + [pts[-1]]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); rings = []; L = [0.0]
    for i in range(1, len(pts)): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    t0 = (pts[1] - pts[0]).normalized(); n = t0.orthogonal().normalized()
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = (n - t * n.dot(t)).normalized(); bnorm = t.cross(n)
        rings.append([bm.verts.new(p + (n * math.cos(2 * math.pi * k / segs) + bnorm * math.sin(2 * math.pi * k / segs)) * r) for k in range(segs)])
    for i in range(len(pts) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs; f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            for lp, (u, v) in zip(f.loops, ((k / segs, L[i]), ((k + 1) / segs, L[i]), ((k + 1) / segs, L[i + 1]), (k / segs, L[i + 1]))):
                lp[uvl].uv = (u * 0.05, v * UVS)
    for ring in (rings[0], rings[-1][::-1]):
        bm.faces.new(ring[::-1] if ring is rings[0] else ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = link(bpy.data.objects.new(name, me)); shade_smooth(o, 50)
    return K.set_mat(o, mat or iron)

def arcpts(c, rx, rz, a0, a1, n, y=0.0, plane="XZ"):
    out = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        out.append((c[0] + rx * math.cos(a), c[1] + y, c[2] + rz * math.sin(a)) if plane == "XZ" else (c[0] + rx * math.cos(a), c[1] + rz * math.sin(a), c[2]))
    return out

W = 0.130; H0, H1 = 0.020, 0.220; P = 0.009; hw = W / 2
body, panes, door_parts, candle, grip = [], [], [], [], []
# base + feet
body.append(ibox("Base", (W + 0.012, W + 0.012, 0.016), (0, 0, 0.012), 0.002))
body.append(ibox("BaseLip", (W + 0.004, W + 0.004, 0.006), (0, 0, 0.023), 0.0015))
for sx in (-1, 1):
    for sy in (-1, 1): body.append(ibox(f"Foot{sx}{sy}", (0.016, 0.016, 0.004), (sx * (hw - 0.002), sy * (hw - 0.002), 0.002), 0.001))
# corner posts (L-section look: two flat bars) + rails
for sx in (-1, 1):
    for sy in (-1, 1):
        body.append(ibox(f"PostA{sx}{sy}", (P, 0.002, H1 - H0), (sx * (hw - P / 2 + 0.001), sy * (hw + 0.001), (H0 + H1) / 2), 0.0006))
        body.append(ibox(f"PostB{sx}{sy}", (0.002, P, H1 - H0), (sx * (hw + 0.001), sy * (hw - P / 2 + 0.001), (H0 + H1) / 2), 0.0006))
for z in (0.030, 0.212):
    for sy in (-1, 1):
        if sy == -1 and z < 0.1: continue   # front bottom rail belongs to the door opening sill below
        body.append(ibox(f"RailX{sy}{z}", (W - 0.004, 0.003, 0.012), (0, sy * (hw + 0.0005), z), 0.0006))
    for sx in (-1, 1): body.append(ibox(f"RailY{sx}{z}", (0.003, W - 0.004, 0.012), (sx * (hw + 0.0005), 0, z), 0.0006))
body.append(ibox("Sill", (W - 0.004, 0.006, 0.006), (0, -(hw - 0.001), 0.027), 0.0008))
# fixed panes: left, right, back
GH = 0.170; GZ = 0.121
for sx in (-1, 1): panes.append(K.set_mat(ibox(f"Pane{sx}", (0.0022, W - 0.012, GH), (sx * (hw - 0.0025), 0, GZ), 0.0003), glass))
panes.append(K.set_mat(ibox("PaneBack", (W - 0.012, 0.0022, GH), (0, hw - 0.0025, GZ), 0.0003), glass))
# roof: plate + square-to-round frustum (superellipse exponent blends 12 -> 2), chimney, vent slots, brass cap, ring
body.append(ibox("RoofPlate", (W + 0.016, W + 0.016, 0.005), (0, 0, H1 + 0.0025), 0.0015))
roof = K.revolve("Roof", [(0, 0.2245), (hw + 0.004, 0.2245, 12), (hw + 0.004, 0.229, 12), (0.050, 0.243, 5), (0.034, 0.254, 2.6), (0.031, 0.257, 2), (0, 0.257)], segs=64, vscale=UVS)
body.append(K.set_mat(roof, iron))
body.append(K.set_mat(K.revolve("Chimney", [(0, 0.255), (0.0285, 0.255), (0.0285, 0.296), (0.031, 0.297), (0.031, 0.300), (0, 0.300)], segs=48, vscale=UVS), iron))
for k in range(12):
    a = 2 * math.pi * k / 12; o = box(f"Vent{k}", (0.0035, 0.004, 0.014), (0.0278 * math.cos(a), 0.0278 * math.sin(a), 0.276), (0, 0, a + math.pi / 2))
    apply_transform(o); uv_box(o, scale=UVS); body.append(K.set_mat(o, dark))
body.append(K.set_mat(K.revolve("Cap", [(0, 0.2985), (0.037, 0.2985), (0.038, 0.303), (0.034, 0.306), (0.020, 0.315), (0.008, 0.3195), (0, 0.320)], segs=64, vscale=UVS), brass))
ring = K.revolve("HangRing", [(0.012 + 0.0024 * math.cos(2 * math.pi * k / 10), 0.0024 * math.sin(2 * math.pi * k / 10)) for k in range(10)], segs=32, closed_loop=True, vscale=UVS)
ring.rotation_euler = (math.pi / 2, 0, 0); ring.location = (0, 0, 0.3325); apply_transform(ring); body.append(K.set_mat(ring, iron))
body.append(K.set_mat(K.revolve("RingLug", [(0, 0.319), (0.004, 0.319), (0.004, 0.322), (0.0025, 0.3215), (0.0025, 0.3205), (0, 0.3205)], segs=16), iron))
# front door: own object, origin on the hinge axis (x = -hw - 0.003, y = -hw - 0.004)
HX, HY = -hw - 0.0025, -hw - 0.004
DZ0, DZ1 = 0.033, 0.208; DW = W - 0.006; FB = 0.009
for nm, size, loc in (("DoorL", (FB, 0.003, DZ1 - DZ0), (-hw + 0.003 + FB / 2, HY + 0.0005, (DZ0 + DZ1) / 2)),
                      ("DoorR", (FB, 0.003, DZ1 - DZ0), (hw - 0.003 - FB / 2, HY + 0.0005, (DZ0 + DZ1) / 2)),
                      ("DoorB", (DW, 0.003, FB), (0, HY + 0.0005, DZ0 + FB / 2)), ("DoorT", (DW, 0.003, FB), (0, HY + 0.0005, DZ1 - FB / 2))):
    door_parts.append(ibox(nm, size, loc, 0.0007))
door_parts.append(K.set_mat(ibox("DoorPane", (DW - 0.010, 0.0022, DZ1 - DZ0 - 0.010), (0, HY + 0.0025, (DZ0 + DZ1) / 2), 0.0003), glass))
for z in (0.060, 0.180):
    kn = cylinder(f"Knuckle{z}", 0.0028, 0.022, (HX, HY, z), segs=16); apply_transform(kn); uv_box(kn, scale=UVS); door_parts.append(K.set_mat(kn, iron))
door_parts.append(ibox("Latch", (0.012, 0.005, 0.006), (hw - 0.004, HY - 0.002, 0.120), 0.0008))
lk = K.revolve("LatchKnob", [(0, 0), (0.0035, 0), (0.0042, 0.003), (0.003, 0.006), (0, 0.0065)], segs=20); lk.rotation_euler = (math.pi / 2, 0, 0); lk.location = (hw - 0.004, HY - 0.0045, 0.120)
apply_transform(lk); door_parts.append(K.set_mat(lk, brass))
body.append(K.set_mat(tube("HingePin", [(HX, HY, 0.045), (HX, HY, 0.195)], 0.0012, 8), iron))
# bail handle (as in the reference): wire bail pivoting on two chimney lugs, folded down in front, horizontal turned-wood grip
GY = -(hw + 0.030); GZ = 0.168; GLEN = 0.118
gp = K.revolve("Grip", [(0, 0), (0.0095, 0), (0.0125, 0.008), (0.0108, 0.026), (0.0122, 0.059), (0.0108, 0.092), (0.0125, 0.110), (0.0095, 0.118), (0, 0.118)], segs=32, vscale=4.0)
gp.rotation_euler = (0, math.pi / 2, 0); gp.location = (-GLEN / 2, GY, GZ); apply_transform(gp); grip.append(K.set_mat(gp, wood))
for sx in (-1, 1):
    lug = box(f"BailLug{sx}", (0.006, 0.010, 0.012), (sx * 0.0315, 0, 0.283)); lug = K.bevel_apply(lug, 0.0012, 2); uv_box(lug, scale=UVS); body.append(K.set_mat(lug, iron))
    eye = K.revolve(f"BailEye{sx}", [(0.0045 + 0.0016 * math.cos(2 * math.pi * k / 8), 0.0016 * math.sin(2 * math.pi * k / 8)) for k in range(8)], segs=16, closed_loop=True)
    eye.rotation_euler = (0, math.pi / 2, 0); eye.location = (sx * 0.0365, 0, 0.283); apply_transform(eye); body.append(K.set_mat(eye, iron))
    body.append(tube(f"Bail{sx}", [(sx * 0.0375, 0, 0.283), (sx * 0.056, -0.004, 0.279), (sx * 0.074, -0.022, 0.262), (sx * 0.079, -hw - 0.010, 0.222),
                                    (sx * 0.076, GY + 0.004, 0.186), (sx * 0.068, GY, GZ + 0.004), (sx * 0.0625, GY, GZ)], 0.0019, 10))
body.append(tube("GripRod", [(-GLEN / 2 - 0.004, GY, GZ), (GLEN / 2 + 0.004, GY, GZ)], 0.0019, 10))
# candle + holder + flame (flame = emissive; a small practical light is added for renders only)
candle.append(K.set_mat(K.revolve("Holder", [(0, 0.026), (0.024, 0.026), (0.024, 0.029), (0.0165, 0.031), (0.0165, 0.044), (0.0150, 0.044), (0.0150, 0.032), (0, 0.032)], segs=40, vscale=UVS), iron))
cw = K.set_mat(K.revolve("Wax", [(0, 0.032), (0.0138, 0.032), (0.0138, 0.112), (0.0128, 0.1155), (0.006, 0.1162), (0.0035, 0.1145), (0, 0.114)], segs=40, vscale=8), wax)
candle.append(cw)
wick = cylinder("Wick", 0.0007, 0.008, (0, 0, 0.118), segs=8); apply_transform(wick); uv_box(wick, scale=UVS); candle.append(K.set_mat(wick, dark))
fl = K.set_mat(K.revolve("FlameMesh", [(0, 0.1175), (0.0035, 0.1205), (0.0050, 0.1265), (0.0042, 0.1335), (0.0018, 0.1405), (0, 0.1445)], segs=20), flame)

def J(name, objs): return K.join(name, objs)
L_body = J("Lantern_Body", body); L_glass = J("Lantern_Glass", panes); L_door = J("Lantern_Door", door_parts)
L_grip = grip[0]; L_grip.name = "Lantern_Grip"; L_candle = J("Lantern_Candle", candle); fl.name = "Lantern_Flame"
L_door.data.transform(Matrix.Translation((-HX, -HY, 0))); L_door.location = (HX, HY, 0)   # pivot on the hinge axis (+Z rotation opens)
model = [L_body, L_glass, L_door, L_grip, L_candle, fl]
print("PARTS", {o.name: len(o.data.polygons) for o in model})
os.makedirs(OUT, exist_ok=True)
if "--check" in argv:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lantern_check.blend")); sys.exit(0)
stats = K.export_all(model, OUT, "lantern", extra={"door_pivot": "Lantern_Door origin on the hinge axis; rotate -Z to open",
                                                   "reference": "examples/models/lantern/lantern_reference_cc0.jpg (CC0)"})
L_door.rotation_euler = (0, 0, math.radians(-DOOR))
K.studio(scale=0.40)
pl = bpy.data.lights.new("CandleLight", "POINT"); pl.energy = 1.2; pl.color = (1.0, 0.62, 0.3); pl.shadow_soft_size = 0.004
plo = link(bpy.data.objects.new("CandleLight", pl)); plo.location = (0, 0, 0.128); plo["practical"] = True
cam = camera("Cam_Hero", (-0.40, -0.82, 0.40), (0.0, 0.0, 0.160), lens=48)
for o in (L_glass, L_door): o.visible_shadow = False   # renders: no caustics, so glass must not block light into the lantern
try: bpy.ops.file.pack_all()
except Exception as e: print("pack failed", e)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lantern.blend"), compress=True)
if "--no-renders" not in argv:
    t = K.render_sets(sc, model, cam, os.path.join(OUT, "renders"), "lantern", wire_thickness=0.00022, hide_for_clay=(fl,), samples=SAMPLES,
                      res=tuple(map(int, arg("--res", "1920x1080").split("x"))), skip=tuple(arg("--skip", "").split(",")))
    json.dump(t, open(os.path.join(OUT, "renders", "render_times.json"), "w"), indent=1)
