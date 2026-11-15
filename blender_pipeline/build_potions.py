"""Stylized apothecary / potion bottle set, modelled from a CC0 reference photo:
examples/models/potions/potions_reference_cc0.jpg (Wikimedia Commons, MatthewHoobin, CC0 1.0 - see CREDITS.md).

    blender -b -P build_potions.py -- [--out output/potions] [--samples 128] [--no-renders]
Four bottles (square + stopper, tall round, medium round, wide jar), real glass wall thickness (outer + inner surface),
liquid volumes, paper labels on a shared 2:1 atlas, corks; lathe UVs; exports GLB / FBX / OBJ + renders.
"""
import bpy, sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import reset_scene, camera, ASSETS
import prop_kit as K
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d): return argv[argv.index(k) + 1] if k in argv else d
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, arg("--out", "output/potions")); SAMPLES = int(arg("--samples", "128"))
sc = reset_scene()

glass = K.tex_material("Glass_Amber", color=(0.50, 0.20, 0.035), rough_v=0.03, transmission=1.0, ior=1.5)
cork = K.tex_material("Cork", diffuse=K.gen("cork_Diffuse_1k.jpg"), rough=K.gen("cork_Rough_1k.jpg"), normal=K.gen("cork_nor_gl_1k.jpg"), normal_strength=0.8)
label = K.tex_material("Paper_Label", diffuse=K.gen("labels_Diffuse_2k.jpg"), rough=K.gen("labels_Rough_2k.jpg"))
LIQ = [("Liquid_Elixir", (0.55, 0.05, 0.03)), ("Liquid_Tonic", (0.75, 0.38, 0.06)), ("Liquid_Antidote", (0.20, 0.42, 0.10)), ("Liquid_Mana", (0.10, 0.25, 0.75))]
liquids = [K.tex_material(n, color=c, rough_v=0.02, transmission=1.0, ior=1.33) for n, c in LIQ]

def atlas_rect(i):   # labels_Diffuse_2k.jpg is 2048 x 1024, 2 x 2 cells; row 0 = top of the image (v = 1)
    u0 = (i % 2) * 0.5; vt = 1.0 - (i // 2) * 0.5; return (u0 + 0.004, vt - 0.5 + 0.008, u0 + 0.5 - 0.004, vt - 0.008)

B = [  # name, outer profile, inner profile, fill z, label (z0, z1, half-angle or None), closure, position, rot
 dict(n="Bottle_1_Square", p=7,
      outer=[(0, 0), (0.026, 0), (0.030, 0.004), (0.030, 0.105), (0.027, 0.118, 6), (0.020, 0.126, 4), (0.013, 0.131, 2.5), (0.011, 0.134, 2),
             (0.011, 0.150, 2), (0.0135, 0.152, 2), (0.0135, 0.158, 2), (0.0110, 0.160, 2)],
      inner=[(0.0085, 0.160, 2), (0.0085, 0.134, 2), (0.0105, 0.129, 2.5), (0.017, 0.123, 4), (0.0245, 0.115, 6), (0.0275, 0.104), (0.0275, 0.008), (0.024, 0.005), (0, 0.005)],
      fill=0.090, lab=(0.040, 0.067, 0.025), stopper=[(0, 0.140), (0.0080, 0.140), (0.0084, 0.160), (0.006, 0.162), (0.006, 0.166), (0.014, 0.168), (0.016, 0.174), (0.013, 0.181), (0.006, 0.1835), (0, 0.184)],
      pos=(-0.005, -0.035), rot=-22),
 dict(n="Bottle_2_Tall", p=2,
      outer=[(0, 0), (0.038, 0), (0.042, 0.005), (0.042, 0.128), (0.039, 0.142), (0.031, 0.153), (0.020, 0.161), (0.0125, 0.166), (0.012, 0.170), (0.012, 0.181),
             (0.0145, 0.183), (0.0145, 0.189), (0.0105, 0.190)],
      inner=[(0.0095, 0.190), (0.0095, 0.168), (0.0105, 0.164), (0.018, 0.158), (0.029, 0.150), (0.0365, 0.140), (0.0395, 0.127), (0.0395, 0.008), (0.035, 0.005), (0, 0.005)],
      fill=0.105, lab=(0.040, 0.088, 1.13), cork=[(0, 0.174), (0.0090, 0.174), (0.0096, 0.190), (0.0112, 0.1905), (0.0116, 0.201), (0.0106, 0.2045), (0, 0.205)],
      pos=(-0.088, 0.030), rot=-3),
 dict(n="Bottle_3_Round", p=2,
      outer=[(0, 0), (0.029, 0), (0.032, 0.004), (0.032, 0.094), (0.029, 0.106), (0.021, 0.116), (0.0115, 0.123), (0.011, 0.128), (0.011, 0.148), (0.0135, 0.150),
             (0.0135, 0.156), (0.0095, 0.157)],
      inner=[(0.0085, 0.157), (0.0085, 0.126), (0.0095, 0.120), (0.019, 0.113), (0.0265, 0.104), (0.0295, 0.093), (0.0295, 0.007), (0.026, 0.005), (0, 0.005)],
      fill=0.072, lab=(0.030, 0.066, 1.10), cork=[(0, 0.141), (0.0080, 0.141), (0.0086, 0.157), (0.0102, 0.1575), (0.0105, 0.168), (0.0096, 0.171), (0, 0.1712)],
      pos=(0.080, 0.058), rot=-14),
 dict(n="Bottle_4_Jar", p=2,
      outer=[(0, 0), (0.032, 0), (0.035, 0.004), (0.035, 0.074), (0.032, 0.082), (0.0255, 0.087), (0.025, 0.090), (0.025, 0.094), (0.0275, 0.095), (0.0275, 0.100), (0.0235, 0.1005)],
      inner=[(0.0225, 0.1005), (0.0225, 0.088), (0.0245, 0.083), (0.030, 0.079), (0.0325, 0.073), (0.0325, 0.007), (0.029, 0.005), (0, 0.005)],
      fill=0.058, lab=(0.022, 0.058, 1.00), cork=[(0, 0.088), (0.0221, 0.088), (0.0227, 0.100), (0.0262, 0.1008), (0.0266, 0.112), (0.0242, 0.1152), (0, 0.1156)],
      pos=(0.132, -0.050), rot=-22),
]
def face_label(name, r, pe, hw, z0, z1, rect, nx=24, off=0.0004):
    import bmesh
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); V = []
    for j, z in enumerate((z0, z1)):
        row = []
        for i in range(nx + 1):
            x = -hw + 2 * hw * i / nx; y = -(r * (1 - abs(x / r) ** pe) ** (1 / pe) + off); row.append(bm.verts.new((x, y, z)))
        V.append(row)
    for i in range(nx):
        f = bm.faces.new((V[0][i], V[0][i + 1], V[1][i + 1], V[1][i]))
        for lp, (u, v) in zip(f.loops, ((i / nx, 0), ((i + 1) / nx, 0), ((i + 1) / nx, 1), (i / nx, 1))):
            lp[uvl].uv = (rect[0] + (rect[2] - rect[0]) * u, rect[1] + (rect[3] - rect[1]) * v)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = K.link(bpy.data.objects.new(name, me)); K.shade_smooth(o, 40); return o

model, groups = [], {}
for bi, b in enumerate(B):
    pe = b["p"]; prof = [(q[0], q[1], q[2] if len(q) > 2 else pe) for q in b["outer"] + b["inner"]]
    g = K.set_mat(K.revolve(b["n"] + "_Glass", prof, segs=64 if pe == 2 else 72, vscale=8.0), glass)
    # liquid: follows the inner wall 0.6 mm inside, flat meniscus-free top at the fill height
    inn = [q for q in b["inner"] if 0.007 <= q[1] <= b["fill"]]
    lp = [(0, 0.0056), (b["inner"][-2][0] - 0.0006, 0.0056, pe)] + [((q[0] - 0.0006), q[1], q[2] if len(q) > 2 else pe) for q in reversed(inn)]
    rr = lp[-1][0]; lp += [(rr, b["fill"], pe), (0, b["fill"], pe)]
    lq = K.set_mat(K.revolve(b["n"] + "_Liquid", lp, segs=48 if pe == 2 else 72, vscale=8.0), liquids[bi])
    z0, z1, ha = b["lab"]; r_lab = max(q[0] for q in b["outer"])
    if pe == 2:
        lab = K.set_mat(K.revolve(b["n"] + "_Label", [(r_lab, z0, pe), (r_lab, z1, pe)], segs=24, a0=-math.pi / 2 - ha, a1=-math.pi / 2 + ha,
                                  offset=0.0004, uv_rect=atlas_rect(bi)), label)
    else:   # square bottle: label follows the superellipse front face, x sampled uniformly (no text distortion); ha = half-width (m)
        lab = K.set_mat(face_label(b["n"] + "_Label", r_lab, pe, ha, z0, z1, atlas_rect(bi)), label)
    # flip label normals outward check: revolve recalc makes the open sheet consistent; make sure they face away from the axis
    me = lab.data; me.update()
    if sum(p.normal.y for p in me.polygons) > 0: me.flip_normals()
    if "cork" in b: cl = K.set_mat(K.revolve(b["n"] + "_Cork", b["cork"], segs=40, vscale=10.0), cork)
    else: cl = K.set_mat(K.revolve(b["n"] + "_Stopper", b["stopper"], segs=48, vscale=8.0), glass)
    for o in (g, lq, lab, cl):
        o.location = (*b["pos"], 0); o.rotation_euler = (0, 0, math.radians(b["rot"])); model.append(o)
    groups[b["n"]] = [o.name for o in (g, lq, lab, cl)]
print("PARTS", len(model))
if "--check" in argv:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "potions_check.blend")); sys.exit(0)
os.makedirs(OUT, exist_ok=True)
stats = K.export_all(model, OUT, "potions", extra={"bottles": groups, "reference": "examples/models/potions/potions_reference_cc0.jpg (CC0)"})
# studio + renders
K.studio(scale=0.32)
cam = camera("Cam_Hero", (-0.12, -0.68, 0.28), (0.012, 0.0, 0.078), lens=50)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 0.70; cam.data.dof.aperture_fstop = 11
try: bpy.ops.file.pack_all()
except Exception as e: print("pack failed", e)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "potions.blend"), compress=True)
if "--no-renders" not in argv:
    t = K.render_sets(sc, model, cam, os.path.join(OUT, "renders"), "potions", wire_thickness=0.00016, samples=SAMPLES,
                      res=tuple(map(int, arg("--res", "1920x1080").split("x"))), skip=tuple(arg("--skip", "").split(",")))
    json.dump(t, open(os.path.join(OUT, "renders", "render_times.json"), "w"), indent=1)
