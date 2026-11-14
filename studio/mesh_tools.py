"""Pure mesh post-processing (no torch needed) - orientation, cleanup, decimation, export, stats."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import trimesh

FORMATS = ("glb", "obj", "stl", "ply")


@dataclass
class MeshStats:
    vertices: int
    faces: int
    watertight: bool
    width: float
    height: float
    depth: float


def orient_y_up(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """TripoSR's canonical frame is Z-up facing +X; glTF viewers expect Y-up facing +Z."""
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))  # face the camera (+Z)
    return mesh


def normalize(mesh: trimesh.Trimesh, height: float = 1.0) -> trimesh.Trimesh:
    """Scale so the model is `height` units tall, centered on X/Z and resting on the ground (y=0)."""
    lo, hi = mesh.bounds
    size = float(hi[1] - lo[1]) or 1.0
    mesh.apply_scale(height / size)
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    return mesh


def clean(mesh: trimesh.Trimesh, keep_largest: bool = True) -> trimesh.Trimesh:
    """Drop floating fragments, degenerate faces and duplicate vertices; fix winding/normals."""
    if keep_largest:
        parts = mesh.split(only_watertight=False)
        if len(parts) > 1:
            biggest = max(parts, key=lambda m: len(m.faces))
            # keep any part with at least 5% of the largest part's faces (e.g. separate feet)
            keep = [p for p in parts if len(p.faces) >= 0.05 * len(biggest.faces)]
            mesh = trimesh.util.concatenate(keep)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    return mesh


def smooth(mesh: trimesh.Trimesh, iterations: int = 8) -> trimesh.Trimesh:
    """Taubin smoothing: removes marching-cubes stair-stepping without shrinking the volume."""
    if iterations > 0:
        trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=iterations)
    return mesh


def decimate(mesh: trimesh.Trimesh, target_faces: int | None) -> trimesh.Trimesh:
    if not target_faces or len(mesh.faces) <= target_faces:
        return mesh
    colors = mesh.visual.vertex_colors if mesh.visual.kind == "vertex" else None
    out = mesh.simplify_quadric_decimation(face_count=target_faces)
    if colors is not None and len(out.vertices):
        # re-sample vertex colours from the nearest original vertex
        _, idx = trimesh.proximity.ProximityQuery(mesh).vertex(out.vertices)
        out.visual.vertex_colors = colors[idx]
    return out


def stats(mesh: trimesh.Trimesh) -> MeshStats:
    ext = mesh.extents
    return MeshStats(len(mesh.vertices), len(mesh.faces), bool(mesh.is_watertight),
                     round(float(ext[0]), 4), round(float(ext[1]), 4), round(float(ext[2]), 4))


def srgb_to_linear(colors: np.ndarray) -> np.ndarray:
    """Convert uint8 sRGB(A) vertex colors to uint8 linear RGB(A).

    glTF stores COLOR_0 in linear space; writing the sRGB values TripoSR predicts makes models look washed out.
    """
    c = colors.astype(np.float64) / 255.0
    rgb = c[:, :3]
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    out = c.copy()
    out[:, :3] = lin
    return np.clip(np.round(out * 255), 0, 255).astype(np.uint8)


def export_all(mesh: trimesh.Trimesh, out_dir: Path, name: str, formats=FORMATS, stl_height_mm: float | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"unsupported format {fmt!r}, choose from {FORMATS}")
        path = out_dir / f"{name}.{fmt}"
        m = mesh
        if fmt == "glb" and getattr(mesh.visual, "kind", None) == "vertex":
            m = mesh.copy()
            m.visual.vertex_colors = srgb_to_linear(np.asarray(mesh.visual.vertex_colors))
        if fmt == "stl" and stl_height_mm:
            m = mesh.copy()
            m.apply_scale(stl_height_mm / float(mesh.extents[1]))
        m.export(path)
        files[fmt] = path.name
    return files


def write_report(out_dir: Path, name: str, source: str, mesh_stats: MeshStats, files: dict, seconds: float) -> Path:
    report = {"name": name, "source": source, "seconds": round(seconds, 1), "files": files, "stats": asdict(mesh_stats)}
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(report, indent=2))
    return path


# ---------------------------------------------------------------------------------------------------------------
# 3D-print analysis and repair
# ---------------------------------------------------------------------------------------------------------------

def edge_report(mesh: trimesh.Trimesh) -> dict:
    """Count open (boundary) edges and non-manifold edges after merging coincident vertices."""
    m = mesh.copy()
    m.merge_vertices()
    _, counts = np.unique(m.edges_sorted, axis=0, return_counts=True)
    return {
        "open_edges": int((counts == 1).sum()),
        "non_manifold_edges": int((counts > 2).sum()),
        "shells": int(len(m.split(only_watertight=False))),
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
    }


def real_world(mesh: trimesh.Trimesh, height_mm: float) -> dict:
    """Dimensions / area / volume once the model is scaled so its height is `height_mm`."""
    k = height_mm / float(mesh.extents[1] or 1.0)
    w, h, d = (float(x) * k for x in mesh.extents)
    out = {"height_mm": round(h, 1), "width_mm": round(w, 1), "depth_mm": round(d, 1),
           "area_cm2": round(float(mesh.area) * k * k / 100.0, 1), "scale_mm_per_unit": round(k, 4)}
    out["volume_cm3"] = round(float(abs(mesh.volume)) * k ** 3 / 1000.0, 1) if mesh.is_watertight else None
    return out


def transfer_colors(src: trimesh.Trimesh, dst: trimesh.Trimesh) -> trimesh.Trimesh:
    """Copy vertex colours from the nearest vertex of `src` (used after remeshing)."""
    if getattr(src.visual, "kind", None) == "vertex" and len(dst.vertices):
        _, idx = trimesh.proximity.ProximityQuery(src).vertex(dst.vertices)
        dst.visual.vertex_colors = np.asarray(src.visual.vertex_colors)[idx]
    return dst


def repair_for_print(mesh: trimesh.Trimesh, resolution: int = 160, target_faces: int | None = 60000):
    """Return (watertight_mesh, method).

    1. merge vertices + fill small holes + fix normals; if that is already a closed 2-manifold, keep it.
    2. otherwise voxel remesh: voxelize at `resolution` cells along the longest side, flood-fill the inside,
       marching cubes back to a single closed shell, Taubin-smooth, decimate and re-sample the colours.
       This closes holes, fuses overlapping shells and removes non-manifold edges (fine detail below one
       voxel is softened - 160 cells on a 120 mm model is ~0.75 mm).
    """
    m = mesh.copy()
    m.merge_vertices()
    trimesh.repair.fill_holes(m)
    trimesh.repair.fix_normals(m)
    if m.is_watertight and len(m.split(only_watertight=False)) == 1:
        return m, "hole-fill"
    pitch = float(mesh.extents.max()) / resolution
    vox = mesh.voxelized(pitch).fill()
    out = vox.marching_cubes
    out.apply_transform(vox.transform)
    out = trimesh.Trimesh(out.vertices, out.faces, process=True)
    # marching cubes may produce a few tiny internal bubbles; keep the main closed shell(s)
    parts = [p for p in out.split(only_watertight=False)]
    if len(parts) > 1:
        big = max(parts, key=lambda p: len(p.faces))
        out = trimesh.util.concatenate([p for p in parts if len(p.faces) >= 0.05 * len(big.faces)])
    trimesh.smoothing.filter_taubin(out, lamb=0.5, nu=-0.53, iterations=6)
    trimesh.repair.fix_normals(out)
    if target_faces and len(out.faces) > target_faces:
        # quadric decimation can pinch edges; only keep the lighter mesh if it is still a closed manifold
        lighter = out.simplify_quadric_decimation(face_count=target_faces)
        lighter.merge_vertices()
        if lighter.is_watertight and edge_report(lighter)["non_manifold_edges"] == 0:
            trimesh.repair.fix_normals(lighter)
            out = lighter
    # keep the original placement (centred, resting on the ground)
    out.apply_translation([0, mesh.bounds[0][1] - out.bounds[0][1], 0])
    transfer_colors(mesh, out)
    return out, "voxel-remesh"


def print_report(original: trimesh.Trimesh, repaired: trimesh.Trimesh, method: str, height_mm: float) -> dict:
    return {
        "height_mm": height_mm,
        "method": method,
        "before": {**edge_report(original), "faces": int(len(original.faces))},
        "after": {**edge_report(repaired), "faces": int(len(repaired.faces))},
        "size": real_world(repaired, height_mm),
    }
