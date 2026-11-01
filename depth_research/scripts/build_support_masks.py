#!/usr/bin/env python3
"""Estimate fixed HAMMER sensor support from cross-frame observations."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


SENSOR_FOLDERS = {
    "d435": "depth_d435",
    "l515": "depth_l515",
    "itof": "depth_tof",
}


def depth_files(root: Path, folder: str) -> tuple[list[Path], list[Path]]:
    selected_layout = sorted(root.glob(f"*/{folder}/*.png"))
    archive_layout = sorted(root.glob(f"*/polarization/{folder}/*.png"))
    if selected_layout and archive_layout:
        raise RuntimeError(f"Mixed selected/archive layouts under {root}")
    candidates = selected_layout or archive_layout

    # Anchor support estimation to frames that have GT.  HAMMER contains one
    # malformed literal ``depth_d435/{06d}.png`` member with no matching frame;
    # silently counting such archive artifacts changes the observation
    # denominator and can contaminate the union mask.
    selected_gt = sorted(root.glob("*/_gt/*.png"))
    archive_gt = sorted(root.glob("*/polarization/_gt/*.png"))
    if selected_gt and archive_gt:
        raise RuntimeError(f"Mixed selected/archive GT layouts under {root}")
    ground_truth = selected_gt or archive_gt
    if not ground_truth:
        return candidates, []

    paired = [path.parent.parent / folder / path.name for path in ground_truth]
    missing = [path for path in paired if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing {len(missing)} {folder} files paired with GT; first: {missing[0]}"
        )
    paired_set = set(paired)
    ignored = [path for path in candidates if path not in paired_set]
    return paired, ignored


def bbox(mask: np.ndarray) -> list[int] | None:
    rows, columns = np.nonzero(mask)
    if not rows.size:
        return None
    return [
        int(columns.min()),
        int(rows.min()),
        int(columns.max()),
        int(rows.max()),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--minimum-observed-fraction",
        type=float,
        default=0.01,
        help="Pixel must contain positive depth in this fraction of frames",
    )
    args = parser.parse_args()
    if not 0 <= args.minimum_observed_fraction <= 1:
        raise SystemExit("--minimum-observed-fraction must be in [0, 1]")

    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "method": "cross_frame_observation_frequency",
        "minimum_observed_fraction": args.minimum_observed_fraction,
        "sensors": {},
    }
    for sensor, folder in SENSOR_FOLDERS.items():
        files, ignored = depth_files(args.root, folder)
        if not files:
            raise SystemExit(f"No {folder} PNGs under {args.root}")
        counts = None
        shape = None
        for index, path in enumerate(files, start=1):
            with Image.open(path) as image:
                depth = np.asarray(image)
            if depth.ndim == 3:
                depth = depth[..., 0]
            if counts is None:
                shape = depth.shape
                counts = np.zeros(shape, dtype=np.uint32)
            elif depth.shape != shape:
                raise ValueError(f"Shape changed from {shape} to {depth.shape}: {path}")
            counts += np.isfinite(depth) & (depth > 0)
            if index % 1000 == 0:
                print(f"sensor={sensor} progress={index}/{len(files)}")

        assert counts is not None
        minimum_count = max(
            1, math.ceil(args.minimum_observed_fraction * len(files))
        )
        support = counts >= minimum_count
        union = counts > 0
        np.save(args.output / f"{sensor}.npy", support, allow_pickle=False)
        Image.fromarray(support.astype(np.uint8) * 255).save(
            args.output / f"{sensor}.png"
        )
        report["sensors"][sensor] = {
            "frames": len(files),
            "ignored_unpaired_depth_files": len(ignored),
            "ignored_unpaired_examples": [str(path) for path in ignored[:10]],
            "shape": list(counts.shape),
            "minimum_observed_count": minimum_count,
            "union_fraction": float(np.mean(union)),
            "support_fraction": float(np.mean(support)),
            "union_bbox_xyxy": bbox(union),
            "support_bbox_xyxy": bbox(support),
            "mean_observed_fraction_within_support": float(
                np.mean(counts[support] / len(files))
            )
            if np.any(support)
            else None,
        }
        print(
            f"sensor={sensor} frames={len(files)} "
            f"support_fraction={np.mean(support):.6f}"
        )

    metadata = args.output / "metadata.json"
    metadata.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(metadata)


if __name__ == "__main__":
    main()
