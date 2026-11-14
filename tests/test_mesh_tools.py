import json

import numpy as np
import pytest
import trimesh

from studio import mesh_tools


def colored_box():
    m = trimesh.creation.box(extents=(2.0, 1.0, 4.0))
    m.visual.vertex_colors = np.tile([200, 50, 50, 255], (len(m.vertices), 1))
    return m


def test_orient_maps_z_up_to_y_up():
    m = trimesh.creation.box(extents=(1.0, 1.0, 3.0))  # tall along Z (TripoSR frame)
    mesh_tools.orient_y_up(m)
    assert m.extents[1] == pytest.approx(3.0)


def test_normalize_rests_on_ground_and_unit_height():
    m = mesh_tools.normalize(colored_box(), height=1.0)
    lo, hi = m.bounds
    assert hi[1] - lo[1] == pytest.approx(1.0)
    assert lo[1] == pytest.approx(0.0)
    assert (lo[0] + hi[0]) / 2 == pytest.approx(0.0, abs=1e-9)


def test_clean_drops_tiny_floaters():
    main = trimesh.creation.icosphere(subdivisions=3)
    speck = trimesh.creation.icosphere(subdivisions=0, radius=0.01)
    speck.apply_translation([5, 0, 0])
    out = mesh_tools.clean(trimesh.util.concatenate([main, speck]))
    assert len(out.split(only_watertight=False)) == 1


def test_decimate_keeps_colors():
    m = trimesh.creation.icosphere(subdivisions=4)
    m.visual.vertex_colors = np.tile([10, 200, 30, 255], (len(m.vertices), 1))
    out = mesh_tools.decimate(m, 500)
    assert len(out.faces) <= 520
    assert tuple(out.visual.vertex_colors[0][:3]) == (10, 200, 30)


def test_export_all_and_report(tmp_path):
    m = mesh_tools.normalize(colored_box())
    files = mesh_tools.export_all(m, tmp_path, "box", stl_height_mm=50)
    assert set(files) == {"glb", "obj", "stl", "ply"}
    stl = trimesh.load(tmp_path / "box.stl")
    assert stl.extents[1] == pytest.approx(50, rel=1e-3)
    st = mesh_tools.stats(m)
    rep = mesh_tools.write_report(tmp_path, "box", "box.png", st, files, 1.23)
    assert json.loads(rep.read_text())["stats"]["watertight"] is True


def test_export_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        mesh_tools.export_all(colored_box(), tmp_path, "x", formats=("fbx",))


def test_smooth_reduces_noise_but_keeps_volume():
    m = trimesh.creation.icosphere(subdivisions=4)
    rng = np.random.default_rng(0)
    m.vertices += rng.normal(0, 0.02, m.vertices.shape)
    rough = np.std(np.linalg.norm(m.vertices, axis=1))
    vol = m.volume
    mesh_tools.smooth(m, 10)
    assert np.std(np.linalg.norm(m.vertices, axis=1)) < rough
    assert m.volume == pytest.approx(vol, rel=0.05)


def test_srgb_to_linear_darkens_midtones_and_keeps_extremes():
    import numpy as np
    from studio.mesh_tools import srgb_to_linear
    c = np.array([[0, 0, 0, 255], [255, 255, 255, 255], [128, 128, 128, 200]], dtype=np.uint8)
    out = srgb_to_linear(c)
    assert out[0, :3].tolist() == [0, 0, 0] and out[1, :3].tolist() == [255, 255, 255]
    assert 50 <= out[2, 0] <= 56 and out[2, 3] == 200


def test_repair_for_print_closes_open_mesh():
    m = trimesh.creation.icosphere(subdivisions=3)
    m.update_faces(np.arange(len(m.faces)) > 40)  # punch a big hole
    m.remove_unreferenced_vertices()
    assert not m.is_watertight
    fixed, method = mesh_tools.repair_for_print(m, resolution=64, target_faces=None)
    rep = mesh_tools.edge_report(fixed)
    assert rep["watertight"] and rep["open_edges"] == 0 and rep["non_manifold_edges"] == 0
    assert method in ("hole-fill", "voxel-remesh")


def test_real_world_scales_volume_cubically():
    box = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    r = mesh_tools.real_world(box, 100.0)
    assert r["height_mm"] == pytest.approx(100.0)
    assert r["volume_cm3"] == pytest.approx(1000.0, rel=1e-3)
