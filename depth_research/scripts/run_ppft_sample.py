#!/usr/bin/env python3
"""Run the public PPFT checkpoint on one HAMMER frame and verify metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from poldepth.metrics import depth_boundary_mask, depth_metrics, erode_mask
from poldepth.ppft_compat import UPSTREAM_COMMIT, load_ppft_model


def named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected NAME=PATH")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("Expected non-empty NAME=PATH")
    return name, Path(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def read_unchanged(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return image


def polar_triplet(composite_path: Path, downsample: int) -> np.ndarray:
    """Match the author's ``process_hammer.py`` pointwise representation."""

    composite = cv2.imread(str(composite_path), cv2.IMREAD_COLOR)
    if composite is None:
        raise FileNotFoundError(f"Could not read polarization image: {composite_path}")
    height, width = composite.shape[:2]
    if height % 2 or width % 2:
        raise ValueError(f"Odd polarization composite shape: {composite.shape}")
    gray = cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY).astype(np.float64)
    half_h, half_w = height // 2, width // 2
    i0 = gray[:half_h:downsample, :half_w:downsample, None] / 255.0
    i45 = gray[:half_h:downsample, half_w::downsample, None] / 255.0
    i90 = gray[half_h::downsample, :half_w:downsample, None] / 255.0
    i135 = gray[half_h::downsample, half_w::downsample, None] / 255.0

    intensity = 0.5 * (i0 + i45 + i90 + i135)
    q = i0 - i90
    u = i45 - i135
    # Preserve the author's in-place substitutions exactly.  In particular,
    # the substituted intensity is saved as a feature, and substituted Q also
    # participates in the DoLP numerator (not only in the AoLP division).
    q[q == 0] = 1e-10
    intensity[intensity == 0] = 1e-10
    rho = np.clip(np.sqrt(np.square(q) + np.square(u)) / intensity, 0, 1)
    phi = 0.5 * np.arctan(u / q)
    phi[np.cos(2 * phi) * q < 0] += np.pi / 2
    phi = np.mod(phi + np.pi, np.pi)
    # Keep float64 until the final seven-channel tensor conversion, as in the
    # public preprocessor/loader pair.  A compact float32 cache is an explicit
    # storage trade-off and is reported separately by the batch evaluator.
    return np.concatenate((intensity, rho, phi), axis=-1)


def prepare_common_inputs(args) -> tuple[torch.Tensor, torch.Tensor, np.ndarray]:
    rgb_bgr = cv2.imread(str(args.rgb), cv2.IMREAD_COLOR)
    if rgb_bgr is None:
        raise FileNotFoundError(f"Could not read RGB image: {args.rgb}")
    rgb_bgr = rgb_bgr[:: args.downsample, :: args.downsample]
    rgb = rgb_bgr.astype(np.float32) / 255.0
    # Preserve the public loader exactly: cv2 supplies BGR, while the code then
    # applies ImageNet's nominal RGB normalization without channel swapping.
    rgb = (rgb - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )

    if args.polar_cache:
        triplet = np.load(args.polar_cache, allow_pickle=False)
    else:
        triplet = polar_triplet(args.polar, args.downsample)
    viewing_direction = np.load(args.view_directions, mmap_mode="r")
    if viewing_direction.shape[:2] != triplet.shape[:2]:
        viewing_direction = viewing_direction[:: args.downsample, :: args.downsample]
    if viewing_direction.shape[:2] != triplet.shape[:2]:
        raise ValueError(
            f"Viewing directions {viewing_direction.shape} do not align with "
            f"polar features {triplet.shape}"
        )

    intensity = triplet[..., 0:1]
    rho = triplet[..., 1:2]
    phi = triplet[..., 2:3]
    polarization = np.concatenate(
        (
            intensity,
            rho,
            np.cos(2 * phi),
            np.sin(2 * phi),
            np.asarray(viewing_direction),
        ),
        axis=-1,
    ).astype(np.float32)

    if rgb.shape[:2] != polarization.shape[:2]:
        raise ValueError(f"RGB {rgb.shape} and polarization {polarization.shape} differ")
    rgb_tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
    pol_tensor = torch.from_numpy(polarization).permute(2, 0, 1).unsqueeze(0)
    return rgb_tensor, pol_tensor, triplet


def region_metrics(
    prediction_m: np.ndarray,
    ground_truth_m: np.ndarray,
    label: np.ndarray | None,
) -> dict[str, dict[str, float | int]]:
    regions: dict[str, np.ndarray | None] = {"full": None}
    if label is not None:
        regions["reflective_label140_provisional"] = label == 140
        regions["transparent_label160_provisional"] = label == 160
        regions["reflective_label140_interior"] = erode_mask(label == 140, 1)
        regions["transparent_label160_interior"] = erode_mask(label == 160, 1)
    regions["depth_boundary"] = depth_boundary_mask(
        ground_truth_m, threshold=0.020, dilation_radius=1
    )
    return {
        name: depth_metrics(
            prediction_m,
            ground_truth_m,
            mask=mask,
            max_depth=10.0,
            unit_scale=1000.0,
        )
        for name, mask in regions.items()
    }


def author_protocol_metrics(
    prediction_m: np.ndarray,
    ground_truth_m: np.ndarray,
    mask: np.ndarray | None = None,
) -> dict[str, float | int]:
    """Match ``metric/cfmetric.py`` for direct comparison with PPFT tables.

    Unlike the project's coverage-aware metric, the author protocol evaluates
    every prediction (including zero) wherever GT is above 0.1 mm.  Keeping it
    separate avoids silently changing either scientific question.
    """

    prediction = np.asarray(prediction_m, dtype=np.float64).squeeze()
    ground_truth = np.asarray(ground_truth_m, dtype=np.float64).squeeze()
    if prediction.shape != ground_truth.shape:
        raise ValueError(
            f"Shape mismatch: prediction {prediction.shape}, GT {ground_truth.shape}"
        )
    valid = ground_truth > 0.0001
    if mask is not None:
        explicit = np.asarray(mask, dtype=bool).squeeze()
        if explicit.shape != valid.shape:
            raise ValueError(f"Mask shape {explicit.shape} does not match {valid.shape}")
        valid &= explicit
    count = int(valid.sum())
    if not count:
        return {
            "gt_valid_pixels": 0,
            "mae_mm": math.nan,
            "rmse_mm": math.nan,
            "abs_rel": math.nan,
            "delta_1": math.nan,
            "delta_2": math.nan,
            "delta_3": math.nan,
        }
    prediction = prediction[valid]
    ground_truth = ground_truth[valid]
    difference = prediction - ground_truth
    absolute = np.abs(difference)
    ratio = np.maximum(
        ground_truth / (prediction + 1e-8),
        prediction / (ground_truth + 1e-8),
    )
    return {
        "gt_valid_pixels": count,
        "mae_mm": float(np.mean(absolute) * 1000.0),
        "rmse_mm": float(np.sqrt(np.mean(np.square(difference))) * 1000.0),
        "abs_rel": float(np.mean(absolute / (ground_truth + 1e-8))),
        "delta_1": float(np.mean(ratio < 1.25)),
        "delta_2": float(np.mean(ratio < 1.25**2)),
        "delta_3": float(np.mean(ratio < 1.25**3)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--foundation-checkpoint", type=Path)
    parser.add_argument("--rgb", type=Path, required=True)
    polar_group = parser.add_mutually_exclusive_group(required=True)
    polar_group.add_argument("--polar", type=Path, help="Raw 2x2 composite PNG")
    polar_group.add_argument("--polar-cache", type=Path, help="Compact I/rho/phi NPY")
    parser.add_argument("--view-directions", type=Path, required=True)
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--label", type=Path)
    parser.add_argument(
        "--depth",
        action="append",
        type=named_path,
        required=True,
        metavar="NAME=PATH",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--downsample", type=int, default=4)
    parser.add_argument("--amp", choices=("none", "fp16"), default="none")
    args = parser.parse_args()

    if args.downsample < 1:
        raise SystemExit("--downsample must be positive")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but is unavailable")

    torch.manual_seed(43)
    np.random.seed(43)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rgb, polarization, triplet = prepare_common_inputs(args)
    gt_mm = read_unchanged(args.gt)[:: args.downsample, :: args.downsample]
    gt_m = gt_mm.astype(np.float32) / 1000.0
    label = (
        read_unchanged(args.label)[:: args.downsample, :: args.downsample]
        if args.label
        else None
    )

    started = time.perf_counter()
    model, model_args, model_metadata = load_ppft_model(
        args.upstream_root,
        args.checkpoint,
        foundation_checkpoint=args.foundation_checkpoint,
        device=args.device,
    )
    load_seconds = time.perf_counter() - started
    rgb = rgb.to(args.device)
    polarization = polarization.to(args.device)

    report = {
        "status": "completed",
        "upstream_commit": UPSTREAM_COMMIT,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": sha256(args.checkpoint),
        "foundation_checkpoint": (
            str(args.foundation_checkpoint.resolve())
            if args.foundation_checkpoint
            else None
        ),
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "python": platform.python_version(),
        "device": str(args.device),
        "gpu": torch.cuda.get_device_name(args.device)
        if args.device.startswith("cuda")
        else None,
        "amp": args.amp,
        "downsample": args.downsample,
        "quadrant_order": ["0", "45", "90", "135"],
        "rgb_channel_behavior": "opencv_bgr_then_imagenet_constants_author_compatible",
        "metric_protocols": {
            "audit": "coverage-aware; GT and prediction valid; GT/pred <= 10 m",
            "author": "PPFT cfmetric.py; GT > 0.1 mm; zero predictions retained",
        },
        "model_load_seconds": load_seconds,
        "model": model_metadata,
        "inputs": {
            "rgb": str(args.rgb.resolve()),
            "polar": str((args.polar or args.polar_cache).resolve()),
            "polar_source": "compact_cache" if args.polar_cache else "raw_composite",
            "polar_triplet_dtype": str(triplet.dtype),
            "gt": str(args.gt.resolve()),
            "label": str(args.label.resolve()) if args.label else None,
            "shape": list(gt_m.shape),
            "mean_dolp": float(np.mean(triplet[..., 1])),
        },
        "sensors": {},
    }

    amp_enabled = args.amp == "fp16" and args.device.startswith("cuda")
    for sensor, depth_path in args.depth:
        depth_mm = read_unchanged(depth_path)[:: args.downsample, :: args.downsample]
        depth_m = depth_mm.astype(np.float32) / 1000.0
        if depth_m.shape != gt_m.shape:
            raise ValueError(f"Depth {depth_m.shape} and GT {gt_m.shape} differ")
        depth_tensor = (
            torch.from_numpy(depth_m).unsqueeze(0).unsqueeze(0).to(args.device)
        )
        sample = {"rgb": rgb, "dep": depth_tensor, "pol": polarization}

        if args.device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats(args.device)
            torch.cuda.synchronize(args.device)
        begin = time.perf_counter()
        with torch.inference_mode(), torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=amp_enabled,
        ):
            output = model(sample)
        if args.device.startswith("cuda"):
            torch.cuda.synchronize(args.device)
        elapsed = time.perf_counter() - begin
        prediction = output["pred"].float().cpu().numpy()[0, 0]
        if not np.isfinite(prediction).all():
            raise RuntimeError(
                f"Non-finite PPFT prediction for sensor={sensor} with amp={args.amp}; "
                "the author checkpoint is numerically unstable under full-model "
                "FP16 autocast on this stack"
            )

        raw_metrics = region_metrics(depth_m, gt_m, label)
        ppft_metrics = region_metrics(prediction, gt_m, label)
        author_raw_metrics = author_protocol_metrics(depth_m, gt_m)
        author_ppft_metrics = author_protocol_metrics(prediction, gt_m)
        raw_rmse = raw_metrics["full"]["rmse"]
        ppft_rmse = ppft_metrics["full"]["rmse"]
        improvement = (
            100.0 * (float(raw_rmse) - float(ppft_rmse)) / float(raw_rmse)
            if raw_rmse and math.isfinite(float(raw_rmse))
            else math.nan
        )

        prediction_path = args.output_dir / f"{sensor}_prediction_m.npy"
        np.save(prediction_path, prediction.astype(np.float32), allow_pickle=False)
        report["sensors"][sensor] = {
            "depth": str(depth_path.resolve()),
            "prediction": str(prediction_path.resolve()),
            "inference_seconds": elapsed,
            "peak_vram_mib": (
                torch.cuda.max_memory_allocated(args.device) / 2**20
                if args.device.startswith("cuda")
                else None
            ),
            "raw": raw_metrics,
            "ppft": ppft_metrics,
            "author_protocol": {
                "raw": author_raw_metrics,
                "ppft": author_ppft_metrics,
            },
            "full_rmse_improvement_percent": improvement,
            "prediction_min_m": float(np.min(prediction)),
            "prediction_max_m": float(np.max(prediction)),
            "prediction_finite": bool(np.isfinite(prediction).all()),
        }
        del output, depth_tensor

    report_path = args.output_dir / "report.json"
    report_path.write_text(
        json.dumps(json_safe(report), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(report_path)


if __name__ == "__main__":
    main()
