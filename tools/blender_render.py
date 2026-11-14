"""Blender headless check render: blender -b --python tools/blender_render.py -- model.glb out.png

Proves the delivered GLB opens in Blender (vertex colours wired to a Principled material) and renders a
Cycles CPU product shot on a light studio floor."""
import bpy, sys, math
src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
obs=[o for o in bpy.context.scene.objects if o.type=="MESH"]
for ob in obs:
    mat = bpy.data.materials.new("vc"); mat.use_nodes=True
    n=mat.node_tree.nodes; l=mat.node_tree.links; bsdf=n.get("Principled BSDF")
    a=n.new("ShaderNodeVertexColor"); a.layer_name=ob.data.color_attributes[0].name if ob.data.color_attributes else ""
    l.new(a.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value=0.6
    ob.data.materials.clear(); ob.data.materials.append(mat)
    bpy.context.view_layer.objects.active=ob; ob.select_set(True)
bpy.ops.object.shade_smooth()
sc=bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=30)
pl=bpy.context.active_object; pm=bpy.data.materials.new("floor"); pm.use_nodes=True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value=(0.82,0.83,0.87,1); pl.data.materials.append(pm)
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); sc.collection.objects.link(co); sc.camera=co
co.location=(1.6,-2.9,1.5)
import mathutils
d=mathutils.Vector((0,0,0.45))-co.location; co.rotation_euler=d.to_track_quat('-Z','Y').to_euler(); cam.lens=50
for loc,e,s in [((3,-3,4),350,3),((-4,-1,3),120,4),((0,4,3),250,3)]:
    L=bpy.data.lights.new("l","AREA"); L.energy=e; L.size=s; lo=bpy.data.objects.new("l",L); lo.location=loc
    dd=mathutils.Vector((0,0,0.4))-lo.location; lo.rotation_euler=dd.to_track_quat('-Z','Y').to_euler(); sc.collection.objects.link(lo)
w=bpy.data.worlds.new("w"); sc.world=w; w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.9,0.9,0.95,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.25
sc.render.engine="CYCLES"; sc.cycles.device="CPU"; sc.cycles.samples=48; sc.cycles.use_denoising=True
sc.render.resolution_x=1600; sc.render.resolution_y=1000; sc.view_settings.view_transform="AgX"; sc.view_settings.look="AgX - Punchy"
sc.render.filepath=dst; bpy.ops.render.render(write_still=True)
