#!/usr/bin/env python3
"""Synthetic affine-instrument recovery used as an E1 software gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from polread.instrument import (
    estimate_affine_instrument,
    ideal_linear_instrument,
    solve_stokes,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--noise-std", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=20261102)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    s0 = rng.uniform(0.2, 1.0, size=args.samples)
    dolp = rng.uniform(0.0, 0.9, size=args.samples)
    aolp = rng.uniform(0.0, np.pi, size=args.samples)
    stokes = np.column_stack(
        [s0, s0 * dolp * np.cos(2.0 * aolp), s0 * dolp * np.sin(2.0 * aolp)]
    )

    actual_angles = np.array([1.3, 43.8, 91.1, 136.7])
    gains = np.array([1.03, 0.96, 1.01, 0.98])
    offsets = np.array([0.006, 0.003, 0.008, 0.004])
    actual_instrument = ideal_linear_instrument(actual_angles) * gains[:, None]
    measurements = stokes @ actual_instrument.T + offsets
    measurements += rng.normal(0.0, args.noise_std, size=measurements.shape)

    calibration_count = args.samples // 2
    estimated_instrument, estimated_offsets = estimate_affine_instrument(
        stokes[:calibration_count], measurements[:calibration_count]
    )
    test_measurements = measurements[calibration_count:]
    test_stokes = stokes[calibration_count:]
    ideal_reconstruction = solve_stokes(
        test_measurements, ideal_linear_instrument([0, 45, 90, 135])
    )
    calibrated_reconstruction = solve_stokes(
        test_measurements, estimated_instrument, offsets=estimated_offsets
    )

    def rmse(prediction: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(prediction - test_stokes))))

    payload = {
        "experiment": "offline-e1-affine-instrument-recovery",
        "proxy_only": True,
        "samples": args.samples,
        "calibration_samples": calibration_count,
        "noise_std": args.noise_std,
        "seed": args.seed,
        "ideal_assumption_stokes_rmse": rmse(ideal_reconstruction),
        "calibrated_stokes_rmse": rmse(calibrated_reconstruction),
        "instrument_max_abs_error": float(
            np.max(np.abs(estimated_instrument - actual_instrument))
        ),
        "offset_max_abs_error": float(np.max(np.abs(estimated_offsets - offsets))),
        "actual_angles_deg": actual_angles.tolist(),
        "actual_gains": gains.tolist(),
        "actual_offsets": offsets.tolist(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    print(f"sha256={hashlib.sha256(encoded.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
