"""CC0-reference look-dev variant of the chest, matched to examples/models/chest/chest_reference_cc0.jpg.

Opens a COPY of output/chest/chest.blend, splits the joined metal into iron straps/bands, red-painted rim trim and brass
fittings (by connected component), restains the wood reddish-brown, raises the body x1.15 and flattens the dome x0.78,
then renders a matched camera. The default chest model and its GLB/FBX/OBJ exports are not modified.

    blender -b chest_copy.blend --python chest_cc0_variant.py -- --out ref_match_cc0.png --lens 60 [--res 1440x1440 --samples 128 --save]
"""
import bpy, bmesh, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mesh_components import comps
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg('--out', 'ref_match_cc0.png'); PCT = int(arg('--pct', '100')); SAMP = int(arg('--samples', '128'))
sc = bpy.context.scene

def principled(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    return m, b

def noisy(m, b, c1, c2, scale=60.0, bump=0.25):
    N, L = m.node_tree.nodes, m.node_tree.links
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.65
    L.new(nz.outputs['Fac'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], b.inputs['Base Color'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])

iron, ib = principled('Iron_Blackened', (0.03, 0.028, 0.026), 0.55, 0.75); noisy(iron, ib, (0.02, 0.019, 0.018), (0.055, 0.047, 0.04), 90, 0.06)
trim, tb = principled('Trim_RedPaint', (0.30, 0.07, 0.045), 0.62); noisy(trim, tb, (0.15, 0.03, 0.018), (0.27, 0.075, 0.045), 70, 0.05); tb.inputs['Roughness'].default_value = 0.72
brass = bpy.data.materials['Brass_Aged']

# wood: reddish-brown stained planks like the reference
w = bpy.data.materials['Wood_Oak_Aged']; N, L = w.node_tree.nodes, w.node_tree.links; b = N['Principled BSDF']
src = b.inputs['Base Color'].links[0].from_socket
hs = N.new('ShaderNodeHueSaturation'); hs.inputs['Hue'].default_value = 0.47; hs.inputs['Saturation'].default_value = 0.6; hs.inputs['Value'].default_value = 1.0
mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs['Factor'].default_value = 1.0; mx.inputs[7].default_value = (0.85, 0.56, 0.48, 1)
L.new(src, hs.inputs['Color']); L.new(hs.outputs['Color'], mx.inputs[6]); L.new(mx.outputs[2], b.inputs['Base Color'])
we = bpy.data.materials['Wood_EndGrain']; N2 = we.node_tree.nodes; b2 = N2['Principled BSDF']
if b2.inputs['Base Color'].links:
    s2 = b2.inputs['Base Color'].links[0].from_socket; m2 = N2.new('ShaderNodeMix'); m2.data_type = 'RGBA'; m2.blend_type = 'MULTIPLY'; m2.inputs['Factor'].default_value = 1; m2.inputs[7].default_value = (0.8, 0.45, 0.38, 1)
    we.node_tree.links.new(s2, m2.inputs[6]); we.node_tree.links.new(m2.outputs[2], b2.inputs['Base Color'])

stat = {}
for n in ('Chest_Body_Metal', 'Chest_Lid_Metal'):
    o = bpy.data.objects[n]; me = o.data
    me.materials.append(iron); me.materials.append(trim); i_iron = len(me.materials) - 2; i_trim = i_iron + 1
    C = comps(o); bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    for grp, mn, mx_, mats in C:
        d = mx_ - mn; c = (mn + mx_) / 2
        if 0 not in mats: continue
        long_ = max(d) >= 0.17; hinge = abs(abs(c.x) - 0.17) < 0.012 and c.y > 0.15 if n == 'Chest_Body_Metal' else abs(abs(c.x) - 0.17) < 0.012 and c.y > -0.05
        horiz = long_ and d.z < 0.05 and max(d.x, d.y) > 0.35
        if horiz and not (n == 'Chest_Body_Metal' and c.z < 0.1): k = i_trim   # red-painted rim slats (lid edge + upper rim)
        elif long_ or hinge: k = i_iron
        else: continue                                                       # studs, corner caps, lock, hasp stay brass
        stat[k] = stat.get(k, 0) + 1
        for fi in grp:
            if bm.faces[fi].material_index == 0: bm.faces[fi].material_index = k
    bm.to_mesh(me); bm.free()
print('ASSIGN', stat)
# aged, darker brass like the reference fittings
bb = brass.node_tree.nodes['Principled BSDF']; bl = brass.node_tree.links
if bb.inputs['Base Color'].links:
    s3 = bb.inputs['Base Color'].links[0].from_socket; m3 = brass.node_tree.nodes.new('ShaderNodeMix'); m3.data_type = 'RGBA'; m3.blend_type = 'MULTIPLY'
    m3.inputs['Factor'].default_value = 1; m3.inputs[7].default_value = tuple(map(float, arg('--brass', '0.5,0.42,0.30,1').split(','))); bl.new(s3, m3.inputs[6]); bl.new(m3.outputs[2], bb.inputs['Base Color'])
else:
    bb.inputs['Base Color'].default_value = (0.40, 0.29, 0.12, 1)
bb.inputs['Roughness'].default_value = 0.58
print('BRASS linked', bool(bb.inputs['Base Color'].links), [n.bl_idname for n in brass.node_tree.nodes])
# proportions closer to the reference trunk: taller body, flatter dome
KB, KL = float(arg('--kb', '1.15')), float(arg('--kl', '0.78'))
HZ = bpy.data.objects['Chest_Lid_Metal'].location.z
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render: continue
    if o.name in ('Chest_Body_Metal', 'Chest_Body_Wood', 'Chest_Lining'): o.scale.z *= KB; o.location.z *= KB
    elif o.name in ('Chest_Lid_Wood', 'Chest_Lid_Metal', 'Chest_Lid_Lining'): o.location.z = HZ * KB + (o.location.z - HZ); o.scale.z *= KL
    elif o.name in ('Chest_Lid_Hasp', 'Chest_Hinge_Pins'): o.location.z += HZ * (KB - 1)
    print('OBJ', o.name, tuple(round(v, 3) for v in o.location), tuple(round(v, 3) for v in o.scale))
for o in bpy.data.objects:
    if o.name.startswith('Chest_Lid'): o.rotation_euler = (0, 0, 0)
from mathutils import Vector
cam = bpy.data.objects['Cam_reference_match']
loc = Vector(tuple(map(float, arg('--loc', '0.80,-1.42,1.02').split(',')))); tgt = Vector(tuple(map(float, arg('--tgt', '0,0,0.24').split(','))))
cam.location = loc; cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = float(arg('--lens', '50'))
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = map(int, arg('--res', '1440x1440').split('x')); sc.render.resolution_percentage = PCT
sc.cycles.samples = SAMP; sc.cycles.use_denoising = True; sc.cycles.device = 'CPU'
sc.render.filepath = os.path.abspath(OUT); bpy.ops.render.render(write_still=True)
if '--save' in argv: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath('chest_cc0_variant.blend'), compress=True)
