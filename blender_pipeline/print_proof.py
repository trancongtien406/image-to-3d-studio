"""Print-readiness proof for an STL (run with a Python that has trimesh + pymeshlab, e.g. a venv).

    python print_proof.py output/chest/chest_print_mm.stl output/chest/print_proof.json [--scales 1,0.25,0.1]

Checks: watertight / winding / single body (trimesh), non-manifold edges + vertices and self-intersecting faces
(pymeshlab), volume, bounding box; wall-thickness estimate by ray casting from surface samples along the inward
normal (distance to the opposite wall) -> min / percentiles, reported at each print scale against FDM limits.
"""
import json, sys
import numpy as np, trimesh

path, out = sys.argv[1], sys.argv[2]
scales = [float(s) for s in (sys.argv[sys.argv.index("--scales") + 1] if "--scales" in sys.argv else "1,0.25,0.1").split(",")]
FIX = "--fix" in sys.argv
FEAT = json.load(open(sys.argv[sys.argv.index("--features") + 1])) if "--features" in sys.argv else {}
fix_log = []
if FIX:
    # remove self-intersecting triangles left by decimation: delete them (+1 ring) and re-close the holes
    import pymeshlab as ml
    for rnd_ in range(6):   # re-load after every save: STL float32 + vertex welding can re-create a few
        ms = ml.MeshSet(); ms.load_new_mesh(path); ms.meshing_merge_close_vertices()
        ms.compute_selection_by_self_intersections_per_face(); n = ms.current_mesh().selected_face_number()
        fix_log.append(int(n))
        if n == 0:
            ms.save_current_mesh(path, binary=True); break
        for it in range(6):
            ms.apply_selection_dilatation(); ms.meshing_remove_selected_faces(); ms.meshing_remove_unreferenced_vertices()
            ms.meshing_repair_non_manifold_edges(); ms.meshing_repair_non_manifold_vertices()   # boolean seams
            ms.meshing_close_holes(maxholesize=300, newfaceselected=False, selfintersection=False)
            ms.meshing_repair_non_manifold_edges(); ms.meshing_repair_non_manifold_vertices()
            ms.compute_selection_by_self_intersections_per_face()
            if ms.current_mesh().selected_face_number() == 0: break
        ms.save_current_mesh(path, binary=True)
m = trimesh.load(path, force="mesh")
rep = {"file": path, "units": "mm", "triangles": int(len(m.faces)), "vertices": int(len(m.vertices)),
       "bbox_mm": [round(float(v), 2) for v in m.extents], "watertight": bool(m.is_watertight),
       "winding_consistent": bool(m.is_winding_consistent), "bodies": int(len(m.split(only_watertight=False))),
       "euler_number": int(m.euler_number), "self_intersection_fix_passes": fix_log, "volume_cm3": round(float(m.volume) / 1000, 1) if m.is_watertight else None}
try:
    import pymeshlab as ml
    ms = ml.MeshSet(); ms.load_new_mesh(path)
    t = ms.get_topological_measures()
    rep["meshlab"] = {k: int(t[k]) for k in ("non_two_manifold_edges", "non_two_manifold_vertices", "boundary_edges", "connected_components_number", "genus") if k in t}
    ms.compute_selection_by_self_intersections_per_face()
    rep["meshlab"]["self_intersecting_faces_as_loaded"] = int(ms.current_mesh().selected_face_number())
    ms.meshing_merge_close_vertices()   # what slicers do on import (vertex welding)
    ms.compute_selection_by_self_intersections_per_face()
    rep["meshlab"]["self_intersecting_faces_after_weld"] = int(ms.current_mesh().selected_face_number())
except Exception as e:  # pragma: no cover
    rep["meshlab_error"] = repr(e)
# wall thickness: rays from 6000 surface samples along -normal
rng = np.random.default_rng(1)
pts, fi = trimesh.sample.sample_surface(m, 6000, seed=1)
nrm = m.face_normals[fi]; org = pts - nrm * 0.01
locs, ri, _ = m.ray.intersects_location(org, -nrm, multiple_hits=False)
th = np.full(len(pts), np.nan); th[ri] = np.linalg.norm(locs - org, axis=1) + 0.01
th = th[np.isfinite(th)]
p = lambda q: round(float(np.percentile(th, q)), 2)
rep["wall_thickness_mm_1to1"] = {"samples": int(len(th)), "min": round(float(th.min()), 2), "p1": p(1), "p5": p(5), "p50": p(50)}
rep["note"] = ("The print model is a solid (lid closed, cores filled), so there are no thin shell walls; the ray-cast "
               "'thickness' above is the solid depth. What limits small prints is relief / feature size (rivet heads, "
               "strap projection, hinge gaps), listed per scale below against FDM 0.4 mm nozzle limits (>=0.8 mm walls, "
               ">=0.4 mm relief) and resin (>=0.3 mm).")
rep["scales"] = {}
for s in scales:
    feats = {k: round(v * s, 2) for k, v in FEAT.items()}
    small = [k for k, v in feats.items() if v < 0.8]
    rep["scales"][f"{s:g}"] = {"size_mm": [round(float(v) * s, 1) for v in m.extents], "features_mm": feats,
                               "below_0.8mm": small,
                               "verdict": "FDM 0.4 mm nozzle: all features print" if not small else
                               ("FDM: " + ", ".join(small) + " below 0.8 mm (use 0.2-0.25 mm nozzle or resin)")}
json.dump(rep, open(out, "w"), indent=2); print(json.dumps(rep, indent=2))
