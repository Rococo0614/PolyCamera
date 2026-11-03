"""Linear Stokes representations used by the offline E1/E2 experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np


ANGLE_KEYS = ("i0", "i45", "i90", "i135")


def _channel(channels: Mapping[str, np.ndarray], name: str) -> np.ndarray:
    if name not in channels:
        raise ValueError(f"Missing polarization channel: {name}")
    array = np.asarray(channels[name], dtype=np.float64)
    if array.ndim not in (2, 3):
        raise ValueError(f"Expected HxW or HxWxC for {name}, got {array.shape}")
    return array


def linear_stokes(channels: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Recover S0/S1/S2 from nominal 0/45/90/135-degree measurements.

    S0 is the average of the two orthogonal-pair estimates. Absolute AoLP is
    meaningful only after the source dataset or camera angle convention is
    verified.
    """

    i0, i45, i90, i135 = (_channel(channels, key) for key in ANGLE_KEYS)
    shapes = {array.shape for array in (i0, i45, i90, i135)}
    if len(shapes) != 1:
        raise ValueError(f"Polarization channel shapes differ: {sorted(shapes)}")
    s0 = 0.5 * (i0 + i45 + i90 + i135)
    s1 = i0 - i90
    s2 = i45 - i135
    magnitude = np.sqrt(np.square(s1) + np.square(s2))
    safe = np.where(np.abs(s0) > 1e-12, s0, 1.0)
    dolp_raw = magnitude / safe
    aolp = np.mod(0.5 * np.arctan2(s2, s1), np.pi)
    pair_a = i0 + i90
    pair_b = i45 + i135
    pair_residual = np.abs(pair_a - pair_b) / np.maximum(
        0.5 * (np.abs(pair_a) + np.abs(pair_b)), 1e-12
    )
    return {
        "s0": s0,
        "s1": s1,
        "s2": s2,
        "dolp": np.clip(dolp_raw, 0.0, 1.0),
        "dolp_raw": dolp_raw,
        "aolp": aolp,
        "cos_2aolp": np.cos(2.0 * aolp),
        "sin_2aolp": np.sin(2.0 * aolp),
        "pair_residual": pair_residual,
    }


def virtual_analyzer(
    stokes: Mapping[str, np.ndarray], angle_deg: float
) -> np.ndarray:
    """Synthesize an ideal linear-analyzer image at ``angle_deg``."""

    for key in ("s0", "s1", "s2"):
        if key not in stokes:
            raise ValueError(f"Missing Stokes component: {key}")
    theta = math.radians(float(angle_deg))
    return 0.5 * (
        np.asarray(stokes["s0"], dtype=np.float64)
        + np.asarray(stokes["s1"], dtype=np.float64) * math.cos(2.0 * theta)
        + np.asarray(stokes["s2"], dtype=np.float64) * math.sin(2.0 * theta)
    )


def virtual_angle_grid(step_deg: int = 5) -> tuple[int, ...]:
    if step_deg <= 0 or 180 % step_deg:
        raise ValueError("step_deg must be a positive divisor of 180")
    return tuple(range(0, 180, step_deg))


def representation_images(
    channels: Mapping[str, np.ndarray],
    *,
    virtual_angles_deg: Sequence[float] = (),
) -> dict[str, np.ndarray]:
    """Return fixed, analytic-fusion and requested virtual-angle images."""

    fixed = {key: _channel(channels, key) for key in ANGLE_KEYS}
    stack = np.stack([fixed[key] for key in ANGLE_KEYS], axis=0)
    stokes = linear_stokes(fixed)
    images: dict[str, np.ndarray] = {
        **fixed,
        "s0": stokes["s0"],
        "min": np.min(stack, axis=0),
        "median": np.median(stack, axis=0),
        "mean": np.mean(stack, axis=0),
    }
    for angle in virtual_angles_deg:
        images[f"virtual_{float(angle):06.2f}"] = virtual_analyzer(stokes, angle)
    return images


def to_uint8(image: np.ndarray, *, mode: str = "clip") -> np.ndarray:
    """Convert a representation for OCR while making normalization explicit."""

    array = np.asarray(image, dtype=np.float64)
    if mode == "clip":
        scaled = np.clip(array, 0.0, 255.0)
    elif mode == "minmax":
        finite = array[np.isfinite(array)]
        if not finite.size or float(finite.max()) <= float(finite.min()):
            scaled = np.zeros_like(array)
        else:
            scaled = (array - finite.min()) * 255.0 / (finite.max() - finite.min())
    elif mode == "robust":
        finite = array[np.isfinite(array)]
        if not finite.size:
            scaled = np.zeros_like(array)
        else:
            low, high = np.percentile(finite, (1.0, 99.0))
            if high <= low:
                scaled = np.zeros_like(array)
            else:
                scaled = (array - low) * 255.0 / (high - low)
                scaled = np.clip(scaled, 0.0, 255.0)
    else:
        raise ValueError(f"Unknown uint8 conversion mode: {mode}")
    return np.rint(scaled).astype(np.uint8)
