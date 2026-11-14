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
    assert set(files) == {"glb", "obj", "stl"}
    stl = trimesh.load(tmp_path / "box.stl")
    assert stl.extents[1] == pytest.approx(50, rel=1e-3)
    st = mesh_tools.stats(m)
    rep = mesh_tools.write_report(tmp_path, "box", "box.png", st, files, 1.23)
    assert json.loads(rep.read_text())["stats"]["watertight"] is True


def test_export_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        mesh_tools.export_all(colored_box(), tmp_path, "x", formats=("fbx",))
