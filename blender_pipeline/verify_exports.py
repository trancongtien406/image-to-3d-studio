"""Re-import the exported GLB / OBJ / FBX in a fresh Blender scene and compare with the source model stats.

    blender -b -P verify_exports.py -- output/chest
"""
import bpy, json, os, sys
from mathutils import Vector
D = sys.argv[sys.argv.index("--") + 1]
src = json.load(open(os.path.join(D, "model_stats.json")))
out = {"source_total_tris": src["total_tris"], "formats": {}}
for fmt, fn in (("glb", "chest.glb"), ("obj", "chest.obj"), ("fbx", "chest.fbx")):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = os.path.join(D, fn)
    if fmt == "glb": bpy.ops.import_scene.gltf(filepath=p)
    elif fmt == "obj": bpy.ops.wm.obj_import(filepath=p)
    else: bpy.ops.import_scene.fbx(filepath=p)
    bpy.context.view_layer.update()
    ms = [o for o in bpy.data.objects if o.type == "MESH"]
    tris = sum(sum(len(pl.vertices) - 2 for pl in o.data.polygons) for o in ms)
    pts = [o.matrix_world @ v.co for o in ms for v in o.data.vertices]
    dims = [round(max(p_[i] for p_ in pts) - min(p_[i] for p_ in pts), 4) for i in range(3)]
    imgs = [i.name for i in bpy.data.images]
    out["formats"][fmt] = {"file_mb": round(os.path.getsize(p) / 1e6, 2), "objects": sorted(o.name for o in ms), "tris": tris,
                           "tris_match_source": tris == src["total_tris"], "bbox_m": dims,
                           "materials": sorted({m.name for o in ms for m in o.data.materials if m}), "images": len(imgs)}
json.dump(out, open(os.path.join(D, "export_verification.json"), "w"), indent=2)
print("VERIFY", json.dumps(out, indent=1))
