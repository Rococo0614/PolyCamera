"""Intensity and linear-polarization reconstruction metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from .polarization import linear_stokes


def circular_aolp_error_radians(reference: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    """Smallest absolute AoLP-axis error in [0, pi/2]."""

    difference = 2.0 * (np.asarray(prediction) - np.asarray(reference))
    wrapped = np.angle(np.exp(1j * difference))
    return 0.5 * np.abs(wrapped)


def polarization_reconstruction_metrics(
    prediction: Mapping[str, np.ndarray],
    reference: Mapping[str, np.ndarray],
    *,
    minimum_s0: float = 0.02,
    minimum_dolp_for_angle: float = 0.05,
    saturation_value: float = 1.0,
) -> dict[str, float | int]:
    keys = ("i0", "i45", "i90", "i135")
    predicted = np.stack([np.asarray(prediction[key], dtype=np.float64) for key in keys])
    target = np.stack([np.asarray(reference[key], dtype=np.float64) for key in keys])
    if predicted.shape != target.shape:
        raise ValueError(f"Prediction/reference mismatch: {predicted.shape} vs {target.shape}")
    intensity_error = predicted - target
    intensity_mse = float(np.mean(np.square(intensity_error)))
    intensity_psnr = math.inf if intensity_mse == 0 else float(-10.0 * math.log10(intensity_mse))

    pred_stokes = linear_stokes(prediction)
    ref_stokes = linear_stokes(reference)
    finite = np.ones(target.shape[1:], dtype=bool)
    for array in (*prediction.values(), *reference.values()):
        finite &= np.isfinite(np.asarray(array))
    unsaturated = np.max(target, axis=0) < saturation_value
    physical_reference = ref_stokes["dolp_raw"] <= 1.0 + 1e-6
    valid = finite & unsaturated & physical_reference & (ref_stokes["s0"] > minimum_s0)
    angle_valid = valid & (ref_stokes["dolp"] > minimum_dolp_for_angle)

    def masked_mean(values: np.ndarray, mask: np.ndarray) -> float:
        return float(np.mean(values[mask])) if np.any(mask) else math.nan

    angle_error = circular_aolp_error_radians(ref_stokes["aolp"], pred_stokes["aolp"])
    return {
        "pixels": int(valid.size),
        "valid_pixels": int(valid.sum()),
        "angle_valid_pixels": int(angle_valid.sum()),
        "valid_fraction": float(valid.mean()),
        "intensity_mae": float(np.mean(np.abs(intensity_error))),
        "intensity_psnr_db": intensity_psnr,
        "s0_mae": masked_mean(np.abs(pred_stokes["s0"] - ref_stokes["s0"]), valid),
        "s1_mae": masked_mean(np.abs(pred_stokes["s1"] - ref_stokes["s1"]), valid),
        "s2_mae": masked_mean(np.abs(pred_stokes["s2"] - ref_stokes["s2"]), valid),
        "dolp_mae": masked_mean(np.abs(pred_stokes["dolp"] - ref_stokes["dolp"]), valid),
        "aolp_mae_deg": math.degrees(masked_mean(angle_error, angle_valid)),
        "prediction_nonphysical_fraction": masked_mean(
            pred_stokes["dolp_raw"] > 1.0 + 1e-6, valid
        ),
    }
