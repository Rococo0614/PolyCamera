"""Linear-polarization representations and auditable quality heuristics.

The formulas use the common 0/45/90/135 degree convention. Dataset-specific
quadrant placement and angle zero points must be verified before interpreting
AoLP as an absolute physical direction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


ANGLE_NAMES = ("0", "45", "90", "135")


def split_polar_quadrants(
    image: np.ndarray,
    order: Sequence[str] = ANGLE_NAMES,
) -> dict[str, np.ndarray]:
    """Split a 2x2 polarization composite into named quadrants.

    ``order`` is row-major: top-left, top-right, bottom-left, bottom-right.
    The default is a hypothesis used by public PPFT preprocessing, not a
    verified statement about every HAMMER file.
    """

    array = np.asarray(image)
    if array.ndim not in (2, 3):
        raise ValueError(f"Expected HxW or HxWxC image, got {array.shape}")
    if array.shape[0] % 2 or array.shape[1] % 2:
        raise ValueError(f"Composite dimensions must be even, got {array.shape[:2]}")
    if len(order) != 4 or set(order) != set(ANGLE_NAMES):
        raise ValueError(f"order must be a permutation of {ANGLE_NAMES}, got {order}")

    half_h, half_w = array.shape[0] // 2, array.shape[1] // 2
    quadrants = (
        array[:half_h, :half_w],
        array[:half_h, half_w:],
        array[half_h:, :half_w],
        array[half_h:, half_w:],
    )
    return dict(zip(order, quadrants, strict=True))


def quadrant_pairing_scores(image: np.ndarray) -> dict[str, float]:
    """Score the three possible opposite-angle pairings of a 2x2 composite.

    For ideal linear measurements, two orthogonal measurements sum to S0.
    The correct partition of four unlabeled quadrants should therefore make
    the two pair sums most consistent. This identifies opposite pairs, but it
    cannot recover the absolute angle zero point or signs by itself.
    """

    array = np.asarray(image)
    if array.ndim not in (2, 3) or array.shape[0] % 2 or array.shape[1] % 2:
        raise ValueError(f"Expected even-sized 2x2 composite, got {array.shape}")
    half_h, half_w = array.shape[0] // 2, array.shape[1] // 2
    quadrants = [
        _as_gray_float(array[:half_h, :half_w]),
        _as_gray_float(array[:half_h, half_w:]),
        _as_gray_float(array[half_h:, :half_w]),
        _as_gray_float(array[half_h:, half_w:]),
    ]
    partitions = {
        "q0+q1_vs_q2+q3": ((0, 1), (2, 3)),
        "q0+q2_vs_q1+q3": ((0, 2), (1, 3)),
        "q0+q3_vs_q1+q2": ((0, 3), (1, 2)),
    }
    scores: dict[str, float] = {}
    for name, (first, second) in partitions.items():
        first_sum = quadrants[first[0]] + quadrants[first[1]]
        second_sum = quadrants[second[0]] + quadrants[second[1]]
        denominator = np.maximum(
            0.5 * (np.abs(first_sum) + np.abs(second_sum)), 1e-8
        )
        scores[name] = float(np.mean(np.abs(first_sum - second_sum) / denominator))
    return scores


def _as_gray_float(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image, dtype=np.float64)
    if array.ndim == 2:
        return array
    if array.ndim != 3:
        raise ValueError(f"Expected 2D or 3D image, got {array.shape}")
    if array.shape[-1] == 1:
        return array[..., 0]
    if array.shape[-1] < 3:
        raise ValueError(f"Expected at least three color channels, got {array.shape}")

    # PIL arrays are RGB. This conversion is only for a reproducible grayscale
    # audit; spectral-polarization studies should retain each color channel.
    return 0.2126 * array[..., 0] + 0.7152 * array[..., 1] + 0.0722 * array[..., 2]


def polarization_features(
    channels: Mapping[str, np.ndarray],
    *,
    saturation_value: float | None = None,
    min_intensity: float = 1e-8,
    physical_tolerance: float = 1e-3,
) -> dict[str, np.ndarray]:
    """Compute Stokes features and transparent quality diagnostics.

    Returns S0/S1/S2, DoLP, AoLP, periodic AoLP encoding, channel-pair
    consistency, a validity mask, and a conservative heuristic confidence.
    Confidence is an audit feature, not a calibrated probability.
    """

    missing = set(ANGLE_NAMES) - set(channels)
    if missing:
        raise ValueError(f"Missing polarization channels: {sorted(missing)}")

    raw_channels = [np.asarray(channels[name]) for name in ANGLE_NAMES]
    i0, i45, i90, i135 = (_as_gray_float(channel) for channel in raw_channels)
    if not (i0.shape == i45.shape == i90.shape == i135.shape):
        raise ValueError("All polarization channels must have identical shapes")

    # Averaging the two orthogonal estimates gives S0 = sum(I_theta) / 2.
    s0 = 0.5 * (i0 + i45 + i90 + i135)
    s1 = i0 - i90
    s2 = i45 - i135
    linear_magnitude = np.sqrt(np.square(s1) + np.square(s2))

    safe_s0 = np.where(np.abs(s0) > min_intensity, s0, 1.0)
    dolp_raw = linear_magnitude / safe_s0
    dolp = np.clip(dolp_raw, 0.0, 1.0)
    aolp = np.mod(0.5 * np.arctan2(s2, s1), np.pi)

    pair_sum_a = i0 + i90
    pair_sum_b = i45 + i135
    pair_residual = np.abs(pair_sum_a - pair_sum_b) / np.maximum(
        0.5 * (np.abs(pair_sum_a) + np.abs(pair_sum_b)), min_intensity
    )

    finite = np.isfinite(s0) & np.isfinite(s1) & np.isfinite(s2)
    positive_signal = s0 > min_intensity
    physical = dolp_raw <= 1.0 + physical_tolerance
    if saturation_value is None:
        not_saturated = np.ones_like(finite, dtype=bool)
    else:
        not_saturated = np.ones_like(finite, dtype=bool)
        for raw in raw_channels:
            per_pixel_max = np.max(raw, axis=-1) if raw.ndim == 3 else raw
            not_saturated &= per_pixel_max < saturation_value
    valid = finite & positive_signal & physical & not_saturated

    finite_signal = s0[np.isfinite(s0) & (s0 > 0)]
    reference = float(np.percentile(finite_signal, 95)) if finite_signal.size else 1.0
    signal_score = np.clip(s0 / max(reference, min_intensity), 0.0, 1.0)
    consistency_score = np.exp(-pair_residual)
    confidence = valid.astype(np.float64) * signal_score * consistency_score

    return {
        "s0": s0,
        "s1": s1,
        "s2": s2,
        "dolp": dolp,
        "dolp_raw": dolp_raw,
        "aolp": aolp,
        "cos_2aolp": np.cos(2.0 * aolp),
        "sin_2aolp": np.sin(2.0 * aolp),
        "pair_residual": pair_residual,
        "low_signal": ~positive_signal,
        "saturated": ~not_saturated,
        "valid": valid,
        "confidence": confidence,
    }
