#!/usr/bin/env python3
"""Run full-channel/noisy and simple MPFA interpolation baselines on PDD."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from polread.mosaic import demosaic_bilinear, demosaic_nearest, make_mpfa_mosaic
from polread.pdd import discover_pdd_scenes, load_pdd_channels
from polread.polar_metrics import polarization_reconstruction_metrics


def _json_value(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-sha256", default="")
    args = parser.parse_args()

    scenes = discover_pdd_scenes(args.root)
    if not scenes:
        raise SystemExit(f"No PDD scenes found below {args.root}")
    rows: list[dict[str, object]] = []
    for scene in scenes:
        reference = load_pdd_channels(scene, prefix="GT")
        noisy = load_pdd_channels(scene, prefix="Test")
        mosaic = make_mpfa_mosaic(noisy)
        predictions = {"noisy_full": noisy}
        for method_id, function in (
            ("nearest_mpfa", demosaic_nearest),
            ("bilinear_mpfa", demosaic_bilinear),
        ):
            start = time.perf_counter()
            prediction = function(mosaic)
            latency_ms = (time.perf_counter() - start) * 1000.0
            predictions[method_id] = prediction
            rows.append(
                {
                    "noise_level": scene.noise_level,
                    "scene_id": scene.scene_id,
                    "method_id": method_id,
                    "latency_ms": latency_ms,
                    **polarization_reconstruction_metrics(prediction, reference),
                }
            )
        rows.append(
            {
                "noise_level": scene.noise_level,
                "scene_id": scene.scene_id,
                "method_id": "noisy_full",
                "latency_ms": 0.0,
                **polarization_reconstruction_metrics(noisy, reference),
            }
        )

    aggregate: dict[str, dict[str, object]] = {}
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["noise_level"]), str(row["method_id"]))].append(row)
    metric_names = (
        "intensity_mae",
        "intensity_psnr_db",
        "s0_mae",
        "s1_mae",
        "s2_mae",
        "dolp_mae",
        "aolp_mae_deg",
        "prediction_nonphysical_fraction",
        "latency_ms",
    )
    for (level, method), group_rows in sorted(grouped.items()):
        key = f"{level}/{method}"
        aggregate[key] = {"scenes": len(group_rows)}
        for metric in metric_names:
            values = [float(row[metric]) for row in group_rows if math.isfinite(float(row[metric]))]
            aggregate[key][metric] = float(np.mean(values)) if values else None

    payload = {
        "experiment": "offline-e1-pdd-simple-baselines",
        "date": "2026-11-03",
        "proxy_only": True,
        "claim_boundary": "Public PDD reconstruction benchmark; not a calibration of the future project camera.",
        "root": str(args.root.resolve()),
        "archive_sha256": args.archive_sha256,
        "scene_conditions": len(scenes),
        "records": len(rows),
        "color_channel": "green",
        "mpfa_pattern": [["i90", "i45"], ["i135", "i0"]],
        "aggregate_arithmetic_scene_mean": aggregate,
        "rows": [{key: _json_value(value) for key, value in row.items()} for row in rows],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
    print(f"sha256={hashlib.sha256(encoded.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
