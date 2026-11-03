#!/usr/bin/env python3
"""Audit SHDocs processed four-direction consistency before OCR inference."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from polread.polarization import linear_stokes
from polread.shdocs import discover_captures


def _gray(path: str) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def _safe_correlation(first: np.ndarray, second: np.ndarray) -> float:
    a = first.ravel()
    b = second.ravel()
    if np.std(a) <= 1e-12 or np.std(b) <= 1e-12:
        return math.nan
    return float(np.corrcoef(a, b)[0, 1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-sha256", default="")
    args = parser.parse_args()

    captures = discover_captures(args.images_root)
    rows: list[dict[str, object]] = []
    for capture in captures:
        channels = {
            "i0": _gray(capture.i0_path),
            "i45": _gray(capture.i45_path),
            "i90": _gray(capture.i90_path),
            "i135": _gray(capture.i135_path),
        }
        shapes = {array.shape for array in channels.values()}
        if len(shapes) != 1:
            raise ValueError(f"Channel shape mismatch for {capture.sample_id}: {shapes}")
        stokes = linear_stokes(channels)
        stack = np.stack(tuple(channels.values()))
        valid_signal = np.isfinite(stokes["s0"]) & (stokes["s0"] > 1.0)
        s0_norm = _gray(capture.s0_norm_path)
        deglared = _gray(capture.deglared_path)
        if s0_norm.shape != channels["i0"].shape or deglared.shape != channels["i0"].shape:
            raise ValueError(f"Derived image shape mismatch for {capture.sample_id}")
        rows.append(
            {
                "sample_id": capture.sample_id,
                "document_id": capture.document_id,
                "condition_id": capture.condition_id,
                "width": capture.width,
                "height": capture.height,
                "pair_residual_mean": (
                    float(np.mean(stokes["pair_residual"][valid_signal]))
                    if np.any(valid_signal)
                    else None
                ),
                "nonphysical_dolp_fraction": float(
                    np.mean(stokes["dolp_raw"][valid_signal] > 1.0 + 1e-3)
                ),
                "saturation_fraction": float(np.mean(np.any(stack >= 255.0, axis=0))),
                "low_signal_fraction": float(np.mean(stokes["s0"] <= 5.0)),
                "mean_dolp_valid_signal": float(np.mean(stokes["dolp"][valid_signal])),
                "s0_norm_correlation": _safe_correlation(stokes["s0"], s0_norm),
            }
        )

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["condition_id"])].append(row)
        grouped["ALL"].append(row)
    metric_names = (
        "pair_residual_mean",
        "nonphysical_dolp_fraction",
        "saturation_fraction",
        "low_signal_fraction",
        "mean_dolp_valid_signal",
        "s0_norm_correlation",
    )
    aggregate: dict[str, dict[str, object]] = {}
    for condition, condition_rows in sorted(grouped.items()):
        summary: dict[str, object] = {"captures": len(condition_rows)}
        for metric in metric_names:
            values = [
                float(row[metric])
                for row in condition_rows
                if row[metric] is not None and math.isfinite(float(row[metric]))
            ]
            summary[metric] = float(np.mean(values)) if values else None
        aggregate[condition] = summary

    payload = {
        "experiment": "offline-shdocs-polarization-audit",
        "date": "2026-11-03",
        "proxy_only": True,
        "archive_sha256": args.archive_sha256,
        "captures": len(captures),
        "documents": len({capture.document_id for capture in captures}),
        "aggregate_arithmetic_capture_mean": aggregate,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
    print(f"sha256={hashlib.sha256(encoded.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
