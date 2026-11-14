"""Post-process an existing model folder into a client delivery pack (no torch / TripoSR needed).

    python -m studio deliver examples/models/chest --height-mm 120 [--fbx]

Writes next to the model:
  <name>_print.stl     watertight, repaired STL scaled to real millimetres (3D-print prototype)
  <name>_print.json    before/after mesh report (open + non-manifold edges, shells, watertight, size, volume)
  <name>.ply           coloured point/mesh exchange format (MeshLab, CloudCompare)
  <name>.fbx           optional, only when Blender is installed (`blender` on PATH or $BLENDER)
and updates <name>.json so the web viewer shows the print panel and extra downloads.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import trimesh

from . import mesh_tools

ROOT = Path(__file__).resolve().parent.parent
BLENDER_FBX = ROOT / "tools" / "blender_glb_to_fbx.py"


def find_blender() -> str | None:
    cand = os.environ.get("BLENDER") or shutil.which("blender")
    return cand if cand and Path(cand).exists() else None


def to_fbx(glb: Path, fbx: Path) -> bool:
    blender = find_blender()
    if not blender:
        return False
    subprocess.run([blender, "-b", "--factory-startup", "-noaudio", "--python", str(BLENDER_FBX), "--", str(glb), str(fbx)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return fbx.exists()


def deliver(model_dir: Path, height_mm: float = 120.0, fbx: bool = False, resolution: int = 128) -> dict:
    model_dir = Path(model_dir)
    report_path = next(p for p in sorted(model_dir.glob("*.json")) if not p.stem.endswith("_print"))
    report = json.loads(report_path.read_text())
    name = report["name"]
    t0 = time.time()
    mesh = trimesh.load(model_dir / report["files"]["glb"], force="mesh")
    # GLB colours are stored linear; the OBJ next to it keeps the original sRGB colours, prefer it as the colour source
    obj = model_dir / report["files"].get("obj", "")
    if obj.is_file():
        mesh = trimesh.load(obj, force="mesh", process=False)
    repaired, method = mesh_tools.repair_for_print(mesh, resolution=resolution)
    pr = mesh_tools.print_report(mesh, repaired, method, height_mm)
    stl = repaired.copy()
    stl.apply_scale(height_mm / float(repaired.extents[1]))
    stl.export(model_dir / f"{name}_print.stl")
    mesh.export(model_dir / f"{name}.ply")
    pr["seconds"] = round(time.time() - t0, 1)
    report["files"]["print_stl"] = f"{name}_print.stl"
    report["files"]["ply"] = f"{name}.ply"
    if fbx and to_fbx(model_dir / report["files"]["glb"], model_dir / f"{name}.fbx"):
        report["files"]["fbx"] = f"{name}.fbx"
    report["print"] = pr
    report["analysis"] = {**mesh_tools.edge_report(mesh), "size_at_120mm": mesh_tools.real_world(mesh, 120.0)}
    (model_dir / f"{name}_print.json").write_text(json.dumps(pr, indent=2))
    report_path.write_text(json.dumps(report, indent=2))
    return report
