"""Blender headless helper: blender -b --python tools/blender_glb_to_fbx.py -- in.glb out.fbx

Imports the GLB, turns the COLOR_0 vertex colours into a material (so they survive in Maya / Unity / Unreal)
and exports a binary FBX with Y-up axes and applied transforms.
"""
import sys

import bpy

src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    mat = bpy.data.materials.new(name=f"{ob.name}_vertex_color")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    attr = nodes.new("ShaderNodeVertexColor")
    if ob.data.color_attributes:
        attr.layer_name = ob.data.color_attributes[0].name
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    ob.data.materials.clear()
    ob.data.materials.append(mat)
bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, apply_scale_options="FBX_SCALE_ALL",
                         axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE", colors_type="SRGB")
