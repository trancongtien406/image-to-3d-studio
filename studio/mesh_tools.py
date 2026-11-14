"""Pure mesh post-processing (no torch needed) - orientation, cleanup, decimation, export, stats."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import trimesh

FORMATS = ("glb", "obj", "stl")


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


def export_all(mesh: trimesh.Trimesh, out_dir: Path, name: str, formats=FORMATS, stl_height_mm: float | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"unsupported format {fmt!r}, choose from {FORMATS}")
        path = out_dir / f"{name}.{fmt}"
        m = mesh
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
