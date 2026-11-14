"""CLI: python -m studio convert image.jpg [more.jpg] -o outputs/"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import ImageTo3D, Options

ROOT = Path(__file__).resolve().parent.parent


def build_gallery(models_dir: Path) -> Path:
    """Collect every <name>.json report under models_dir into viewer/models.json for the web viewer."""
    items = []
    for report in sorted(models_dir.glob("*/*.json")):
        data = json.loads(report.read_text())
        if "files" not in data:
            continue
        rel = report.parent.relative_to(ROOT).as_posix()
        data["base"] = f"../{rel}/"
        items.append(data)
    out = ROOT / "viewer" / "models.json"
    out.write_text(json.dumps(items, indent=2))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="studio", description="Image to 3D model (GLB/OBJ/STL) with TripoSR")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="convert one or more images")
    c.add_argument("images", nargs="+", type=Path)
    c.add_argument("-o", "--out", type=Path, default=ROOT / "outputs")
    c.add_argument("--resolution", type=int, default=256)
    c.add_argument("--faces", type=int, default=40000, help="target face count after decimation (0 = keep all)")
    c.add_argument("--formats", default="glb,obj,stl")
    c.add_argument("--stl-height-mm", type=float, default=80.0)
    c.add_argument("--device", default="auto")
    g = sub.add_parser("gallery", help="rebuild viewer/models.json from a models folder")
    g.add_argument("dir", type=Path, nargs="?", default=ROOT / "examples" / "models")
    args = p.parse_args(argv)

    if args.cmd == "gallery":
        print(build_gallery(args.dir.resolve()))
        return
    opts = Options(resolution=args.resolution, target_faces=args.faces or None,
                   formats=tuple(args.formats.split(",")), stl_height_mm=args.stl_height_mm, device=args.device)
    engine = ImageTo3D(opts)
    print(f"device: {engine.device}")
    for img in args.images:
        res = engine.convert(img, args.out / img.stem)
        s = res["stats"]
        print(f"{img.name}: {s['vertices']:,} verts / {s['faces']:,} faces, watertight={s['watertight']}, "
              f"{res['seconds']}s -> {args.out / img.stem}")


if __name__ == "__main__":
    main()
