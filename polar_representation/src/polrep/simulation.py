"""Small image-based Stokes layer simulator for P3 identifiability sweeps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .baselines import psnr
from .physics import (
    analyze_stokes,
    demosaic_mpfa_bilinear,
    make_mpfa_mosaic,
    solve_stokes,
    stokes_from_intensity,
    virtual_extrema,
)


@dataclass(frozen=True)
class SimulationConfig:
    reflection_ratio: float
    reflection_dolp: float
    transmission_dolp: float = 0.0
    aolp_difference_deg: float = 45.0
    noise_sigma: float = 0.0
    angle_error_deg: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    gains: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    offsets: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    mpfa_bilinear: bool = False
    seed: int = 20261110


def synthetic_layers(size: int = 96) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic transmission/reflection textures in [0, 1]."""

    y, x = np.mgrid[0:size, 0:size]
    checker = ((x // 12 + y // 12) % 2).astype(np.float64)
    gradient = 0.15 + 0.55 * x / max(size - 1, 1)
    transmission = np.clip(gradient + 0.22 * checker, 0.0, 0.92)
    rings = 0.5 + 0.5 * np.sin(0.18 * np.hypot(x - 0.68 * size, y - 0.35 * size))
    bars = ((x + 2 * y) % 31 < 5).astype(np.float64)
    reflection = np.clip(0.08 + 0.42 * rings + 0.28 * bars, 0.0, 0.9)
    return transmission, reflection


def simulate(config: SimulationConfig, *, size: int = 96) -> dict[str, np.ndarray]:
    transmission, reflection_pattern = synthetic_layers(size)
    reflection = np.clip(config.reflection_ratio * reflection_pattern, 0.0, 2.0)
    transmission_stokes = stokes_from_intensity(
        transmission, config.transmission_dolp, config.aolp_difference_deg
    )
    reflection_stokes = stokes_from_intensity(reflection, config.reflection_dolp, 0.0)
    observed_stokes = transmission_stokes + reflection_stokes
    angles = np.asarray((0.0, 45.0, 90.0, 135.0)) + np.asarray(config.angle_error_deg)
    measurement = analyze_stokes(observed_stokes, angles)
    measurement = measurement * np.asarray(config.gains) + np.asarray(config.offsets)
    if config.noise_sigma > 0.0:
        rng = np.random.default_rng(config.seed)
        measurement = measurement + rng.normal(0.0, config.noise_sigma, measurement.shape)
    measurement = np.clip(measurement, 0.0, 1.0)
    if config.mpfa_bilinear:
        measurement = demosaic_mpfa_bilinear(make_mpfa_mosaic(measurement))
    estimated_stokes = solve_stokes(measurement)
    virtual_min, _ = virtual_extrema(estimated_stokes)
    return {
        "transmission": transmission,
        "reflection": reflection,
        "transmission_stokes": transmission_stokes,
        "reflection_stokes": reflection_stokes,
        "observed_stokes": observed_stokes,
        "measurement": measurement,
        "estimated_stokes": estimated_stokes,
        "mean4": measurement.mean(axis=-1),
        "min4": measurement.min(axis=-1),
        "virtual_min": np.clip(virtual_min, 0.0, 1.0),
    }


def score_simulation(result: dict[str, np.ndarray]) -> dict[str, float]:
    target = result["transmission"]
    observed = result["mean4"]
    return {
        "rgb_psnr": psnr(observed, target),
        "min4_psnr": psnr(result["min4"], target),
        "virtual_min_psnr": psnr(result["virtual_min"], target),
        "min4_gain_db": psnr(result["min4"], target) - psnr(observed, target),
        "virtual_min_gain_db": psnr(result["virtual_min"], target) - psnr(observed, target),
        "stokes_rmse": float(
            np.sqrt(np.mean((result["estimated_stokes"] - result["observed_stokes"]) ** 2))
        ),
        "saturation_share": float(np.mean((result["measurement"] <= 0.0) | (result["measurement"] >= 1.0))),
    }
