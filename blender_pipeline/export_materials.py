"""Exporter-safe material state for GLB / FBX / OBJ.

The render materials use node chains the exporters cannot follow (procedural brass wear from Pointiness/AO/Noise,
per-plank Hue/AO/scratch variation on the wood, a desaturate+tint on the velvet). glTF then writes an EMPTY
material for Brass_Aged (viewer default = white metal) and FBX/OBJ lose the wood diffuse/roughness maps (flat grey).

`export_safe(materials)` temporarily rewires every Principled BSDF into a glTF-compatible form and restores the
original render network afterwards (renders and the saved .blend are unchanged):
  * Base Color / Roughness: if an image texture feeds the chain, link that image directly;
  * procedural-only channels: flat PBR factors from EXPORT_FLAT (measured/approximated from the render shader);
  * procedural Bump normals are unlinked (Normal Map nodes from real textures are kept);
  * transmissive glass materials (name starts with "Glass") also get Alpha = GLASS_EXPORT_ALPHA + blended render method, so glTF writes
    alphaMode BLEND (baseColor alpha < 1) next to KHR_materials_transmission; engines without transmission
    support (e.g. Godot 4.3) then import the glass as alpha-blended instead of opaque.
"""
import contextlib

GLASS_EXPORT_ALPHA = 0.3

# Flat PBR values for procedural-only channels (linear RGB). Brass: average of the aged-brass wear shader
# (tarnish/dull/polished-edge mix) lifted slightly so the part still reads as brass without the edge highlights.
EXPORT_FLAT = {
    "Brass_Aged": {"base": (0.42, 0.30, 0.12), "metallic": 1.0, "roughness": 0.45},
    "Coin_Gold": {"base": (0.95, 0.68, 0.25), "metallic": 1.0, "roughness": 0.22},
}


def _upstream_image(sock, non_color):
    """First image-texture node feeding `sock` (breadth-first through any nodes)."""
    seen, todo = set(), [l.from_node for l in sock.links]
    while todo:
        n = todo.pop(0)
        if n in seen: continue
        seen.add(n)
        if n.type == "TEX_IMAGE" and n.image is not None:
            is_nc = n.image.colorspace_settings.name == "Non-Color"
            if is_nc == non_color: return n
        for i in n.inputs:
            todo += [l.from_node for l in i.links]
    return None


def _tinted_velvet(m, bsdf):
    """Desaturate+tint chain -> flat base colour (mean luminance of the diffuse x tint)."""
    img = _upstream_image(bsdf.inputs["Base Color"], False)
    tint = None
    for n in m.node_tree.nodes:
        if n.type == "MIX" and getattr(n, "blend_type", "") == "MULTIPLY" and not n.inputs[7].is_linked:
            tint = tuple(n.inputs[7].default_value)[:3]
    if img is None or tint is None: return None
    px = list(img.image.pixels[:]); n = len(px) // 4 or 1
    step = max(1, n // 20000)
    lum = sum(0.2126 * px[i * 4] + 0.7152 * px[i * 4 + 1] + 0.0722 * px[i * 4 + 2] for i in range(0, n, step)) / len(range(0, n, step))
    return tuple(c * lum for c in tint)


@contextlib.contextmanager
def export_safe(materials, report=None):
    saved = []   # (material, socket name, [from_sockets], default_value)
    modes = []   # (material, surface_render_method, blend_method)
    try:
        for m in materials:
            if not m or not m.use_nodes: continue
            nt = m.node_tree; L = nt.links
            b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if b is None: continue
            for k in ("Base Color", "Roughness", "Metallic", "Normal"):
                s = b.inputs[k]
                saved.append((m, k, [l.from_socket for l in s.links], tuple(s.default_value) if hasattr(s.default_value, "__len__") else s.default_value))
            flat = dict(EXPORT_FLAT.get(m.name, {}))
            if m.name == "Lining_Velvet":
                c = _tinted_velvet(m, b)
                if c: flat["base"] = c
            act = {}
            # base colour
            s = b.inputs["Base Color"]
            if "base" in flat:
                for l in list(s.links): L.remove(l)
                s.default_value = (*flat["base"], 1.0); act["base"] = "factor"
            elif s.is_linked:
                img = _upstream_image(s, False)
                if img is not None:
                    for l in list(s.links): L.remove(l)
                    L.new(img.outputs["Color"], s); act["base"] = "image:" + img.image.name
            # roughness
            s = b.inputs["Roughness"]
            if "roughness" in flat:
                for l in list(s.links): L.remove(l)
                s.default_value = flat["roughness"]; act["roughness"] = "factor"
            elif s.is_linked:
                img = _upstream_image(s, True)
                if img is not None:
                    for l in list(s.links): L.remove(l)
                    L.new(img.outputs["Color"], s); act["roughness"] = "image:" + img.image.name
            # metallic
            s = b.inputs["Metallic"]
            if "metallic" in flat:
                for l in list(s.links): L.remove(l)
                s.default_value = flat["metallic"]
            # normal: drop procedural bump (keep real normal maps)
            s = b.inputs["Normal"]
            if s.is_linked and s.links[0].from_node.type == "BUMP":
                for l in list(s.links): L.remove(l)
                act["normal"] = "bump dropped"
            # glass: alpha blend for engines that ignore KHR_materials_transmission
            tw = b.inputs.get("Transmission Weight")
            if m.name.startswith("Glass") and tw is not None and not tw.is_linked and tw.default_value > 0.5:
                s = b.inputs["Alpha"]
                saved.append((m, "Alpha", [l.from_socket for l in s.links], s.default_value))
                modes.append((m, getattr(m, "surface_render_method", None), m.blend_method))
                for l in list(s.links): L.remove(l)
                s.default_value = GLASS_EXPORT_ALPHA
                if hasattr(m, "surface_render_method"): m.surface_render_method = "BLENDED"
                m.blend_method = "BLEND"; act["alpha"] = f"blend {GLASS_EXPORT_ALPHA}"
            if report is not None: report[m.name] = act
        yield
    finally:
        for m, k, froms, dv in reversed(saved):
            nt = m.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); s = b.inputs[k]
            for l in list(s.links): nt.links.remove(l)
            for fs in froms: nt.links.new(fs, s)
            s.default_value = dv
        for m, srm, bm in modes:
            if srm is not None: m.surface_render_method = srm
            m.blend_method = bm
