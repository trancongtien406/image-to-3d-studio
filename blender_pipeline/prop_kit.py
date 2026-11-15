"""Shared helpers for the small game-prop samples (potion set, lantern). Run inside `blender -b -P ...`.

* revolve(): lathe/loft from a (r, z[, p]) profile; p = superellipse exponent per ring (2 = round, 8+ = rounded square),
  real cylindrical UVs (U around, V = profile arc length in metres x vscale), optional angular sub-range / wrap.
* tex_material(): Principled material whose channels are image textures linked directly (exporter-safe).
* studio(), render_sets(): grey cyclorama + area lights, beauty / clay / wireframe-over-clay renders.
* export_all(): GLB / FBX / OBJ via export_materials.export_safe + model_stats.json for verify_exports.py.
"""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix
from common import mesh_obj, link, shade_smooth as _ss, look_at, camera, cycles, world_hdri, render_to, shade_smooth, apply_transform, ASSETS
HERE = os.path.dirname(os.path.abspath(__file__)); GEN = os.path.join(HERE, "textures_generated")

def se_xy(r, a, p=2.0, ax=1.0, ay=1.0):
    """Point on a superellipse of 'radius' r (half-size) at parameter angle a."""
    c, s = math.cos(a), math.sin(a)
    e = 2.0 / p
    return (r * ax * math.copysign(abs(c) ** e, c), r * ay * math.copysign(abs(s) ** e, s))

def revolve(name, prof, segs=48, vscale=1.0, a0=0.0, a1=2 * math.pi, closed_loop=False, offset=0.0, ax=1.0, ay=1.0, uv_rect=None):
    """prof: list of (r, z) or (r, z, p). Rings with r == 0 at the ends become poles. a1 - a0 < 2pi -> open sheet.
    closed_loop: the profile itself is a closed loop (torus-like cross-section). uv_rect=(u0, v0, u1, v1) maps the
    sheet into that atlas rectangle (labels); otherwise U = around (whole tiles), V = arc length (m) x vscale."""
    full = abs((a1 - a0) - 2 * math.pi) < 1e-9
    P = [(q[0], q[1], q[2] if len(q) > 2 else 2.0) for q in prof]
    na = segs if full else segs + 1
    sl = [0.0]
    for i in range(1, len(P)): sl.append(sl[-1] + math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]))
    tot = sl[-1] + (math.hypot(P[0][0] - P[-1][0], P[0][1] - P[-1][1]) if closed_loop else 0.0)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); rings = []
    for (r, z, pe) in P:
        if r <= 1e-9 and not closed_loop:
            v = bm.verts.new((0, 0, z)); rings.append([v] * na)
        else:
            row = []
            for i in range(na):
                ang = a0 + (a1 - a0) * i / segs; x, y = se_xy(r + offset, ang, pe, ax, ay); row.append(bm.verts.new((x, y, z)))
            rings.append(row)
    nr = len(rings); rmax = max(q[0] for q in P) or 1e-3
    utiles = max(1, round((a1 - a0) * rmax * vscale))
    def uv_of(k, i, kwrap=False):
        u = i / segs; v = (tot if kwrap else sl[k])
        if uv_rect: return (uv_rect[0] + (uv_rect[2] - uv_rect[0]) * u, uv_rect[1] + (uv_rect[3] - uv_rect[1]) * (v / (sl[-1] or 1)))
        return (u * utiles, v * vscale)
    for k in range(nr - 1 + (1 if closed_loop else 0)):
        k2 = (k + 1) % nr; wrap = closed_loop and k2 == 0
        for i in range(segs):
            i2 = (i + 1) % na if full else i + 1
            corners = [(k, i, False), (k, i + 1, False), (k2, i + 1, wrap), (k2, i, wrap)]
            verts, uvs = [], []
            for (kk, ii, wr) in corners:
                v = rings[kk][ii % na if full else ii]
                if v in verts: continue
                verts.append(v); uvs.append(uv_of(kk, ii, wr))
            if len(verts) < 3: continue
            try: f = bm.faces.new(verts)
            except ValueError: continue
            for lp, uv in zip(f.loops, uvs): lp[uvl].uv = uv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new(name, me)); shade_smooth(o, 40); return o

def img_node(nt, path, non_color, uvmap=None):
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(path, check_existing=True)
    if non_color: t.image.colorspace_settings.name = "Non-Color"
    return t

def tex_material(name, diffuse=None, rough=None, normal=None, metal=None, color=(0.8, 0.8, 0.8), rough_v=0.5, metal_v=0.0,
                 normal_strength=1.0, transmission=0.0, ior=1.5, emission=None, emission_strength=0.0, alpha=1.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]; L = nt.links
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough_v; b.inputs["Metallic"].default_value = metal_v
    b.inputs["IOR"].default_value = ior
    if transmission: b.inputs["Transmission Weight"].default_value = transmission
    if coat: b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1); b.inputs["Emission Strength"].default_value = emission_strength
    if diffuse: L.new(img_node(nt, diffuse, False).outputs["Color"], b.inputs["Base Color"])
    if rough: L.new(img_node(nt, rough, True).outputs["Color"], b.inputs["Roughness"])
    if metal: L.new(img_node(nt, metal, True).outputs["Color"], b.inputs["Metallic"])
    if normal:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal_strength
        L.new(img_node(nt, normal, True).outputs["Color"], nm.inputs["Color"]); L.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m

def gen(fn): return os.path.join(GEN, fn)

def set_mat(o, *mats):
    o.data.materials.clear()
    for m in mats: o.data.materials.append(m)
    return o

def join(name, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); j = bpy.context.view_layer.objects.active; j.name = name; j.data.name = name; return j

def apply_mods(o):
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
    for md in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=md.name)
    apply_transform(o); return o

def bevel_apply(o, width, segs=2, angle=40):
    md = o.modifiers.new("Bevel", "BEVEL"); md.width = width; md.segments = segs; md.limit_method = "ANGLE"; md.angle_limit = math.radians(angle)
    return apply_mods(o)

def studio(scale=1.0, bg=(0.30, 0.30, 0.31), hdri_strength=0.35):
    """Grey cyclorama + 3 area lights, sized by `scale` (1.0 = the 60 cm chest set-up)."""
    world_hdri(os.path.join(ASSETS, "hdris/studio_small_09/studio_small_09_2k.hdr"), strength=hdri_strength, rot_z=math.radians(40), bg_color=bg, bg_strength=1.0)
    prof = [(0.0, 0.0), (2.2 * scale, 0.0)]
    for j in range(1, 13):
        a = (math.pi / 2) * j / 12; prof.append(((2.2 + 1.5 * math.sin(a)) * scale, (1.5 - 1.5 * math.cos(a)) * scale))
    prof.append((3.7 * scale, 8.0 * scale))
    bd = revolve("Backdrop", prof, segs=96)
    bm_ = bmesh.new(); bm_.from_mesh(bd.data); bmesh.ops.remove_doubles(bm_, verts=bm_.verts, dist=1e-6); bm_.to_mesh(bd.data); bm_.free()
    bd.data.uv_layers.clear() if hasattr(bd.data.uv_layers, "clear") else None
    set_mat(bd, tex_material("Backdrop", color=bg, rough_v=0.9))
    def area(nm, loc, tgt, size, power, color=(1, 1, 1)):
        ld = bpy.data.lights.new(nm, "AREA"); ld.size = size * scale; ld.energy = power * scale * scale; ld.color = color
        lo = link(bpy.data.objects.new(nm, ld)); lo.location = Vector(loc) * scale; look_at(lo, Vector(tgt) * scale); return lo
    area("Key", (-1.1, -1.3, 1.5), (0, 0, 0.2), 1.0, 55, (1.0, 0.95, 0.88))
    area("Fill", (1.4, -0.9, 0.7), (0, 0, 0.2), 1.5, 14, (0.9, 0.95, 1.0))
    area("Rim", (0.6, 1.4, 1.3), (0, 0, 0.25), 0.8, 45)
    return bd

def render_sets(sc, model, cam, outdir, prefix, wire_thickness, hide_for_clay=(), samples=128, res=(1920, 1080), skip=()):
    os.makedirs(outdir, exist_ok=True); times = {}
    cycles(sc, samples=samples, res=res)
    if "beauty" not in skip: times["beauty"] = render_to(sc, cam, os.path.join(outdir, f"{prefix}_beauty.png"))
    clay = tex_material("Clay", color=(0.55, 0.53, 0.50), rough_v=0.55)
    saved = {o.name: list(o.data.materials) for o in model}
    for o in model:
        for i in range(len(o.data.materials)): o.data.materials[i] = clay
    hidden = [(o, o.hide_render) for o in hide_for_clay]
    for o in hide_for_clay: o.hide_render = True
    lights = [(o, o.data.energy) for o in bpy.data.objects if o.type == "LIGHT" and o.get("practical")]
    for o, _ in lights: o.data.energy = 0
    if "clay" not in skip: times["clay"] = render_to(sc, cam, os.path.join(outdir, f"{prefix}_clay.png"))
    wm = tex_material("Wire", color=(0.03, 0.05, 0.08), rough_v=0.6); wires = []
    for o in model:
        if o in hide_for_clay: continue
        w_ = o.copy(); w_.data = o.data.copy(); sc.collection.objects.link(w_)
        mw = w_.modifiers.new("Wire", "WIREFRAME"); mw.thickness = wire_thickness; mw.use_replace = True; mw.use_even_offset = False
        w_.data.materials.clear(); w_.data.materials.append(wm); wires.append(w_)
    if "wire" not in skip: times["wire"] = render_to(sc, cam, os.path.join(outdir, f"{prefix}_wire.png"))
    for w_ in wires: bpy.data.objects.remove(w_)
    for o in model:
        for i, mm in enumerate(saved[o.name]): o.data.materials[i] = mm
    for o, h in hidden: o.hide_render = h
    for o, e in lights: o.data.energy = e
    return times

def export_all(model, out, name, extra=None):
    from export_materials import export_safe
    os.makedirs(out, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in model: o.select_set(True)
    bpy.context.view_layer.objects.active = model[0]
    with export_safe({m for o in model for m in o.data.materials if m}):
        bpy.ops.export_scene.gltf(filepath=os.path.join(out, f"{name}.glb"), use_selection=True, export_format="GLB", export_apply=True)
        bpy.ops.export_scene.fbx(filepath=os.path.join(out, f"{name}.fbx"), use_selection=True, apply_unit_scale=True, object_types={"MESH"}, path_mode="COPY", embed_textures=True)
        bpy.ops.wm.obj_export(filepath=os.path.join(out, f"{name}.obj"), export_selected_objects=True, export_materials=True, path_mode="COPY")
    stats = {o.name: {"tris": sum(len(p.vertices) - 2 for p in o.data.polygons), "verts": len(o.data.vertices),
                      "materials": [m.name for m in o.data.materials], "uv": bool(o.data.uv_layers)} for o in model}
    pts = [o.matrix_world @ v.co for o in model for v in o.data.vertices]
    dims = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(3)]
    d = {"objects": stats, "total_tris": sum(v["tris"] for v in stats.values()), "bbox_m": dims}
    if extra: d.update(extra)
    json.dump(d, open(os.path.join(out, "model_stats.json"), "w"), indent=2); print("STATS", json.dumps(d)[:600])
    return d
