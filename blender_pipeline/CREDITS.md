# Asset credits (Blender pipeline)

| Asset | Licence | Author(s) | Used for |
|---|---|---|---|
| [Dark Wood](https://polyhaven.com/a/dark_wood) texture (Poly Haven) | CC0 | Dario Barresi, Dimitrios Savva, Rico Cilliers | chest planks (colour-graded copy in `output/chest/textures/`) |
| [Velour Velvet](https://polyhaven.com/a/velour_velvet) texture (Poly Haven) | CC0 | colormass, Rico Cilliers | velvet lining (normal + roughness maps, tinted) |
| [Studio Small 09](https://polyhaven.com/a/studio_small_09) HDRI (Poly Haven) | CC0 | Sergej Majboroda | studio lighting (renders only) |

Reference images:
- `examples/models/chest/chest_reference_cc0.jpg` (cropped, unedited): ["Chest - 19c - Kasimov museum-reserve"](https://commons.wikimedia.org/wiki/File:Chest_-_19c_-_Kasimov_museum-reserve.jpg)
  by Wikimedia Commons user Лапоть (Lapot'), **CC0 1.0** public-domain dedication. Used for the CC0-matched look-dev variant
  (`chest_cc0_variant.py`) shown in the portfolio's reference → 3D comparison.
- `examples/models/chest/chest_input.png` is the original **demo concept image** (AI-generated sample input, generator not
  recorded; not a third-party photo, not CC0). The base model geometry was first blocked out from it.
End-grain maps (`make_endgrain.py`), geometry, brass material, backdrop and lights are procedural (`build_chest.py`, MIT like this repo).

Exports: the brass wear shader is render-only. GLB / FBX / OBJ carry Brass_Aged as flat PBR (base colour 0.42/0.30/0.12
linear, metallic 1, roughness 0.45) via `export_materials.py`; the velvet lining exports as a flat tinted colour plus its
CC0 roughness/normal maps.
