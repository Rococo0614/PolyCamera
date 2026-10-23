"""Depth metrics with explicit validity and coverage accounting."""

from __future__ import annotations

import math

import numpy as np


def _binary_ranking_metrics(
    target: np.ndarray, score: np.ndarray
) -> tuple[float, float]:
    labels = np.asarray(target, dtype=bool).ravel()
    scores = np.asarray(score, dtype=np.float64).ravel()
    valid = np.isfinite(scores)
    labels, scores = labels[valid], scores[valid]
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    if positives == 0:
        return math.nan, math.nan

    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_ranks = np.arange(1, len(scores) + 1, dtype=np.float64)
    starts = np.r_[0, np.flatnonzero(np.diff(sorted_scores)) + 1]
    ends = np.r_[starts[1:], len(scores)]
    for start, end in zip(starts, ends, strict=True):
        sorted_ranks[start:end] = 0.5 * (start + end + 1)
    ranks = np.empty_like(sorted_ranks)
    ranks[order] = sorted_ranks
    if negatives:
        statistic = ranks[labels].sum() - positives * (positives + 1) / 2
        auroc = float(statistic / (positives * negatives))
    else:
        auroc = math.nan

    descending_order = order[::-1]
    descending_labels = labels[descending_order]
    descending_scores = scores[descending_order]
    cumulative_tp = np.cumsum(descending_labels)
    group_ends = np.r_[np.flatnonzero(np.diff(descending_scores)), len(scores) - 1]
    tp = cumulative_tp[group_ends]
    predicted = group_ends + 1
    precision = tp / predicted
    recall = tp / positives
    previous_recall = np.r_[0.0, recall[:-1]]
    average_precision = float(np.sum((recall - previous_recall) * precision))
    return auroc, average_precision


def binary_auroc(target: np.ndarray, score: np.ndarray) -> float:
    """Compute tie-aware binary AUROC without scikit-learn."""

    return _binary_ranking_metrics(target, score)[0]


def binary_average_precision(target: np.ndarray, score: np.ndarray) -> float:
    """Compute threshold-grouped average precision for a binary target."""

    return _binary_ranking_metrics(target, score)[1]


def silent_error_detection_metrics(
    prediction: np.ndarray,
    ground_truth: np.ndarray,
    anomaly_score: np.ndarray,
    *,
    error_threshold: float,
    mask: np.ndarray | None = None,
) -> dict[str, float | int]:
    """Evaluate detection of valid-but-wrong sensor depth pixels."""

    pred = np.asarray(prediction, dtype=np.float64).squeeze()
    gt = np.asarray(ground_truth, dtype=np.float64).squeeze()
    score = np.asarray(anomaly_score, dtype=np.float64).squeeze()
    if not (pred.shape == gt.shape == score.shape):
        raise ValueError("prediction, ground_truth, and anomaly_score must align")
    valid = np.isfinite(pred) & (pred > 0) & np.isfinite(gt) & (gt > 0) & np.isfinite(score)
    if mask is not None:
        valid &= np.asarray(mask, dtype=bool).squeeze()
    target = np.abs(pred[valid] - gt[valid]) >= error_threshold
    selected_score = score[valid]
    auroc, average_precision = _binary_ranking_metrics(target, selected_score)
    return {
        "evaluated_pixels": int(valid.sum()),
        "error_threshold": float(error_threshold),
        "positive_pixels": int(target.sum()),
        "positive_fraction": float(np.mean(target)) if target.size else math.nan,
        "auroc": auroc,
        "average_precision": average_precision,
    }


def erode_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Binary square erosion without an external image-processing dependency."""

    binary = np.asarray(mask, dtype=bool).squeeze()
    if binary.ndim != 2:
        raise ValueError(f"Expected a 2D mask, got {binary.shape}")
    if radius < 0:
        raise ValueError("radius must be non-negative")
    if radius == 0:
        return binary.copy()
    padded = np.pad(binary, radius, mode="constant")
    eroded = np.ones_like(binary)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            eroded &= padded[dy : dy + binary.shape[0], dx : dx + binary.shape[1]]
    return eroded


def observed_support_bbox_mask(depth: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    """Approximate a sensor's warped support by the bbox of positive depth.

    This is a diagnostic fallback when an exact calibration/FoV mask is not
    available. It separates large outside-FoV borders from holes inside the
    observed rectangle, but it must not replace a true static support mask in
    final experiments.
    """

    array = np.asarray(depth, dtype=np.float64).squeeze()
    if array.ndim != 2:
        raise ValueError(f"Expected a 2D depth map, got {array.shape}")
    valid = np.isfinite(array) & (array > 0)
    rows, columns = np.nonzero(valid)
    mask = np.zeros_like(valid)
    if not rows.size:
        return mask, None
    x_min, x_max = int(columns.min()), int(columns.max())
    y_min, y_max = int(rows.min()), int(rows.max())
    mask[y_min : y_max + 1, x_min : x_max + 1] = True
    return mask, (x_min, y_min, x_max, y_max)


def depth_boundary_mask(
    ground_truth: np.ndarray,
    *,
    threshold: float,
    dilation_radius: int = 2,
) -> np.ndarray:
    """Return a band around valid GT depth discontinuities.

    ``threshold`` uses the same unit as ``ground_truth``. Both pixels adjacent
    to a horizontal/vertical discontinuity are marked, then dilated with a
    square neighborhood. Image borders and invalid GT are not boundaries by
    themselves.
    """

    gt = np.asarray(ground_truth, dtype=np.float64).squeeze()
    if gt.ndim != 2:
        raise ValueError(f"Expected a 2D depth map, got {gt.shape}")
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if dilation_radius < 0:
        raise ValueError("dilation_radius must be non-negative")

    valid = np.isfinite(gt) & (gt > 0)
    boundary = np.zeros_like(valid)
    horizontal = valid[:, 1:] & valid[:, :-1] & (
        np.abs(gt[:, 1:] - gt[:, :-1]) >= threshold
    )
    vertical = valid[1:, :] & valid[:-1, :] & (
        np.abs(gt[1:, :] - gt[:-1, :]) >= threshold
    )
    boundary[:, 1:] |= horizontal
    boundary[:, :-1] |= horizontal
    boundary[1:, :] |= vertical
    boundary[:-1, :] |= vertical

    if dilation_radius:
        padded = np.pad(boundary, dilation_radius, mode="constant")
        dilated = np.zeros_like(boundary)
        for dy in range(2 * dilation_radius + 1):
            for dx in range(2 * dilation_radius + 1):
                dilated |= padded[dy : dy + gt.shape[0], dx : dx + gt.shape[1]]
        boundary = dilated
    return boundary & valid


def depth_metrics(
    prediction: np.ndarray,
    ground_truth: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    min_depth: float = 1e-6,
    max_depth: float | None = None,
    unit_scale: float = 1.0,
) -> dict[str, float | int]:
    """Evaluate depth while keeping invalid predictions visible via coverage.

    ``unit_scale`` converts input units to the report unit. For example, use
    1000 when input arrays are in metres and millimetre errors are desired.
    Error metrics are computed where GT and prediction are both valid;
    ``coverage`` reports how much valid GT received a valid prediction.
    """

    pred = np.asarray(prediction, dtype=np.float64).squeeze()
    gt = np.asarray(ground_truth, dtype=np.float64).squeeze()
    if pred.shape != gt.shape:
        raise ValueError(f"Shape mismatch: prediction {pred.shape}, GT {gt.shape}")

    gt_valid = np.isfinite(gt) & (gt > min_depth)
    if max_depth is not None:
        gt_valid &= gt <= max_depth
    if mask is not None:
        explicit = np.asarray(mask, dtype=bool).squeeze()
        if explicit.shape != gt.shape:
            raise ValueError(f"Mask shape {explicit.shape} does not match {gt.shape}")
        gt_valid &= explicit

    pred_valid = np.isfinite(pred) & (pred > min_depth)
    if max_depth is not None:
        pred_valid &= pred <= max_depth
    joint = gt_valid & pred_valid

    gt_count = int(gt_valid.sum())
    valid_count = int(joint.sum())
    coverage = valid_count / gt_count if gt_count else math.nan
    result: dict[str, float | int] = {
        "gt_valid_pixels": gt_count,
        "evaluated_pixels": valid_count,
        "coverage": float(coverage),
        "invalid_prediction_rate": float(1.0 - coverage) if gt_count else math.nan,
    }
    if valid_count == 0:
        result.update(
            {
                "mae": math.nan,
                "rmse": math.nan,
                "mean_signed_error": math.nan,
                "median_signed_error": math.nan,
                "positive_error_fraction": math.nan,
                "abs_rel": math.nan,
                "delta_1": math.nan,
                "delta_2": math.nan,
                "delta_3": math.nan,
                "p95_abs_error": math.nan,
                "p99_abs_error": math.nan,
            }
        )
        return result

    pred_v = pred[joint]
    gt_v = gt[joint]
    error = pred_v - gt_v
    abs_error = np.abs(error)
    scaled_abs_error = abs_error * unit_scale
    ratio = np.maximum(pred_v / gt_v, gt_v / pred_v)

    result.update(
        {
            "mae": float(np.mean(scaled_abs_error)),
            "rmse": float(np.sqrt(np.mean(np.square(error))) * unit_scale),
            "mean_signed_error": float(np.mean(error) * unit_scale),
            "median_signed_error": float(np.median(error) * unit_scale),
            "positive_error_fraction": float(np.mean(error > 0)),
            "abs_rel": float(np.mean(abs_error / gt_v)),
            "delta_1": float(np.mean(ratio < 1.25)),
            "delta_2": float(np.mean(ratio < 1.25**2)),
            "delta_3": float(np.mean(ratio < 1.25**3)),
            "p95_abs_error": float(np.percentile(scaled_abs_error, 95)),
            "p99_abs_error": float(np.percentile(scaled_abs_error, 99)),
        }
    )
    return result
