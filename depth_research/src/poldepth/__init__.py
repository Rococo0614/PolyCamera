"""Core analysis utilities for polarization-guided depth research."""

from .metrics import (
    binary_auroc,
    binary_average_precision,
    depth_boundary_mask,
    depth_metrics,
    erode_mask,
    observed_support_bbox_mask,
    silent_error_detection_metrics,
)
from .polarization import (
    polarization_features,
    quadrant_pairing_scores,
    split_polar_quadrants,
)

__all__ = [
    "depth_metrics",
    "binary_auroc",
    "binary_average_precision",
    "depth_boundary_mask",
    "erode_mask",
    "observed_support_bbox_mask",
    "silent_error_detection_metrics",
    "polarization_features",
    "quadrant_pairing_scores",
    "split_polar_quadrants",
]
