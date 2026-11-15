"""Re-export chest.glb / .fbx / .obj from the saved chest.blend with exporter-safe materials (no re-render).

    blender -b output/chest/chest.blend -P reexport_chest.py -- output/chest
"""
import bpy, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_materials import export_safe
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "output/chest"
O = bpy.data.objects
model = [O[n] for n in ("Chest_Body_Wood", "Chest_Body_Metal", "Chest_Hinge_Pins", "Chest_Lid_Wood", "Chest_Lid_Metal",
                        "Chest_Lid_Hasp", "Chest_Lining", "Chest_Lid_Lining")]
lid = [O[n] for n in ("Chest_Lid_Wood", "Chest_Lid_Metal", "Chest_Lid_Lining", "Chest_Lid_Hasp")]
for o in lid + [O["Core_Lid"]]: o.rotation_euler = (0, 0, 0)          # export with the lid closed (as the original build)
bpy.context.view_layer.update()
# the saved .blend can carry stale relative texture paths -> point them at the real files next to the blend
BD = os.path.dirname(bpy.data.filepath)
for i in bpy.data.images:
    if i.source == "FILE" and not os.path.exists(bpy.path.abspath(i.filepath)):
        for cand in (os.path.join(BD, "textures", os.path.basename(i.filepath)), os.path.join(BD, os.path.basename(i.filepath))):
            if os.path.exists(cand): i.filepath = cand; i.reload(); print("REMAP", i.name, "->", cand); break
missing = [i.filepath for i in bpy.data.images if i.source == "FILE" and not os.path.exists(bpy.path.abspath(i.filepath))]
print("MISSING_IMAGES", missing)
assert not missing, missing
bpy.ops.object.select_all(action="DESELECT")
for o in model: o.select_set(True)
bpy.context.view_layer.objects.active = model[0]
mats = {m for o in model for m in o.data.materials if m}
rep = {}
with export_safe(mats, rep):
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "chest.glb"), use_selection=True, export_format="GLB", export_apply=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "chest.fbx"), use_selection=True, apply_unit_scale=True, object_types={"MESH"}, path_mode="COPY", embed_textures=True)
    bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "chest.obj"), export_selected_objects=True, export_materials=True, path_mode="COPY")
print("EXPORT_MATERIALS", json.dumps(rep, indent=1))
