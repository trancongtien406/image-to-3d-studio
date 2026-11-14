# Blender production pipeline (hand-built quality, scripted)

The AI path (`studio/`) turns one photo into a mesh in minutes, but the back of the object is guessed and
the surface is soft. For paid orders that need clean topology, real dimensions and a printable file, the
same reference image is rebuilt **parts-based in Blender with Python** (`bpy`, headless) and rendered with
Cycles.

Pilot: the treasure chest from `examples/models/chest/chest_input.png`.

| | |
|---|---|
| Size | 60 x 40 cm body, 63.1 x 45.4 x 44.1 cm overall (W x D x H) incl. handles, lock and hinges |
| Parts | 4 plank rows per face (staggered joints front / back), bottom board, 5 curved lid staves, 3-board lid ends, 3 lid straps, rim + base bands, L-shaped corner straps, 64 rivets, shield lock plate with keyhole, hasp, 2 strap hinges, 2 ring handles |
| Materials | PBR wood (Poly Haven CC0 texture, colour graded and baked into the files), hammered brass, all UV-mapped (grain follows each board) |
| Exports | `chest.glb`, `chest.fbx`, `chest.obj` (+mtl, textures), `chest_print_mm.stl` (single watertight shell, millimetres, Z up), `chest.blend` |
| Renders | front, 3/4, side, back (1920x1080, 64 spp + OpenImageDenoise), clay, wireframe, 360° turntable MP4 |

`output/chest/mesh_report.json` (trimesh) shows dimensions, triangle counts, watertight / manifold status.

```bash
blender -b -P blender_pipeline/build_chest.py -- --out blender_pipeline/output/chest --renders renders/ --samples 64 --turntable
.venv/bin/python blender_pipeline/validate_mesh.py blender_pipeline/output/chest
ffmpeg -framerate 24 -i blender_pipeline/output/chest/tt_frames/f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 turntable.mp4
```

Assets: `blender_pipeline/assets` -> Poly Haven downloads (CC0), see [CREDITS.md](CREDITS.md).

Headless `bpy` scripts are what a render server needs. For interactive sessions the same calls can be made
from an AI client through [MCP for Blender](https://github.com/ahujasid/mcp-for-blender) (Blender GUI addon +
`uvx mcp-for-blender`); it is optional here.
