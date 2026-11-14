"""Shared Blender helpers for the headless pipeline (run inside `blender -b -P ...`)."""
import math, os, random
import bpy, bmesh
from mathutils import Vector, Matrix

ASSETS = os.environ.get("BLENDER_ASSETS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(); me.update()
    return link(bpy.data.objects.new(name, me), coll)


def box(name, size, loc, rot=(0, 0, 0), coll=None):
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = mesh_obj(name, v, f, coll)
    o.location = loc; o.rotation_euler = rot
    return o


def cylinder(name, r, h, loc, segs=32, axis="Z", r2=None, coll=None):
    r2 = r if r2 is None else r2
    v, f = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        v.append((r * math.cos(a), r * math.sin(a), -h / 2))
    for i in range(segs):
        a = 2 * math.pi * i / segs
        v.append((r2 * math.cos(a), r2 * math.sin(a), h / 2))
    for i in range(segs):
        j = (i + 1) % segs
        f.append((i, j, segs + j, segs + i))
    f.append(tuple(reversed(range(segs))))
    f.append(tuple(range(segs, 2 * segs)))
    o = mesh_obj(name, v, f, coll)
    if axis == "X": o.rotation_euler = (0, math.pi / 2, 0)
    elif axis == "Y": o.rotation_euler = (math.pi / 2, 0, 0)
    o.location = loc
    return o


def dome(name, r, h, loc, segs=24, rings=8, coll=None):
    """Closed half-ellipsoid (rivet head), flat side at z=0."""
    v, f = [(0, 0, 0)], []
    for k in range(rings):
        phi = (math.pi / 2) * k / rings
        for i in range(segs):
            a = 2 * math.pi * i / segs
            v.append((r * math.cos(phi) * math.cos(a), r * math.cos(phi) * math.sin(a), h * math.sin(phi)))
    top = len(v); v.append((0, 0, h))
    for i in range(segs):
        f.append((0, 1 + (i + 1) % segs, 1 + i))
    for k in range(rings - 1):
        for i in range(segs):
            a = 1 + k * segs + i; b = 1 + k * segs + (i + 1) % segs
            f.append((a, b, b + segs, a + segs))
    base = 1 + (rings - 1) * segs
    for i in range(segs):
        f.append((base + i, base + (i + 1) % segs, top))
    o = mesh_obj(name, v, f, coll); o.location = loc
    return o


def apply_transform(o):
    o.data.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)


def bevel(o, width, segs=2, limit="ANGLE", harden=True):
    m = o.modifiers.new("Bevel", "BEVEL")
    m.width = width; m.segments = segs; m.limit_method = limit
    m.angle_limit = math.radians(40); m.harden_normals = False
    return m


def shade_smooth(o, angle=35):
    for p in o.data.polygons: p.use_smooth = True
    try:
        o.data.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass


def uv_box(o, scale=1.0, long_axis=0, rnd=None):
    """Planar per-face box UVs in object space; grain (U) runs along `long_axis` when it lies in the face plane."""
    me = o.data
    if not me.uv_layers: me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    rnd = rnd or random.Random(hash(o.name) & 0xffff)
    ou, ov = rnd.random() * 4, rnd.random() * 4
    for p in me.polygons:
        n = [abs(c) for c in p.normal]
        d = n.index(max(n))
        ax = [i for i in range(3) if i != d]
        if long_axis in ax:
            U = long_axis; V = [a for a in ax if a != long_axis][0]
        else:
            U, V = ax
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = (co[U] * scale + ou, co[V] * scale + ov)


ASSETS_TEX_OVERRIDE = None


def tex_path(name, kind, res="2k"):
    d = os.path.join(ASSETS, "textures", name)
    if ASSETS_TEX_OVERRIDE and os.path.exists(os.path.join(ASSETS_TEX_OVERRIDE, f"{name}_{kind}_{res}.jpg")):
        d = ASSETS_TEX_OVERRIDE
    for ext in ("jpg", "png", "exr"):
        p = os.path.join(d, f"{name}_{kind}_{res}.{ext}")
        if os.path.exists(p): return p
    return None


def pbr_material(name, tex=None, color=None, rough=0.5, metal=0.0, scale=1.0, tint=None, hsv=None,
                 bump=0.0, normal_strength=1.0, mapping="UV", coat=0.0, specular=0.5, rough_mul=1.0):
    """Principled material, optionally driven by a Poly Haven texture set (Diffuse / nor_gl / Rough)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if "Coat Weight" in bsdf.inputs: bsdf.inputs["Coat Weight"].default_value = coat
    if color: bsdf.inputs["Base Color"].default_value = (*color, 1)
    if tex:
        tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        L.new(tc.outputs["UV" if mapping == "UV" else "Object"], mp.inputs["Vector"])
        def img(kind, non_color):
            p = tex_path(tex, kind)
            if not p: return None
            t = N.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(p, check_existing=True)
            if non_color: t.image.colorspace_settings.name = "Non-Color"
            if mapping != "UV": t.projection = "BOX"; t.projection_blend = 0.2
            L.new(mp.outputs["Vector"], t.inputs["Vector"])
            return t
        d = img("Diffuse", False)
        if d:
            out = d.outputs["Color"]
            if hsv:
                h = N.new("ShaderNodeHueSaturation")
                h.inputs["Hue"].default_value, h.inputs["Saturation"].default_value, h.inputs["Value"].default_value = hsv
                L.new(out, h.inputs["Color"]); out = h.outputs["Color"]
            if tint:
                mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
                mx.inputs["Factor"].default_value = 1.0
                mx.inputs[7].default_value = (*tint, 1)
                L.new(out, mx.inputs[6]); out = mx.outputs[2]
            L.new(out, bsdf.inputs["Base Color"])
        r = img("Rough", True)
        if r:
            if rough_mul != 1.0:
                mm = N.new("ShaderNodeMath"); mm.operation = "MULTIPLY"; mm.inputs[1].default_value = rough_mul
                L.new(r.outputs["Color"], mm.inputs[0]); L.new(mm.outputs[0], bsdf.inputs["Roughness"])
            else:
                L.new(r.outputs["Color"], bsdf.inputs["Roughness"])
        nm = img("nor_gl", True)
        if nm:
            nn = N.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = normal_strength
            L.new(nm.outputs["Color"], nn.inputs["Color"]); L.new(nn.outputs["Normal"], bsdf.inputs["Normal"])
    elif bump > 0:
        tc = N.new("ShaderNodeTexCoord"); no = N.new("ShaderNodeTexNoise")
        no.inputs["Scale"].default_value = 60; no.inputs["Detail"].default_value = 8
        L.new(tc.outputs["Object"], no.inputs["Vector"])
        b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = bump; b.inputs["Distance"].default_value = 0.002
        L.new(no.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def set_mat(o, m):
    o.data.materials.clear(); o.data.materials.append(m)


def world_hdri(path, strength=1.0, rot_z=0.0, bg_strength=None, bg_color=None):
    w = bpy.data.worlds.new("World"); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new("ShaderNodeOutputWorld")
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value[2] = rot_z
    env = N.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(path)
    bg = N.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    L.new(tc.outputs["Generated"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], env.inputs["Vector"])
    L.new(env.outputs["Color"], bg.inputs["Color"])
    if bg_color is not None:
        # camera sees a flat colour, lighting comes from the HDRI
        bg2 = N.new("ShaderNodeBackground"); bg2.inputs["Color"].default_value = (*bg_color, 1)
        bg2.inputs["Strength"].default_value = bg_strength or 1.0
        lp = N.new("ShaderNodeLightPath"); mix = N.new("ShaderNodeMixShader")
        L.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
        L.new(bg.outputs["Background"], mix.inputs[1]); L.new(bg2.outputs["Background"], mix.inputs[2])
        L.new(mix.outputs["Shader"], out.inputs["Surface"])
    else:
        L.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def cycles(sc, samples=128, res=(1920, 1080), pct=100, denoise=True, threads=0):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = denoise
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 4; sc.cycles.glossy_bounces = 4
    sc.cycles.transmission_bounces = 8; sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = pct
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    if threads:
        sc.render.threads_mode = "FIXED"; sc.render.threads = threads
    sc.render.film_transparent = False


def camera(name, loc, target, lens=50, ortho=None, coll=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.01; cd.clip_end = 500
    if ortho:
        cd.type = "ORTHO"; cd.ortho_scale = ortho
    c = link(bpy.data.objects.new(name, cd), coll)
    c.location = loc
    look_at(c, target)
    return c


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_to(sc, cam, path):
    import time
    sc.camera = cam
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    print(f"RENDERED {path} {dt:.1f}s", flush=True)
    return dt
