"""Mesh validation report for the Blender-built exports (needs trimesh; uses the repo .venv).

    .venv/bin/python blender_pipeline/validate_mesh.py blender_pipeline/output/chest
"""
import json, os, sys
import trimesh

d = sys.argv[1]
rep = {}
for fn, unit in (("chest.glb", "m"), ("chest.obj", "m"), ("chest_print_mm.stl", "mm")):
    p = os.path.join(d, fn)
    if not os.path.exists(p): continue
    s = trimesh.load(p, force="scene")
    meshes = list(s.geometry.values())
    m = trimesh.util.concatenate(meshes)
    k = 100.0 if unit == "m" else 0.1  # -> cm
    ext = (m.bounds[1] - m.bounds[0]) * k
    parts = [g for g in meshes]
    r = {
        "unit_in_file": unit,
        "dimensions_cm_xyz": [round(float(x), 1) for x in ext],
        "triangles": int(len(m.faces)), "vertices": int(len(m.vertices)),
        "submeshes": len(parts),
        "watertight": bool(m.is_watertight), "winding_consistent": bool(m.is_winding_consistent),
        "is_volume": bool(m.is_volume),
    }
    if fn.endswith(".stl"):
        bodies = m.split(only_watertight=False)
        r["bodies"] = len(bodies)
        r["all_bodies_watertight"] = all(b.is_watertight for b in bodies)
        # manifold edges: every edge shared by exactly two faces
        import numpy as np
        e = m.edges_sorted; u, c = np.unique(e, axis=0, return_counts=True)
        r["non_manifold_edges"] = int((c != 2).sum())
        r["volume_cm3"] = round(float(abs(m.volume)) / 1000.0, 1)
    rep[fn] = r
out = os.path.join(d, "mesh_report.json")
json.dump(rep, open(out, "w"), indent=2)
print(json.dumps(rep, indent=2))
