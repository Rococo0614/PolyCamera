#!/usr/bin/env python3
"""Run ``batch_audit.py`` per trajectory in parallel and merge its CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


CSV_NAMES = (
    "frame_metrics.csv",
    "label_metrics.csv",
    "polar_metrics.csv",
    "dolp_bin_metrics.csv",
    "slice_metrics.csv",
    "incomplete_samples.csv",
    "error_detection_metrics.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trajectories(root: Path) -> list[Path]:
    selected = sorted(path.parent.parent for path in root.glob("*/_gt/*.png"))
    archive = sorted(
        path.parent.parent.parent for path in root.glob("*/polarization/_gt/*.png")
    )
    if selected and archive:
        raise RuntimeError(f"Mixed selected/archive layouts under {root}")
    paths = selected or archive
    return sorted(set(paths), key=lambda path: path.name)


def run_shard(
    trajectory: Path,
    *,
    work_root: Path,
    shards_root: Path,
    logs_root: Path,
    batch_script: Path,
    support_root: Path | None,
    run_fingerprint: str,
) -> tuple[str, str]:
    name = trajectory.name
    destination = shards_root / name
    marker = destination / "complete.json"
    if marker.is_file():
        marker_value = json.loads(marker.read_text(encoding="utf-8"))
        if marker_value.get("run_fingerprint") != run_fingerprint:
            raise RuntimeError(f"Shard configuration changed: {destination}")
        return name, "existing"

    input_root = work_root / name
    input_root.mkdir(parents=True, exist_ok=True)
    link = input_root / name
    if link.is_symlink():
        if link.resolve() != trajectory.resolve():
            raise RuntimeError(f"Unexpected shard symlink target: {link}")
    elif link.exists():
        raise RuntimeError(f"Shard input path is not a symlink: {link}")
    else:
        link.symlink_to(trajectory.resolve(), target_is_directory=True)

    temporary = shards_root / f".{name}.part.{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    command = [
        sys.executable,
        str(batch_script),
        "--root",
        str(input_root),
        "--output",
        str(temporary),
    ]
    if support_root is not None:
        command.extend(("--support-root", str(support_root)))
    log_path = logs_root / f"{name}.log"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(
                command,
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        (temporary / "complete.json").write_text(
            json.dumps(
                {
                    "trajectory": name,
                    "status": "completed",
                    "run_fingerprint": run_fingerprint,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except BaseException:
        temporary.rename(shards_root / f"{name}.failed.{os.getpid()}")
        raise
    return name, "created"


def merge_csvs(shards: list[Path], output: Path) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    for csv_name in CSV_NAMES:
        sources = [shard / csv_name for shard in shards if (shard / csv_name).is_file()]
        if not sources:
            continue
        destination = output / csv_name
        temporary = destination.with_name(destination.name + ".part")
        fields: list[str] | None = None
        count = 0
        with temporary.open("w", newline="", encoding="utf-8") as target:
            writer = None
            for source in sources:
                with source.open(newline="", encoding="utf-8") as file:
                    reader = csv.DictReader(file)
                    source_fields = reader.fieldnames
                    if not source_fields:
                        continue
                    if fields is None:
                        fields = source_fields
                        writer = csv.DictWriter(target, fieldnames=fields)
                        writer.writeheader()
                    elif source_fields != fields:
                        raise ValueError(
                            f"CSV schema changed in {source}: {source_fields} != {fields}"
                        )
                    assert writer is not None
                    for row in reader:
                        writer.writerow(row)
                        count += 1
        temporary.replace(destination)
        row_counts[csv_name] = count
    return row_counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--support-root", type=Path)
    parser.add_argument("--data-manifest", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be positive")

    root = args.root.resolve()
    output = args.output.resolve()
    batch_script = Path(__file__).resolve().with_name("batch_audit.py")
    metrics_module = (
        Path(__file__).resolve().parents[1] / "src" / "poldepth" / "metrics.py"
    )
    trajectory_paths = trajectories(root)
    if not trajectory_paths:
        raise SystemExit(f"No trajectories with GT under {root}")

    work_root = output / "_shard_inputs"
    shards_root = output / "shards"
    logs_root = output / "logs"
    for path in (output, work_root, shards_root, logs_root):
        path.mkdir(parents=True, exist_ok=True)

    support_root = args.support_root.resolve() if args.support_root else None
    support_hashes = (
        {
            name: sha256(support_root / name)
            for name in ("d435.npy", "l515.npy", "itof.npy", "metadata.json")
        }
        if support_root
        else None
    )
    run_config = {
        "root": str(root),
        "support_root": str(support_root) if support_root else None,
        "support_sha256": support_hashes,
        "data_manifest": str(args.data_manifest.resolve())
        if args.data_manifest
        else None,
        "data_manifest_sha256": sha256(args.data_manifest.resolve())
        if args.data_manifest
        else None,
        "batch_audit_sha256": sha256(batch_script),
        "metrics_sha256": sha256(metrics_module),
    }
    serialized_config = json.dumps(run_config, sort_keys=True)
    run_fingerprint = hashlib.sha256(serialized_config.encode("utf-8")).hexdigest()
    config_path = output / "run_config.json"
    if config_path.is_file():
        if json.loads(config_path.read_text(encoding="utf-8")) != run_config:
            raise SystemExit(f"Refusing to mix incompatible audit shards under {output}")
    elif any(shards_root.glob("*/complete.json")):
        raise SystemExit(f"Audit shards exist but run configuration is missing: {output}")
    else:
        config_path.write_text(json.dumps(run_config, indent=2), encoding="utf-8")

    status: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_shard,
                trajectory,
                work_root=work_root,
                shards_root=shards_root,
                logs_root=logs_root,
                batch_script=batch_script,
                support_root=support_root,
                run_fingerprint=run_fingerprint,
            ): trajectory.name
            for trajectory in trajectory_paths
        }
        for index, future in enumerate(as_completed(futures), start=1):
            name, result = future.result()
            status[name] = result
            print(
                f"trajectory={name} status={result} "
                f"progress={index}/{len(futures)}",
                flush=True,
            )

    shard_paths = [shards_root / path.name for path in trajectory_paths]
    incomplete = [path for path in shard_paths if not (path / "complete.json").is_file()]
    if incomplete:
        raise RuntimeError(f"Incomplete audit shards: {incomplete}")
    row_counts = merge_csvs(shard_paths, output)
    report = {
        "status": "completed",
        "root": str(root),
        "support_root": str(support_root) if support_root else None,
        "run_fingerprint": run_fingerprint,
        "workers": args.workers,
        "trajectories": len(trajectory_paths),
        "created_shards": sum(value == "created" for value in status.values()),
        "existing_shards": sum(value == "existing" for value in status.values()),
        "csv_rows": row_counts,
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
