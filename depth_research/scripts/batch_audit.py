#!/usr/bin/env python3
"""Aggregate raw sensor and polarization statistics over downloaded samples."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from poldepth.metrics import (
    silent_error_detection_metrics,
    depth_boundary_mask,
    depth_metrics,
    erode_mask,
    observed_support_bbox_mask,
)
from poldepth.polarization import (
    polarization_features,
    quadrant_pairing_scores,
    split_polar_quadrants,
)


SENSOR_FOLDERS = {
    "d435": "depth_d435",
    "l515": "depth_l515",
    "itof": "depth_tof",
}
DOLP_BINS = (0.0, 0.05, 0.1, 0.2, 0.4, 1.000001)
SILENT_ERROR_THRESHOLDS_MM = (25.0, 50.0, 100.0)


def load(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image)


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prefixed_metrics(metrics: dict[str, float | int], prefix: str = "") -> dict[str, object]:
    return {f"{prefix}{key}": value for key, value in metrics.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Root containing extracted ZIP paths")
    parser.add_argument("--output", required=True)
    parser.add_argument("--polar-order", default="0,45,90,135")
    args = parser.parse_args()

    root = Path(args.root)
    output = Path(args.output)
    order = tuple(item.strip() for item in args.polar_order.split(","))

    frame_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    polar_rows: list[dict[str, object]] = []
    dolp_bin_rows: list[dict[str, object]] = []
    slice_rows: list[dict[str, object]] = []
    incomplete_rows: list[dict[str, object]] = []
    error_detection_rows: list[dict[str, object]] = []

    ground_truth_files = sorted(root.glob("*/polarization/_gt/*.png"))
    if not ground_truth_files:
        raise SystemExit(f"No samples found under {root}/*/polarization/_gt")

    for gt_path in ground_truth_files:
        sample_root = gt_path.parent.parent
        trajectory = sample_root.parent.name
        frame = gt_path.stem
        required_paths = {
            "polar": sample_root / "pol" / gt_path.name,
            "label": sample_root / "_instance" / gt_path.name,
            **{
                sensor: sample_root / folder / gt_path.name
                for sensor, folder in SENSOR_FOLDERS.items()
            },
        }
        missing = [name for name, path in required_paths.items() if not path.exists()]
        if missing:
            incomplete_rows.append(
                {
                    "trajectory": trajectory,
                    "frame": frame,
                    "missing_modalities": "/".join(missing),
                }
            )
            continue
        gt = load(gt_path).astype(np.float64).squeeze()
        boundary_mask = depth_boundary_mask(gt, threshold=20.0)

        polar_path = sample_root / "pol" / gt_path.name
        features = None
        if polar_path.exists():
            composite = load(polar_path)
            features = polarization_features(
                split_polar_quadrants(composite, order=order),
                saturation_value=float(np.iinfo(composite.dtype).max)
                if np.issubdtype(composite.dtype, np.integer)
                else None,
            )
            pairing_scores = quadrant_pairing_scores(composite)
            valid = features["valid"]
            polar_rows.append(
                {
                    "trajectory": trajectory,
                    "frame": frame,
                    "quadrant_order_hypothesis": "/".join(order),
                    **pairing_scores,
                    "valid_fraction": float(np.mean(valid)),
                    "low_signal_fraction": float(np.mean(features["low_signal"])),
                    "saturated_fraction": float(np.mean(features["saturated"])),
                    "mean_dolp": float(np.mean(features["dolp"][valid]))
                    if np.any(valid)
                    else np.nan,
                    "mean_pair_residual": float(np.mean(features["pair_residual"])),
                    "mean_confidence": float(np.mean(features["confidence"])),
                }
            )

        label_path = sample_root / "_instance" / gt_path.name
        labels = load(label_path).squeeze() if label_path.exists() else None

        for sensor, folder in SENSOR_FOLDERS.items():
            depth_path = sample_root / folder / gt_path.name
            if not depth_path.exists():
                continue
            prediction = load(depth_path).astype(np.float64).squeeze()
            metrics = depth_metrics(prediction, gt)
            support_mask, support_bbox = observed_support_bbox_mask(prediction)
            support_metrics = depth_metrics(prediction, gt, mask=support_mask)
            frame_rows.append(
                {
                    "trajectory": trajectory,
                    "frame": frame,
                    "sensor": sensor,
                    "observed_support_bbox_xyxy": "/".join(map(str, support_bbox))
                    if support_bbox
                    else "",
                    "observed_support_fraction": float(np.mean(support_mask)),
                    **prefixed_metrics(support_metrics, "within_support_"),
                    **prefixed_metrics(metrics),
                }
            )
            slice_rows.append(
                {
                    "trajectory": trajectory,
                    "frame": frame,
                    "sensor": sensor,
                    "slice": "gt_depth_boundary_20mm_band_r2",
                    "slice_pixels": int(boundary_mask.sum()),
                    **prefixed_metrics(
                        depth_metrics(prediction, gt, mask=boundary_mask)
                    ),
                }
            )

            if labels is not None:
                for label_id in np.unique(labels):
                    label_mask = labels == label_id
                    label_interior_mask = erode_mask(label_mask, radius=5)
                    label_support_mask = label_mask & support_mask
                    label_rows.append(
                        {
                            "trajectory": trajectory,
                            "frame": frame,
                            "sensor": sensor,
                            "label_id": int(label_id),
                            "label_pixels": int(label_mask.sum()),
                            "label_interior_pixels_r5": int(
                                label_interior_mask.sum()
                            ),
                            **prefixed_metrics(
                                depth_metrics(
                                    prediction, gt, mask=label_interior_mask
                                ),
                                "interior_r5_",
                            ),
                            "label_pixels_in_observed_support": int(
                                label_support_mask.sum()
                            ),
                            **prefixed_metrics(
                                depth_metrics(
                                    prediction, gt, mask=label_support_mask
                                ),
                                "within_support_",
                            ),
                            **prefixed_metrics(
                                depth_metrics(prediction, gt, mask=label_mask)
                            ),
                        }
                    )

            if features is not None:
                anomaly_scores = {
                    "dolp": features["dolp"],
                    "pair_residual": features["pair_residual"],
                    "one_minus_polar_confidence": 1.0 - features["confidence"],
                }
                if labels is not None:
                    anomaly_scores["provisional_material_oracle_140_160"] = np.isin(
                        labels, (140, 160)
                    ).astype(np.float64)
                for score_name, anomaly_score in anomaly_scores.items():
                    for threshold in SILENT_ERROR_THRESHOLDS_MM:
                        error_detection_rows.append(
                            {
                                "trajectory": trajectory,
                                "frame": frame,
                                "sensor": sensor,
                                "region": "full_valid_polar",
                                "score": score_name,
                                **silent_error_detection_metrics(
                                    prediction,
                                    gt,
                                    anomaly_score,
                                    error_threshold=threshold,
                                    mask=features["valid"],
                                ),
                            }
                        )
                if labels is not None:
                    for label_id in (140, 160):
                        region_mask = features["valid"] & (labels == label_id)
                        error_detection_rows.append(
                            {
                                "trajectory": trajectory,
                                "frame": frame,
                                "sensor": sensor,
                                "region": f"label_{label_id}_provisional",
                                "score": "dolp",
                                **silent_error_detection_metrics(
                                    prediction,
                                    gt,
                                    features["dolp"],
                                    error_threshold=50.0,
                                    mask=region_mask,
                                ),
                            }
                        )
                for lower, upper in zip(DOLP_BINS[:-1], DOLP_BINS[1:], strict=True):
                    bin_mask = (
                        features["valid"]
                        & (features["dolp"] >= lower)
                        & (features["dolp"] < upper)
                    )
                    dolp_bin_rows.append(
                        {
                            "trajectory": trajectory,
                            "frame": frame,
                            "sensor": sensor,
                            "dolp_min": lower,
                            "dolp_max": min(upper, 1.0),
                            "bin_pixels": int(bin_mask.sum()),
                            **prefixed_metrics(
                                depth_metrics(prediction, gt, mask=bin_mask)
                            ),
                        }
                    )

    write_rows(output / "frame_metrics.csv", frame_rows)
    write_rows(output / "label_metrics.csv", label_rows)
    write_rows(output / "polar_metrics.csv", polar_rows)
    write_rows(output / "dolp_bin_metrics.csv", dolp_bin_rows)
    write_rows(output / "slice_metrics.csv", slice_rows)
    write_rows(output / "incomplete_samples.csv", incomplete_rows)
    write_rows(output / "error_detection_metrics.csv", error_detection_rows)
    complete_samples = len(ground_truth_files) - len(incomplete_rows)
    print(
        f"discovered={len(ground_truth_files)} complete={complete_samples} "
        f"frame_rows={len(frame_rows)} "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
