# Vendored from https://github.com/VAST-AI-Research/TripoSR (MIT, (c) 2024 Tripo AI & Stability AI).
# Modification: marching cubes uses scikit-image instead of torchmcubes so it installs on any CPU machine.
from typing import Callable, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from skimage.measure import marching_cubes as _sk_marching_cubes


def marching_cubes(volume: torch.Tensor, level: float):
    """CPU marching cubes via scikit-image (replaces the compiled torchmcubes dependency)."""
    vol = volume.detach().cpu().float().numpy()
    verts, faces, _, _ = _sk_marching_cubes(vol, level)
    return torch.from_numpy(verts.copy()).float(), torch.from_numpy(faces.astype(np.int64).copy())


class IsosurfaceHelper(nn.Module):
    points_range: Tuple[float, float] = (0, 1)

    @property
    def grid_vertices(self) -> torch.FloatTensor:
        raise NotImplementedError


class MarchingCubeHelper(IsosurfaceHelper):
    def __init__(self, resolution: int) -> None:
        super().__init__()
        self.resolution = resolution
        self.mc_func: Callable = marching_cubes
        self._grid_vertices: Optional[torch.FloatTensor] = None

    @property
    def grid_vertices(self) -> torch.FloatTensor:
        if self._grid_vertices is None:
            # keep the vertices on CPU so that we can support very large resolution
            x, y, z = (
                torch.linspace(*self.points_range, self.resolution),
                torch.linspace(*self.points_range, self.resolution),
                torch.linspace(*self.points_range, self.resolution),
            )
            x, y, z = torch.meshgrid(x, y, z, indexing="ij")
            verts = torch.cat(
                [x.reshape(-1, 1), y.reshape(-1, 1), z.reshape(-1, 1)], dim=-1
            ).reshape(-1, 3)
            self._grid_vertices = verts
        return self._grid_vertices

    def forward(
        self,
        level: torch.FloatTensor,
    ) -> Tuple[torch.FloatTensor, torch.LongTensor]:
        level = -level.view(self.resolution, self.resolution, self.resolution)
        # scikit-image returns vertices in (i, j, k) grid order already, so no axis swap is needed
        v_pos, t_pos_idx = self.mc_func(level.detach(), 0.0)
        v_pos = v_pos / (self.resolution - 1.0)
        return v_pos.to(level.device), t_pos_idx.to(level.device)
