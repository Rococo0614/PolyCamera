#!/usr/bin/env python3
"""Resumable batch-1 PPFT evaluation on an author HAMMER split."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import time
from pathlib import Path, PurePosixPath

import cv2
import numpy as np
import torch

from poldepth.ppft_compat import UPSTREAM_COMMIT, load_ppft_model
from run_ppft_sample import (
    author_protocol_metrics,
    json_safe,
    polar_triplet,
    read_unchanged,
    region_metrics,
    sha256,
)


SENSOR_FOLDERS = {
    "d435": "depth_d435",
    "l515": "depth_l515",
    "itof": "depth_tof",
}
PAPER_TARGETS = {
    "d435": {
        "rmse_mm": 24.78,
        "mae_mm": 10.66,
        "delta_1": 0.995,
        "delta_2": 0.999,
        "delta_3": 1.000,
    },
    "l515": {
        "rmse_mm": 23.84,
        "mae_mm": 10.47,
        "delta_1": 0.995,
        "delta_2": 0.999,
        "delta_3": 1.000,
    },
    "itof": {
        "rmse_mm": 37.27,
        "mae_mm": 21.37,
        "delta_1": 0.987,
        "delta_2": 0.999,
        "delta_3": 1.000,
    },
    "all": {
        "rmse_mm": 28.63,
        "mae_mm": 14.17,
        "delta_1": 0.992,
        "delta_2": 0.999,
        "delta_3": 1.000,
    },
}


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(json_safe(value), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def parse_split(split_path: Path) -> list[PurePosixPath]:
    entries: list[PurePosixPath] = []
    for line_number, line in enumerate(
        split_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        path = PurePosixPath(line)
        parts = path.parts
        if parts and parts[0] == "DATA_ROOT":
            path = PurePosixPath(*parts[1:])
        if len(path.parts) != 3 or path.parts[1] != "rgb":
            raise ValueError(
                f"Unexpected split path on line {line_number}: {line!r}"
            )
        entries.append(path)
    if not entries:
        raise ValueError(f"Split is empty: {split_path}")
    return entries


def prepare_frame(
    data_root: Path,
    relative_rgb: PurePosixPath,
    viewing_direction: np.ndarray,
    *,
    downsample: int,
    polar_cache_root: Path | None,
) -> tuple[torch.Tensor, torch.Tensor, np.ndarray, dict[str, Path]]:
    trajectory, _, filename = relative_rgb.parts
    rgb_path = data_root / trajectory / "rgb" / filename
    rgb_bgr = cv2.imread(str(rgb_path), cv2.IMREAD_COLOR)
    if rgb_bgr is None:
        raise FileNotFoundError(f"Could not read RGB image: {rgb_path}")
    rgb = rgb_bgr[::downsample, ::downsample].astype(np.float32) / 255.0
    rgb = (rgb - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )

    if polar_cache_root is not None:
        polar_path = polar_cache_root / trajectory / "pol_processed" / (
            Path(filename).stem + ".npy"
        )
        triplet = np.load(polar_path, allow_pickle=False)
    else:
        polar_path = data_root / trajectory / "pol" / filename
        triplet = polar_triplet(polar_path, downsample)
    if triplet.shape[:2] != viewing_direction.shape[:2]:
        raise ValueError(
            f"Polar cache {polar_path} has shape {triplet.shape}; expected "
            f"{viewing_direction.shape[:2]} spatially"
        )
    polarization = np.concatenate(
        (
            triplet[..., 0:1],
            triplet[..., 1:2],
            np.cos(2 * triplet[..., 2:3]),
            np.sin(2 * triplet[..., 2:3]),
            viewing_direction,
        ),
        axis=-1,
    ).astype(np.float32)
    if rgb.shape[:2] != polarization.shape[:2]:
        raise ValueError(
            f"RGB {rgb.shape} and polarization {polarization.shape} differ"
        )
    paths = {
        "rgb": rgb_path,
        "polar": polar_path,
        "gt": data_root / trajectory / "_gt" / filename,
        "label": data_root / trajectory / "_instance" / filename,
    }
    return (
        torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0),
        torch.from_numpy(polarization).permute(2, 0, 1).unsqueeze(0),
        triplet,
        paths,
    )


def mean_metrics(records: list[dict], sensor: str | None) -> dict[str, float]:
    selected = records if sensor is None else [r for r in records if r["sensor"] == sensor]
    keys = ("mae_mm", "rmse_mm", "abs_rel", "delta_1", "delta_2", "delta_3")
    result: dict[str, float] = {}
    for key in keys:
        values = [float(r["author_protocol"]["ppft"][key]) for r in selected]
        finite = [value for value in values if math.isfinite(value)]
        result[key] = float(np.mean(finite)) if finite else math.nan
    result["records"] = len(selected)
    result["mean_inference_seconds"] = (
        float(np.mean([r["inference_seconds"] for r in selected]))
        if selected
        else math.nan
    )
    result["peak_vram_mib"] = (
        float(max(r["peak_vram_mib"] for r in selected)) if selected else math.nan
    )
    return result


def paper_comparison(measured: dict[str, float], target: dict[str, float]) -> dict:
    return {
        key: {
            "measured": measured[key],
            "paper": paper_value,
            "absolute_difference": measured[key] - paper_value,
        }
        for key, paper_value in target.items()
    }


def write_flat_csv(path: Path, records: list[dict]) -> None:
    fields = [
        "index",
        "trajectory",
        "frame",
        "sensor",
        "inference_seconds",
        "peak_vram_mib",
        "raw_rmse_mm",
        "raw_mae_mm",
        "ppft_rmse_mm",
        "ppft_mae_mm",
        "ppft_abs_rel",
        "ppft_delta_1",
        "ppft_delta_2",
        "ppft_delta_3",
        "audit_coverage",
        "audit_rmse_mm",
        "audit_mae_mm",
    ]
    temporary = path.with_name(path.name + ".part")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for record in records:
            raw = record["author_protocol"]["raw"]
            ppft = record["author_protocol"]["ppft"]
            audit = record["audit"]["full"]
            writer.writerow(
                {
                    "index": record["index"],
                    "trajectory": record["trajectory"],
                    "frame": record["frame"],
                    "sensor": record["sensor"],
                    "inference_seconds": record["inference_seconds"],
                    "peak_vram_mib": record["peak_vram_mib"],
                    "raw_rmse_mm": raw["rmse_mm"],
                    "raw_mae_mm": raw["mae_mm"],
                    "ppft_rmse_mm": ppft["rmse_mm"],
                    "ppft_mae_mm": ppft["mae_mm"],
                    "ppft_abs_rel": ppft["abs_rel"],
                    "ppft_delta_1": ppft["delta_1"],
                    "ppft_delta_2": ppft["delta_2"],
                    "ppft_delta_3": ppft["delta_3"],
                    "audit_coverage": audit["coverage"],
                    "audit_rmse_mm": audit["rmse"],
                    "audit_mae_mm": audit["mae"],
                }
            )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--foundation-checkpoint", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--data-manifest",
        type=Path,
        help="Optional integrity manifest recorded and hashed in the run configuration",
    )
    parser.add_argument("--split-file", type=Path, required=True)
    parser.add_argument("--view-directions", type=Path, required=True)
    parser.add_argument("--polar-cache-root", type=Path)
    parser.add_argument(
        "--polar-cache-manifest",
        type=Path,
        help="Optional cache integrity manifest recorded and hashed in the run configuration",
    )
    parser.add_argument(
        "--sensor",
        action="append",
        choices=tuple(SENSOR_FOLDERS),
        help="Repeat to select sensors; defaults to all three",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--downsample", type=int, default=4)
    parser.add_argument("--amp", choices=("none", "fp16"), default="none")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--save-predictions", action="store_true")
    parser.add_argument(
        "--resume", action=argparse.BooleanOptionalAction, default=True
    )
    args = parser.parse_args()

    if args.downsample < 1:
        raise SystemExit("--downsample must be positive")
    if args.polar_cache_manifest and not args.polar_cache_root:
        raise SystemExit("--polar-cache-manifest requires --polar-cache-root")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but is unavailable")
    sensors = args.sensor or list(SENSOR_FOLDERS)
    if len(set(sensors)) != len(sensors):
        raise SystemExit("Each --sensor may be selected only once")

    entries = parse_split(args.split_file)
    if args.limit is not None:
        entries = entries[: args.limit]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = args.output_dir / "records"
    predictions_dir = args.output_dir / "predictions"
    if records_dir.exists() and not args.resume and any(records_dir.glob("*.json")):
        raise SystemExit(
            f"Records already exist under {records_dir}; use --resume or a new output dir"
        )
    records_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_digest = sha256(args.checkpoint)
    split_digest = sha256(args.split_file)
    viewing_direction_digest = sha256(args.view_directions)
    runner_path = Path(__file__).resolve()
    sample_runner_path = runner_path.with_name("run_ppft_sample.py")
    compatibility_path = runner_path.parents[1] / "src" / "poldepth" / "ppft_compat.py"
    metrics_path = runner_path.parents[1] / "src" / "poldepth" / "metrics.py"
    run_config = {
        "evaluation_version": 3,
        "runner_sha256": sha256(runner_path),
        "sample_runner_sha256": sha256(sample_runner_path),
        "compatibility_sha256": sha256(compatibility_path),
        "metrics_sha256": sha256(metrics_path),
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_root": str(args.upstream_root.resolve()),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": checkpoint_digest,
        "foundation_checkpoint": str(args.foundation_checkpoint.resolve())
        if args.foundation_checkpoint
        else None,
        "data_root": str(args.data_root.resolve()),
        "data_manifest": str(args.data_manifest.resolve())
        if args.data_manifest
        else None,
        "data_manifest_sha256": sha256(args.data_manifest)
        if args.data_manifest
        else None,
        "polar_cache_root": str(args.polar_cache_root.resolve())
        if args.polar_cache_root
        else None,
        "polar_cache_manifest": str(args.polar_cache_manifest.resolve())
        if args.polar_cache_manifest
        else None,
        "polar_cache_manifest_sha256": sha256(args.polar_cache_manifest)
        if args.polar_cache_manifest
        else None,
        "split_file": str(args.split_file.resolve()),
        "split_sha256": split_digest,
        "view_directions": str(args.view_directions.resolve()),
        "view_directions_sha256": viewing_direction_digest,
        "frames": len(entries),
        "sensors": sensors,
        "downsample": args.downsample,
        "amp": args.amp,
        "device": args.device,
        "save_predictions": args.save_predictions,
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
    }
    config_path = args.output_dir / "run_config.json"
    if config_path.is_file():
        previous_config = json.loads(config_path.read_text(encoding="utf-8"))
        if previous_config != run_config:
            differing = sorted(
                key
                for key in set(previous_config) | set(run_config)
                if previous_config.get(key) != run_config.get(key)
            )
            raise SystemExit(
                "Refusing to mix incompatible resumed records; differing run "
                f"configuration keys: {', '.join(differing)}"
            )
    else:
        if any(records_dir.glob("*.json")):
            raise SystemExit(f"Records exist but run configuration is missing: {config_path}")
        atomic_json(config_path, run_config)

    viewing_direction = np.load(args.view_directions, mmap_mode="r")
    if viewing_direction.shape[:2] == (832, 1088):
        viewing_direction = viewing_direction[:: args.downsample, :: args.downsample]
    if viewing_direction.ndim != 3 or viewing_direction.shape[2] != 3:
        raise ValueError(
            f"Unexpected viewing direction shape: {viewing_direction.shape}"
        )
    viewing_direction = np.asarray(viewing_direction, dtype=np.float32)

    torch.manual_seed(43)
    np.random.seed(43)
    load_started = time.perf_counter()
    model, _, model_metadata = load_ppft_model(
        args.upstream_root,
        args.checkpoint,
        foundation_checkpoint=args.foundation_checkpoint,
        device=args.device,
    )
    model_load_seconds = time.perf_counter() - load_started
    amp_enabled = args.amp == "fp16" and args.device.startswith("cuda")
    device_type = args.device.split(":", 1)[0]

    expected_records = len(entries) * len(sensors)
    completed = sum(
        (records_dir / f"{index:06d}_{sensor}.json").is_file()
        for index in range(len(entries))
        for sensor in sensors
    )
    run_started = time.perf_counter()
    for index, relative_rgb in enumerate(entries):
        trajectory, _, filename = relative_rgb.parts
        stem = Path(filename).stem
        pending = [
            sensor
            for sensor in sensors
            if not (records_dir / f"{index:06d}_{sensor}.json").is_file()
        ]
        if not pending:
            continue

        rgb, polarization, triplet, paths = prepare_frame(
            args.data_root,
            relative_rgb,
            viewing_direction,
            downsample=args.downsample,
            polar_cache_root=args.polar_cache_root,
        )
        gt_m = (
            read_unchanged(paths["gt"])[:: args.downsample, :: args.downsample]
            .astype(np.float32)
            / 1000.0
        )
        label = (
            read_unchanged(paths["label"])[:: args.downsample, :: args.downsample]
            if paths["label"].is_file()
            else None
        )
        rgb = rgb.to(args.device)
        polarization = polarization.to(args.device)

        for sensor in pending:
            depth_path = args.data_root / trajectory / SENSOR_FOLDERS[sensor] / filename
            depth_m = (
                read_unchanged(depth_path)[:: args.downsample, :: args.downsample]
                .astype(np.float32)
                / 1000.0
            )
            depth_tensor = (
                torch.from_numpy(depth_m).unsqueeze(0).unsqueeze(0).to(args.device)
            )
            if args.device.startswith("cuda"):
                torch.cuda.reset_peak_memory_stats(args.device)
                torch.cuda.synchronize(args.device)
            inference_started = time.perf_counter()
            with torch.inference_mode(), torch.autocast(
                device_type=device_type,
                dtype=torch.float16,
                enabled=amp_enabled,
            ):
                output = model(
                    {"rgb": rgb, "dep": depth_tensor, "pol": polarization}
                )
            if args.device.startswith("cuda"):
                torch.cuda.synchronize(args.device)
            inference_seconds = time.perf_counter() - inference_started
            prediction = output["pred"].float().cpu().numpy()[0, 0]
            if not np.isfinite(prediction).all():
                raise RuntimeError(
                    f"Non-finite prediction at index={index} sensor={sensor}"
                )
            peak_vram = (
                torch.cuda.max_memory_allocated(args.device) / 2**20
                if args.device.startswith("cuda")
                else 0.0
            )

            record = {
                "index": index,
                "trajectory": trajectory,
                "frame": stem,
                "sensor": sensor,
                "inference_seconds": inference_seconds,
                "peak_vram_mib": peak_vram,
                "mean_dolp": float(np.mean(triplet[..., 1])),
                "prediction_finite": bool(np.isfinite(prediction).all()),
                "author_protocol": {
                    "raw": author_protocol_metrics(depth_m, gt_m),
                    "ppft": author_protocol_metrics(prediction, gt_m),
                },
                "audit": region_metrics(prediction, gt_m, label),
            }
            if args.save_predictions:
                prediction_path = predictions_dir / trajectory / sensor / f"{stem}.npy"
                prediction_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = prediction_path.with_name(prediction_path.name + ".part")
                with temporary.open("wb") as file:
                    np.save(file, prediction.astype(np.float32), allow_pickle=False)
                temporary.replace(prediction_path)
                record["prediction"] = str(prediction_path.resolve())
            atomic_json(records_dir / f"{index:06d}_{sensor}.json", record)
            completed += 1
            del output, depth_tensor

        if (index + 1) % 25 == 0 or completed == expected_records:
            elapsed = time.perf_counter() - run_started
            print(
                f"frames={index + 1}/{len(entries)} records={completed}/"
                f"{expected_records} elapsed_s={elapsed:.1f}"
            )

    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(records_dir.glob("*.json"))
    ]
    expected_keys = {
        (index, sensor) for index in range(len(entries)) for sensor in sensors
    }
    actual_keys = {(record["index"], record["sensor"]) for record in records}
    missing = sorted(expected_keys - actual_keys)
    if missing:
        raise RuntimeError(f"Evaluation ended with {len(missing)} missing records")
    records = [
        record
        for record in records
        if (record["index"], record["sensor"]) in expected_keys
    ]
    records.sort(key=lambda record: (record["index"], sensors.index(record["sensor"])))

    aggregate = {sensor: mean_metrics(records, sensor) for sensor in sensors}
    aggregate["all"] = mean_metrics(records, None)
    eligible = (
        len(entries) == 946
        and set(sensors) == set(SENSOR_FOLDERS)
        and args.split_file.name == "hammer_test.txt"
    )
    comparison = {
        group: paper_comparison(aggregate[group], PAPER_TARGETS[group])
        for group in (*sensors, "all")
        if group in PAPER_TARGETS
    }
    report = {
        "status": "completed",
        "upstream_commit": UPSTREAM_COMMIT,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": checkpoint_digest,
        "split_file": str(args.split_file.resolve()),
        "split_sha256": split_digest,
        "data_manifest": run_config["data_manifest"],
        "data_manifest_sha256": run_config["data_manifest_sha256"],
        "polar_cache_manifest": run_config["polar_cache_manifest"],
        "polar_cache_manifest_sha256": run_config[
            "polar_cache_manifest_sha256"
        ],
        "view_directions_sha256": viewing_direction_digest,
        "frames": len(entries),
        "sensors": sensors,
        "records": len(records),
        "batch_size": 1,
        "amp": args.amp,
        "downsample": args.downsample,
        "model_load_seconds": model_load_seconds,
        "wall_seconds_this_invocation": time.perf_counter() - run_started,
        "model": model_metadata,
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "python": platform.python_version(),
        "device": args.device,
        "gpu": torch.cuda.get_device_name(args.device)
        if args.device.startswith("cuda")
        else None,
        "rgb_channel_behavior": "opencv_bgr_then_imagenet_constants_author_compatible",
        "quadrant_order": ["0", "45", "90", "135"],
        "polar_input": {
            "source": "compact_cache" if args.polar_cache_root else "raw_composite",
            "cache_root": str(args.polar_cache_root.resolve())
            if args.polar_cache_root
            else None,
            "note": (
                "Compact float32 I/rho/phi is the storage-efficient path and may "
                "differ at float-roundoff scale from author float64 preprocessing."
                if args.polar_cache_root
                else "Raw path keeps author float64 preprocessing until final float32 tensor."
            ),
        },
        "aggregation": "arithmetic mean of per-frame author-protocol metrics",
        "paper_comparison_eligible": eligible,
        "aggregate": aggregate,
        "paper_targets": PAPER_TARGETS,
        "comparison": comparison,
    }
    write_flat_csv(args.output_dir / "per_frame_metrics.csv", records)
    atomic_json(args.output_dir / "report.json", report)
    print(args.output_dir / "report.json")


if __name__ == "__main__":
    main()
