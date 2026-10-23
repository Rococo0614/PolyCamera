#!/usr/bin/env python3
"""Audit one aligned HAMMER-style sample without training a model."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from poldepth.metrics import (
    depth_boundary_mask,
    depth_metrics,
    observed_support_bbox_mask,
)
from poldepth.polarization import (
    polarization_features,
    quadrant_pairing_scores,
    split_polar_quadrants,
)


def load_image(path: str) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image)


def parse_named_path(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected NAME=PATH")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("Expected non-empty NAME=PATH")
    return name, path


def json_safe(value):
    """Replace non-finite scalars so the report is strict JSON."""

    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    if isinstance(value, np.integer):
        return int(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt", required=True, help="Ground-truth depth PNG")
    parser.add_argument(
        "--depth",
        action="append",
        type=parse_named_path,
        default=[],
        metavar="NAME=PATH",
        help="Sensor depth; repeat for multiple sensors",
    )
    parser.add_argument("--polar", help="2x2 polarization composite")
    parser.add_argument("--label", help="Optional aligned instance/material label PNG")
    parser.add_argument(
        "--polar-order",
        default="0,45,90,135",
        help="Row-major quadrant labels. Must be verified for the dataset.",
    )
    parser.add_argument("--depth-unit", choices=("mm", "m"), default="mm")
    parser.add_argument(
        "--boundary-threshold",
        type=float,
        help="GT depth jump in input units; defaults to 20 mm",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gt = load_image(args.gt).astype(np.float64)
    if gt.ndim == 3:
        gt = gt[..., 0]
    scale = 1.0 if args.depth_unit == "mm" else 1000.0
    boundary_threshold = args.boundary_threshold
    if boundary_threshold is None:
        boundary_threshold = 20.0 if args.depth_unit == "mm" else 0.02
    boundary_mask = depth_boundary_mask(gt, threshold=boundary_threshold)

    report: dict[str, object] = {
        "ground_truth": args.gt,
        "depth_unit": args.depth_unit,
        "metrics_report_unit": "mm",
        "depth": {},
    }
    predictions: dict[str, np.ndarray] = {}
    for name, path in args.depth:
        prediction = load_image(path).astype(np.float64)
        if prediction.ndim == 3:
            prediction = prediction[..., 0]
        predictions[name] = prediction
        support_mask, support_bbox = observed_support_bbox_mask(prediction)
        report["depth"][name] = {
            "path": path,
            "metrics": depth_metrics(prediction, gt, unit_scale=scale),
            "observed_support_bbox_xyxy": list(support_bbox) if support_bbox else None,
            "observed_support_fraction": float(np.mean(support_mask)),
            "within_observed_support_metrics": depth_metrics(
                prediction, gt, mask=support_mask, unit_scale=scale
            ),
            "boundary_metrics": depth_metrics(
                prediction, gt, mask=boundary_mask, unit_scale=scale
            ),
        }

    features = None
    if args.polar:
        order = tuple(item.strip() for item in args.polar_order.split(","))
        composite = load_image(args.polar)
        channels = split_polar_quadrants(composite, order=order)
        features = polarization_features(
            channels,
            saturation_value=float(np.iinfo(composite.dtype).max)
            if np.issubdtype(composite.dtype, np.integer)
            else None,
        )
        report["polarization"] = {
            "path": args.polar,
            "quadrant_order_hypothesis": list(order),
            "warning": "Angle convention must be verified before physical interpretation.",
            "opposite_pairing_scores": quadrant_pairing_scores(composite),
            "valid_fraction": float(np.mean(features["valid"])),
            "low_signal_fraction": float(np.mean(features["low_signal"])),
            "saturated_fraction": float(np.mean(features["saturated"])),
            "mean_dolp_on_valid": float(np.mean(features["dolp"][features["valid"]]))
            if np.any(features["valid"])
            else None,
            "mean_pair_residual": float(np.mean(features["pair_residual"])),
            "mean_heuristic_confidence": float(np.mean(features["confidence"])),
        }

    if args.label:
        labels = load_image(args.label).squeeze()
        if labels.shape != gt.shape:
            raise ValueError(f"Label shape {labels.shape} does not match GT {gt.shape}")
        per_label: dict[str, object] = {}
        for value in np.unique(labels):
            label_mask = labels == value
            entry: dict[str, object] = {
                "pixels": int(label_mask.sum()),
                "fraction": float(np.mean(label_mask)),
                "depth": {
                    name: depth_metrics(prediction, gt, mask=label_mask, unit_scale=scale)
                    for name, prediction in predictions.items()
                },
            }
            if features is not None:
                valid = label_mask & features["valid"]
                entry["polarization"] = {
                    "valid_fraction_within_label": float(valid.sum() / label_mask.sum()),
                    "mean_dolp_on_valid": float(np.mean(features["dolp"][valid]))
                    if np.any(valid)
                    else None,
                    "mean_confidence": float(np.mean(features["confidence"][label_mask])),
                }
            per_label[str(int(value))] = entry
        report["labels"] = {"path": args.label, "per_label": per_label}

    if features is not None and predictions:
        conditioned: dict[str, object] = {}
        bin_edges = (0.0, 0.05, 0.1, 0.2, 0.4, 1.000001)
        for name, prediction in predictions.items():
            joint = (
                (gt > 0)
                & np.isfinite(gt)
                & (prediction > 0)
                & np.isfinite(prediction)
                & features["valid"]
            )
            absolute_error = np.abs(prediction - gt)
            if int(joint.sum()) > 1:
                dolp_error_correlation = float(
                    np.corrcoef(features["dolp"][joint], absolute_error[joint])[0, 1]
                )
                confidence_error_correlation = float(
                    np.corrcoef(features["confidence"][joint], absolute_error[joint])[0, 1]
                )
            else:
                dolp_error_correlation = None
                confidence_error_correlation = None

            bins: list[dict[str, object]] = []
            for lower, upper in zip(bin_edges[:-1], bin_edges[1:], strict=True):
                bin_mask = (
                    features["valid"]
                    & (features["dolp"] >= lower)
                    & (features["dolp"] < upper)
                )
                bins.append(
                    {
                        "dolp_min": lower,
                        "dolp_max": min(upper, 1.0),
                        "pixels": int(bin_mask.sum()),
                        "metrics": depth_metrics(
                            prediction, gt, mask=bin_mask, unit_scale=scale
                        ),
                    }
                )
            conditioned[name] = {
                "dolp_vs_abs_error_pearson": dolp_error_correlation,
                "heuristic_confidence_vs_abs_error_pearson": confidence_error_correlation,
                "dolp_bins": bins,
            }
        report["polarization_conditioned_depth"] = conditioned

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(json_safe(report), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
