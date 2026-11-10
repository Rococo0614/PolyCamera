"""Linear-polarization forward and inverse models."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

ANALYZER_ANGLES_DEG = (0.0, 45.0, 90.0, 135.0)
MPFA_OFFSETS = {
    "000": (0, 0),
    "045": (0, 1),
    "090": (1, 0),
    "135": (1, 1),
}


def analyzer_matrix(angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG) -> np.ndarray:
    angles = np.deg2rad(np.asarray(tuple(angles_deg), dtype=np.float64))
    if angles.ndim != 1 or angles.size < 3:
        raise ValueError("At least three analyzer angles are required")
    return 0.5 * np.column_stack(
        [np.ones_like(angles), np.cos(2.0 * angles), np.sin(2.0 * angles)]
    )


def analyze_stokes(
    stokes: np.ndarray, angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG
) -> np.ndarray:
    """Project ``[..., S0, S1, S2]`` onto analyzer states."""

    values = np.asarray(stokes, dtype=np.float64)
    if values.shape[-1] != 3:
        raise ValueError(f"Expected final Stokes axis of 3, got {values.shape}")
    return values @ analyzer_matrix(angles_deg).T


def solve_stokes(
    measurements: np.ndarray,
    angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG,
    *,
    gains: np.ndarray | None = None,
    offsets: np.ndarray | None = None,
) -> np.ndarray:
    """Least-squares Stokes estimate from analyzer measurements."""

    values = np.asarray(measurements, dtype=np.float64)
    matrix = analyzer_matrix(angles_deg)
    if values.shape[-1] != matrix.shape[0]:
        raise ValueError("Measurement states and analyzer angles differ")
    corrected = values
    if offsets is not None:
        corrected = corrected - np.asarray(offsets, dtype=np.float64)
    if gains is not None:
        corrected = corrected / np.asarray(gains, dtype=np.float64)
    return corrected @ np.linalg.pinv(matrix).T


def stokes_from_intensity(
    intensity: np.ndarray,
    dolp: np.ndarray | float,
    aolp_deg: np.ndarray | float,
) -> np.ndarray:
    """Build Stokes vectors whose analyzer-mean intensity is ``intensity``.

    Four evenly spaced analyzer measurements average to ``S0/2``.  Therefore
    ``S0 = 2*intensity`` in the image units used by the PolaRGB processed release.
    """

    image = np.asarray(intensity, dtype=np.float64)
    degree = np.asarray(dolp, dtype=np.float64)
    if np.any((degree < 0.0) | (degree > 1.0)):
        raise ValueError("DoLP must lie in [0, 1]")
    angle = np.deg2rad(np.asarray(aolp_deg, dtype=np.float64))
    s0 = 2.0 * image
    s1 = s0 * degree * np.cos(2.0 * angle)
    s2 = s0 * degree * np.sin(2.0 * angle)
    return np.stack(np.broadcast_arrays(s0, s1, s2), axis=-1)


def polarization_metrics(stokes: np.ndarray, *, epsilon: float = 1e-8) -> dict[str, np.ndarray]:
    values = np.asarray(stokes, dtype=np.float64)
    if values.shape[-1] != 3:
        raise ValueError("Stokes final axis must be 3")
    s0, s1, s2 = np.moveaxis(values, -1, 0)
    amplitude = np.hypot(s1, s2)
    return {
        "intensity": 0.5 * s0,
        "dolp": amplitude / np.maximum(s0, epsilon),
        "aolp_deg": np.rad2deg(0.5 * np.arctan2(s2, s1)) % 180.0,
        "amplitude": amplitude,
    }


def virtual_extrema(stokes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    metrics = polarization_metrics(stokes)
    center = metrics["intensity"]
    radius = 0.5 * metrics["amplitude"]
    return center - radius, center + radius


def rotate_reference(stokes: np.ndarray, angle_deg: float) -> np.ndarray:
    """Express Stokes in an analyzer frame rotated by ``angle_deg``."""

    values = np.asarray(stokes, dtype=np.float64)
    alpha = np.deg2rad(2.0 * angle_deg)
    s0, s1, s2 = np.moveaxis(values, -1, 0)
    rotated_s1 = np.cos(alpha) * s1 + np.sin(alpha) * s2
    rotated_s2 = -np.sin(alpha) * s1 + np.cos(alpha) * s2
    return np.stack([s0, rotated_s1, rotated_s2], axis=-1)


def srgb_decode(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def make_mpfa_mosaic(measurements: np.ndarray) -> np.ndarray:
    """Sample HxWx4 analyzer images on a 2x2 MPFA pattern.

    The ordering follows PolarFree's public preprocessing code: 0/45 on the first
    row and 90/135 on the second. This is a monochrome abstraction; Bayer×MPFA is
    intentionally left for the later raw-data audit.
    """

    values = np.asarray(measurements, dtype=np.float64)
    if values.ndim != 3 or values.shape[-1] != 4:
        raise ValueError(f"Expected HxWx4 measurements, got {values.shape}")
    mosaic = np.empty(values.shape[:2], dtype=np.float64)
    for state, key in enumerate(("000", "045", "090", "135")):
        row, column = MPFA_OFFSETS[key]
        mosaic[row::2, column::2] = values[row::2, column::2, state]
    return mosaic


def _normalized_convolution(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    kernel = np.array([[1.0, 2.0, 1.0], [2.0, 4.0, 2.0], [1.0, 2.0, 1.0]])
    padded_values = np.pad(values, 1, mode="edge")
    padded_mask = np.pad(mask, 1, mode="edge")
    numerator = np.zeros_like(values, dtype=np.float64)
    denominator = np.zeros_like(values, dtype=np.float64)
    for row in range(3):
        for column in range(3):
            weight = kernel[row, column]
            numerator += weight * padded_values[row : row + values.shape[0], column : column + values.shape[1]]
            denominator += weight * padded_mask[row : row + values.shape[0], column : column + values.shape[1]]
    return numerator / np.maximum(denominator, 1e-12)


def demosaic_mpfa_bilinear(mosaic: np.ndarray) -> np.ndarray:
    """Return HxWx4 normalized-bilinear analyzer reconstructions."""

    values = np.asarray(mosaic, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(f"Expected HxW mosaic, got {values.shape}")
    channels = []
    for key in ("000", "045", "090", "135"):
        row, column = MPFA_OFFSETS[key]
        mask = np.zeros_like(values)
        mask[row::2, column::2] = 1.0
        channels.append(_normalized_convolution(values * mask, mask))
    return np.stack(channels, axis=-1)
