"""Small linear-instrument helpers for the offline E1 calibration proxy."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def ideal_linear_instrument(angles_deg: Sequence[float]) -> np.ndarray:
    """Return Kx3 ideal analyzer matrix for [S0, S1, S2]."""

    angles = np.deg2rad(np.asarray(tuple(angles_deg), dtype=np.float64))
    if angles.ndim != 1 or angles.size < 3:
        raise ValueError("At least three one-dimensional analyzer angles are required")
    return 0.5 * np.column_stack(
        [np.ones_like(angles), np.cos(2.0 * angles), np.sin(2.0 * angles)]
    )


def solve_stokes(
    measurements: np.ndarray,
    instrument: np.ndarray,
    *,
    offsets: np.ndarray | None = None,
) -> np.ndarray:
    """Solve Stokes vectors from measurements whose final axis is analyzer state."""

    values = np.asarray(measurements, dtype=np.float64)
    matrix = np.asarray(instrument, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 3:
        raise ValueError(f"instrument must be Kx3, got {matrix.shape}")
    if values.shape[-1] != matrix.shape[0]:
        raise ValueError(
            f"measurement states {values.shape[-1]} != instrument rows {matrix.shape[0]}"
        )
    corrected = values
    if offsets is not None:
        offset = np.asarray(offsets, dtype=np.float64)
        if offset.shape != (matrix.shape[0],):
            raise ValueError(f"offset shape {offset.shape} is not {(matrix.shape[0],)}")
        corrected = corrected - offset
    return corrected @ np.linalg.pinv(matrix).T


def estimate_affine_instrument(
    known_stokes: np.ndarray, measurements: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate analyzer matrix and per-state offset from known calibration states."""

    stokes = np.asarray(known_stokes, dtype=np.float64)
    values = np.asarray(measurements, dtype=np.float64)
    if stokes.ndim != 2 or stokes.shape[1] != 3:
        raise ValueError(f"known_stokes must be Nx3, got {stokes.shape}")
    if values.ndim != 2 or values.shape[0] != stokes.shape[0]:
        raise ValueError("measurements must be NxK and align with known_stokes")
    design = np.column_stack([stokes, np.ones(stokes.shape[0])])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    instrument = coefficients[:3, :].T
    offsets = coefficients[3, :]
    return instrument, offsets
