"""Image -> 3D pipeline: background removal (rembg) -> TripoSR reconstruction -> mesh cleanup -> exports."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import mesh_tools

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "third_party"))  # vendored TripoSR (MIT)


@dataclass
class Options:
    resolution: int = 256          # marching-cubes grid; 192 = faster, 320 = finer
    foreground_ratio: float = 0.85
    target_faces: int | None = 40000
    formats: tuple[str, ...] = mesh_tools.FORMATS
    stl_height_mm: float | None = 80.0
    rembg_model: str = "isnet-general-use"
    device: str = "auto"


class ImageTo3D:
    def __init__(self, opts: Options | None = None):
        import rembg
        import torch
        from tsr.system import TSR

        self.opts = opts or Options()
        self.torch = torch
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if self.opts.device == "auto" else self.opts.device
        self.model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
        self.model.renderer.set_chunk_size(8192)
        self.model.to(self.device)
        self.rembg = rembg.new_session(self.opts.rembg_model)

    def preprocess(self, image: Image.Image) -> Image.Image:
        from tsr.utils import remove_background, resize_foreground

        image = image.convert("RGBA")
        alpha = np.array(image)[:, :, 3]
        if alpha.min() == 255:  # no transparency yet -> cut the object out
            image = remove_background(image.convert("RGB"), self.rembg)
        image = resize_foreground(image, self.opts.foreground_ratio)
        arr = np.array(image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5  # neutral grey bg, as in TripoSR
        return Image.fromarray((arr * 255.0).astype(np.uint8))

    def convert(self, image_path: Path, out_dir: Path, name: str | None = None) -> dict:
        t0 = time.time()
        name = name or image_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        prepared = self.preprocess(Image.open(image_path))
        prepared.save(out_dir / f"{name}_input.png")
        with self.torch.no_grad():
            codes = self.model([prepared], device=self.device)
        mesh = self.model.extract_mesh(codes, True, resolution=self.opts.resolution)[0]
        mesh = mesh_tools.orient_y_up(mesh)
        mesh = mesh_tools.clean(mesh)
        mesh = mesh_tools.decimate(mesh, self.opts.target_faces)
        mesh = mesh_tools.normalize(mesh)
        files = mesh_tools.export_all(mesh, out_dir, name, self.opts.formats, self.opts.stl_height_mm)
        files["input"] = f"{name}_input.png"
        st = mesh_tools.stats(mesh)
        seconds = time.time() - t0
        mesh_tools.write_report(out_dir, name, image_path.name, st, files, seconds)
        return {"name": name, "files": files, "stats": st.__dict__, "seconds": round(seconds, 1)}
