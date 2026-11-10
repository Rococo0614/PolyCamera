"""No-learning reflection-suppression baselines and metrics."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import numpy as np
from skimage.metrics import structural_similarity

from .physics import solve_stokes, virtual_extrema


def representations(channels: Mapping[str, np.ndarray], rgb: np.ndarray) -> dict[str, np.ndarray]:
    ordered = [np.asarray(channels[key], dtype=np.float64) for key in ("000", "045", "090", "135")]
    shapes = {value.shape for value in ordered + [np.asarray(rgb)]}
    if len(shapes) != 1:
        raise ValueError(f"Channel shapes differ: {sorted(shapes)}")
    stack = np.stack(ordered, axis=0)
    measurements = np.moveaxis(stack, 0, -1)
    stokes = solve_stokes(measurements)
    virtual_min, virtual_max = virtual_extrema(stokes)
    return {
        "rgb": np.asarray(rgb, dtype=np.float64),
        "angle_000": ordered[0],
        "angle_045": ordered[1],
        "angle_090": ordered[2],
        "angle_135": ordered[3],
        "mean4": stack.mean(axis=0),
        "median4": np.median(stack, axis=0),
        "min4": stack.min(axis=0),
        "virtual_min": np.clip(virtual_min, 0.0, 1.0),
        "virtual_max": np.clip(virtual_max, 0.0, 1.0),
    }


def crop_pair(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a, b = np.asarray(first), np.asarray(second)
    height, width = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    return a[:height, :width], b[:height, :width]


def psnr(first: np.ndarray, second: np.ndarray, *, data_range: float = 1.0) -> float:
    a, b = crop_pair(first, second)
    mse = float(np.mean((a - b) ** 2))
    return 99.0 if mse == 0.0 else 10.0 * math.log10(data_range**2 / mse)


def ssim(first: np.ndarray, second: np.ndarray, *, data_range: float = 1.0) -> float:
    a, b = crop_pair(first, second)
    channel_axis = -1 if a.ndim == 3 else None
    return float(structural_similarity(a, b, data_range=data_range, channel_axis=channel_axis))


@dataclass(frozen=True)
class ChannelAffine:
    gain: tuple[float, ...]
    offset: tuple[float, ...]

    def apply(self, image: np.ndarray) -> np.ndarray:
        array = np.asarray(image, dtype=np.float64)
        gain = np.asarray(self.gain, dtype=np.float64)
        offset = np.asarray(self.offset, dtype=np.float64)
        return np.clip(array * gain + offset, 0.0, 1.0)


class SceneEqualAffineAccumulator:
    """Scene-equal sufficient statistics for ``target = gain*source + offset``."""

    def __init__(self, channels: int = 3) -> None:
        self.channels = channels
        self._scene_stats: dict[str, np.ndarray] = {}

    def add(self, scene: str, source: np.ndarray, target: np.ndarray, *, stride: int = 16) -> None:
        x, y = crop_pair(source, target)
        x = np.asarray(x[::stride, ::stride], dtype=np.float64).reshape(-1, self.channels)
        y = np.asarray(y[::stride, ::stride], dtype=np.float64).reshape(-1, self.channels)
        if not len(x):
            raise ValueError("No pixels after affine-fit subsampling")
        stats = np.stack(
            [
                np.full(self.channels, len(x)),
                x.sum(axis=0),
                y.sum(axis=0),
                (x * x).sum(axis=0),
                (x * y).sum(axis=0),
            ]
        )
        self._scene_stats[scene] = self._scene_stats.get(scene, np.zeros_like(stats)) + stats

    def fit(self) -> ChannelAffine:
        if not self._scene_stats:
            raise ValueError("No affine-fit samples")
        moments = []
        for stats in self._scene_stats.values():
            n, sum_x, sum_y, sum_xx, sum_xy = stats
            moments.append(np.stack([sum_x / n, sum_y / n, sum_xx / n, sum_xy / n]))
        mean_x, mean_y, mean_xx, mean_xy = np.mean(np.stack(moments), axis=0)
        variance = np.maximum(mean_xx - mean_x**2, 1e-12)
        gain = (mean_xy - mean_x * mean_y) / variance
        offset = mean_y - gain * mean_x
        return ChannelAffine(tuple(float(x) for x in gain), tuple(float(x) for x in offset))


def oracle_channel_affine(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, ChannelAffine]:
    """Per-image GT-fitted color ceiling; never a deployable baseline."""

    x, y = crop_pair(source, target)
    if x.ndim != 3 or x.shape[-1] != 3:
        raise ValueError("oracle_channel_affine expects RGB images")
    flattened_x = x.reshape(-1, 3)
    flattened_y = y.reshape(-1, 3)
    mean_x, mean_y = flattened_x.mean(axis=0), flattened_y.mean(axis=0)
    variance = np.maximum(np.mean((flattened_x - mean_x) ** 2, axis=0), 1e-12)
    gain = np.mean((flattened_x - mean_x) * (flattened_y - mean_y), axis=0) / variance
    offset = mean_y - gain * mean_x
    model = ChannelAffine(tuple(float(v) for v in gain), tuple(float(v) for v in offset))
    return model.apply(source), model
