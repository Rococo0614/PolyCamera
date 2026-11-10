#!/usr/bin/env python3
"""Audit PolaRGB radiometry and four-analyzer consistency without training."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from polrep.physics import solve_stokes, srgb_decode
from polrep.polargb import capture_groups, load_metadata


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def pair_residual(channels: list[np.ndarray]) -> float:
    first = channels[0] + channels[2]
    second = channels[1] + channels[3]
    return float(np.mean(np.abs(first - second)) / max(float(np.mean((first + second) / 2)), 1e-8))


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p05": float(np.percentile(array, 5)),
        "p95": float(np.percentile(array, 95)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--subset", action="append", default=None)
    parser.add_argument("--side", choices=("input", "gt"), default="input")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    subsets = args.subset or ["test"]
    groups = [
        group
        for group in capture_groups(load_metadata(args.metadata))
        if group.subset in subsets and group.side == args.side
    ]
    if not groups:
        raise SystemExit("No matching groups")
    metrics: dict[str, list[float]] = defaultdict(list)
    per_scene: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for index, group in enumerate(groups, start=1):
        paths = {kind: args.root / record.path for kind, record in group.files.items()}
        if not all(path.exists() for path in paths.values()):
            missing = [str(path) for path in paths.values() if not path.exists()]
            raise FileNotFoundError(f"{group.key}: missing {missing[:2]}")
        channels = [load(paths[kind]) for kind in ("000", "045", "090", "135")]
        rgb = load(paths["rgb"])
        stack = np.stack(channels)
        measurements = np.moveaxis(stack, 0, -1)
        stokes = solve_stokes(measurements)
        s0, s1, s2 = np.moveaxis(stokes, -1, 0)
        dolp = np.hypot(s1, s2) / np.maximum(s0, 1e-8)
        valid = s0 > 0.1
        values = {
            "pair_residual_stored": pair_residual(channels),
            "pair_residual_srgb_decoded": pair_residual([srgb_decode(item) for item in channels]),
            "rgb_mean4_mae": float(np.mean(np.abs(rgb - stack.mean(axis=0)))),
            "dolp_median_valid": float(np.median(dolp[valid])),
            "dolp_gt1_share": float(np.mean(dolp[valid] > 1.0)),
            "saturated_share": float(np.mean(stack >= 1.0)),
            "dark_share": float(np.mean(stack <= 1.0 / 255.0)),
            "reprojection_rmse": float(
                np.sqrt(np.mean((measurements - stokes @ np.array(
                    [[0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.5, -0.5, 0.0], [0.5, 0.0, -0.5]]
                ).T) ** 2))
            ),
        }
        for name, value in values.items():
            metrics[name].append(value)
            per_scene[group.scene][name].append(value)
        if index % 100 == 0:
            print(f"audited {index}/{len(groups)}", flush=True)

    result = {
        "experiment": "polargb-processed-physics-audit",
        "subsets": subsets,
        "side": args.side,
        "groups": len(groups),
        "scenes": len(per_scene),
        "metrics_sample": {name: quantiles(values) for name, values in metrics.items()},
        "metrics_scene_macro": {
            name: quantiles([float(np.mean(scene[name])) for scene in per_scene.values()])
            for name in metrics
        },
        "per_scene_mean": {
            scene: {name: float(np.mean(values)) for name, values in scene_metrics.items()}
            for scene, scene_metrics in sorted(per_scene.items())
        },
        "domain_decision": {
            "primary": "stored" if np.mean(metrics["pair_residual_stored"]) < np.mean(metrics["pair_residual_srgb_decoded"]) else "srgb_decoded",
            "criterion": "lower orthogonal-pair relative residual; diagnostic evidence, not a RAW response calibration",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
