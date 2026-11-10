#!/usr/bin/env python3
"""PolaRGB no-learning baselines with scene-aware statistics and train-fitted color controls."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from polrep.baselines import SceneEqualAffineAccumulator, psnr, representations, ssim
from polrep.polargb import CaptureGroup, capture_groups, load_metadata
from polrep.statistics import summarize_with_interval

ANGLE_METHODS = ("angle_000", "angle_045", "angle_090", "angle_135")


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def target_path(root: Path, group: CaptureGroup) -> Path:
    return root / group.subset / "gt" / group.scene / "0000_rgb.png"


def load_representations(root: Path, group: CaptureGroup) -> tuple[dict[str, np.ndarray], np.ndarray]:
    channels = {kind: load(root / group.files[kind].path) for kind in ("000", "045", "090", "135")}
    rgb = load(root / group.files["rgb"].path)
    return representations(channels, rgb), load(target_path(root, group))


def scene_ids(split: dict, name: str) -> set[str]:
    return set(str(item) for item in split[name])


def select_groups(all_groups: list[CaptureGroup], split: dict, name: str) -> list[CaptureGroup]:
    scenes = scene_ids(split, name)
    if name == "test":
        return [g for g in all_groups if g.side == "input" and g.subset == "test" and g.scene in scenes]
    return [g for g in all_groups if g.side == "input" and g.subset.startswith("train/") and g.scene in scenes]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument("--affine-stride", type=int, default=16)
    args = parser.parse_args()

    split = json.loads(args.split.read_text(encoding="utf-8"))
    all_groups = capture_groups(load_metadata(args.metadata))
    fit_groups = select_groups(all_groups, split, "fit")
    test_groups = select_groups(all_groups, split, "test")
    if not fit_groups or not test_groups:
        raise SystemExit("Frozen fit/test groups are empty")

    affine_accumulators = {
        name: SceneEqualAffineAccumulator() for name in ("rgb", "min4", "virtual_min")
    }
    angle_by_scene: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for index, group in enumerate(fit_groups, start=1):
        views, target = load_representations(args.root, group)
        for name, accumulator in affine_accumulators.items():
            accumulator.add(group.scene, views[name], target, stride=args.affine_stride)
        for name in ANGLE_METHODS:
            angle_by_scene[group.scene][name].append(psnr(views[name], target))
        if index % 250 == 0:
            print(f"fit pass {index}/{len(fit_groups)}", flush=True)
    affines = {name: accumulator.fit() for name, accumulator in affine_accumulators.items()}
    angle_macro = {
        name: float(np.mean([np.mean(angle_by_scene[scene][name]) for scene in sorted(angle_by_scene)]))
        for name in ANGLE_METHODS
    }
    fixed_angle = max(ANGLE_METHODS, key=angle_macro.get)

    rows: list[dict[str, object]] = []
    for index, group in enumerate(test_groups, start=1):
        views, target = load_representations(args.root, group)
        evaluated = {
            **{name: views[name] for name in ("rgb", "mean4", "median4", "min4", "virtual_min", *ANGLE_METHODS)},
            "train_best_fixed_angle": views[fixed_angle],
            "rgb_train_affine": affines["rgb"].apply(views["rgb"]),
            "min4_train_affine": affines["min4"].apply(views["min4"]),
            "virtual_min_train_affine": affines["virtual_min"].apply(views["virtual_min"]),
        }
        row: dict[str, object] = {"scene": group.scene, "capture_id": group.capture_id}
        for name, image in evaluated.items():
            row[f"{name}_psnr"] = psnr(image, target)
            row[f"{name}_ssim"] = ssim(image, target)
        rows.append(row)
        if index % 40 == 0:
            print(f"test pass {index}/{len(test_groups)}", flush=True)

    groups = [str(row["scene"]) for row in rows]
    methods = sorted(key[:-5] for key in rows[0] if key.endswith("_psnr"))
    summaries: dict[str, object] = {}
    for method in methods:
        psnr_values = np.array([float(row[f"{method}_psnr"]) for row in rows])
        ssim_values = np.array([float(row[f"{method}_ssim"]) for row in rows])
        summaries[method] = {
            "psnr": summarize_with_interval(groups, psnr_values, iterations=args.bootstrap_iterations),
            "ssim": summarize_with_interval(groups, ssim_values, iterations=args.bootstrap_iterations),
        }
        if method != "rgb":
            summaries[method]["psnr_minus_rgb"] = summarize_with_interval(
                groups,
                psnr_values - np.array([float(row["rgb_psnr"]) for row in rows]),
                iterations=args.bootstrap_iterations,
            )

    clean_rows = []
    test_scenes = sorted(scene_ids(split, "test"))
    by_key = {(g.subset, g.side, g.scene): g for g in all_groups if g.capture_id == "0000"}
    for scene in test_scenes:
        gt_group = by_key[("test", "gt", scene)]
        views, target = load_representations(args.root, gt_group)
        clean_rows.append(
            {
                "scene": scene,
                "mean4_psnr": psnr(views["mean4"], target),
                "min4_psnr": psnr(views["min4"], target),
                "virtual_min_psnr": psnr(views["virtual_min"], target),
            }
        )

    result = {
        "experiment": "polargb-no-learning-baselines-v1",
        "fit_groups": len(fit_groups),
        "test_groups": len(test_groups),
        "fixed_angle_selection_scene_macro_psnr": angle_macro,
        "train_best_fixed_angle": fixed_angle,
        "affine_fit": {
            name: {"gain": list(model.gain), "offset": list(model.offset)}
            for name, model in affines.items()
        },
        "methods": summaries,
        "clean_preservation": clean_rows,
        "claim_boundary": (
            "All fixed choices and affine parameters use frozen fit scenes only. Test scenes are used once "
            "for reporting. LPIPS and learned methods are not part of this no-training result."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}; train-best angle={fixed_angle}")


if __name__ == "__main__":
    main()
