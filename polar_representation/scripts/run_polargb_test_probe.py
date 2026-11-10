#!/usr/bin/env python3
"""Test-only no-learning PolaRGB probe; all GT-selected values are explicit ceilings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from polrep.baselines import oracle_channel_affine, psnr, representations, ssim
from polrep.polargb import capture_groups, load_metadata, metadata_sha256
from polrep.statistics import summarize_with_interval

ANGLE_METHODS = ("angle_000", "angle_045", "angle_090", "angle_135")


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    groups = [g for g in capture_groups(metadata) if g.subset == "test" and g.side == "input"]
    rows = []
    for index, group in enumerate(groups, start=1):
        channels = {kind: load(args.root / group.files[kind].path) for kind in ("000", "045", "090", "135")}
        rgb = load(args.root / group.files["rgb"].path)
        target = load(args.root / "test" / "gt" / group.scene / "0000_rgb.png")
        views = representations(channels, rgb)
        rgb_affine, _ = oracle_channel_affine(views["rgb"], target)
        min_affine, _ = oracle_channel_affine(views["min4"], target)
        evaluated = {
            **{name: views[name] for name in ("rgb", "mean4", "median4", "min4", "virtual_min", *ANGLE_METHODS)},
            "rgb_gt_affine_ceiling": rgb_affine,
            "min4_gt_affine_ceiling": min_affine,
        }
        row = {"scene": group.scene, "capture_id": group.capture_id}
        for name, image in evaluated.items():
            row[f"{name}_psnr"] = psnr(image, target)
            row[f"{name}_ssim"] = ssim(image, target)
        row["angle_oracle_psnr_ceiling"] = max(float(row[f"{name}_psnr"]) for name in ANGLE_METHODS)
        rows.append(row)
        if index % 40 == 0:
            print(f"scored {index}/{len(groups)}", flush=True)

    scene_labels = [str(row["scene"]) for row in rows]
    methods = sorted(key[:-5] for key in rows[0] if key.endswith("_psnr"))
    summaries = {}
    rgb_values = np.array([float(row["rgb_psnr"]) for row in rows])
    for method in methods:
        psnr_values = np.array([float(row[f"{method}_psnr"]) for row in rows])
        ssim_values = np.array([float(row[f"{method}_ssim"]) for row in rows])
        summaries[method] = {
            "psnr": summarize_with_interval(scene_labels, psnr_values, iterations=args.bootstrap_iterations),
            "ssim": summarize_with_interval(scene_labels, ssim_values, iterations=args.bootstrap_iterations),
        }
        if method != "rgb":
            summaries[method]["psnr_minus_rgb"] = summarize_with_interval(
                scene_labels, psnr_values - rgb_values, iterations=args.bootstrap_iterations
            )
    oracle = np.array([float(row["angle_oracle_psnr_ceiling"]) for row in rows])
    summaries["per_sample_angle_oracle_ceiling"] = {
        "psnr": summarize_with_interval(scene_labels, oracle, iterations=args.bootstrap_iterations),
        "psnr_minus_rgb": summarize_with_interval(
            scene_labels, oracle - rgb_values, iterations=args.bootstrap_iterations
        ),
    }

    clean_rows = []
    gt_groups = [g for g in capture_groups(metadata) if g.subset == "test" and g.side == "gt"]
    for group in gt_groups:
        channels = {kind: load(args.root / group.files[kind].path) for kind in ("000", "045", "090", "135")}
        rgb = load(args.root / group.files["rgb"].path)
        views = representations(channels, rgb)
        clean_rows.append(
            {
                "scene": group.scene,
                **{
                    f"{name}_psnr": psnr(views[name], rgb)
                    for name in ("mean4", "min4", "virtual_min")
                },
                **{
                    f"{name}_ssim": ssim(views[name], rgb)
                    for name in ("mean4", "min4", "virtual_min")
                },
            }
        )
    clean_summary = {
        name: {
            "psnr_scene_macro": float(np.mean([row[f"{name}_psnr"] for row in clean_rows])),
            "psnr_range": [
                float(min(row[f"{name}_psnr"] for row in clean_rows)),
                float(max(row[f"{name}_psnr"] for row in clean_rows)),
            ],
            "ssim_scene_macro": float(np.mean([row[f"{name}_ssim"] for row in clean_rows])),
        }
        for name in ("mean4", "min4", "virtual_min")
    }

    result = {
        "experiment": "polargb-test-only-no-learning-probe-v1",
        "repository_revision": metadata.get("sha"),
        "metadata_sha256": metadata_sha256(args.metadata),
        "samples": len(rows),
        "scenes": len(set(scene_labels)),
        "methods": summaries,
        "clean_preservation": clean_summary,
        "claim_boundary": (
            "Release test only. No fixed direction or color transform is selected for deployment. "
            "Per-image angle and GT-affine entries are diagnostic ceilings and must not be compared "
            "as deployable methods. Final P1 waits for fit-scene train-fitted controls."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
