"""Re-import the exported GLB / OBJ / FBX in a fresh Blender scene and compare with the source model stats.

    blender -b -P verify_exports.py -- output/chest
"""
import bpy, json, os, sys
from mathutils import Vector
D = sys.argv[sys.argv.index("--") + 1]
src = json.load(open(os.path.join(D, "model_stats.json")))
out = {"source_total_tris": src["total_tris"], "formats": {}}
EXPECT_TEX = {"Wood_Oak_Aged", "Wood_EndGrain"}
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
    # material check: catches empty/default materials (e.g. procedural shaders the exporter could not follow)
    mats, problems = {}, []
    for m in {m for o in ms for m in o.data.materials if m}:
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.use_nodes else None
        if b is None: problems.append(f"{m.name}: no Principled BSDF"); continue
        bc = b.inputs["Base Color"]
        def _img(sock):
            todo = [l.from_node for l in sock.links]
            while todo:
                n = todo.pop(0)
                if n.type == "TEX_IMAGE" and n.image: return n.image.name
                todo += [l.from_node for i in n.inputs for l in i.links]
            return None
        tex = _img(bc) if bc.is_linked else None
        base = tex or [round(x, 3) for x in bc.default_value[:3]]
        mats[m.name] = {"base": base, "metallic": None if b.inputs["Metallic"].is_linked else round(b.inputs["Metallic"].default_value, 3),
                        "roughness": "texture" if b.inputs["Roughness"].is_linked else round(b.inputs["Roughness"].default_value, 3)}
        if not tex and all(abs(x - 1.0) < 1e-3 for x in bc.default_value[:3]): problems.append(f"{m.name}: default white base colour")
        if m.name in EXPECT_TEX and not tex: problems.append(f"{m.name}: base colour texture lost")
    out["formats"][fmt] = {"file_mb": round(os.path.getsize(p) / 1e6, 2), "objects": sorted(o.name for o in ms), "tris": tris,
                           "tris_match_source": tris == src["total_tris"], "bbox_m": dims,
                           "materials": sorted({m.name for o in ms for m in o.data.materials if m}), "images": len(imgs),
                           "material_values": mats, "material_problems": problems}
json.dump(out, open(os.path.join(D, "export_verification.json"), "w"), indent=2)
print("VERIFY", json.dumps(out, indent=1))
bad = {f: v["material_problems"] for f, v in out["formats"].items() if v["material_problems"]}
print("MATERIAL_PROBLEMS", bad or "none")
