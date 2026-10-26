#!/usr/bin/env python3
"""Extract only the HAMMER non-naked polarization-view training workspace.

The full archive includes four camera-coordinate trees. PPFT and this project
use aligned RGB, polarization, three warped sensor depths, GT and labels under
each non-naked trajectory's ``polarization`` folder. This extractor avoids a
full 171 GiB expansion and is resumable at file granularity.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath


DEFAULT_MODALITIES = (
    "rgb",
    "pol",
    "depth_d435",
    "depth_l515",
    "depth_tof",
    "_gt",
    "_instance",
    "_pose",
    "intrinsics.txt",
)


def selected(info: zipfile.ZipInfo, modalities: set[str]) -> bool:
    if info.is_dir():
        return False
    parts = PurePosixPath(info.filename).parts
    return (
        len(parts) >= 3
        and "naked" not in parts[0]
        and parts[1] == "polarization"
        and parts[2] in modalities
    )


def split_for_trajectory(trajectory: str) -> str:
    scene = int(trajectory.split("_", 1)[0].removeprefix("scene"))
    if 2 <= scene <= 10:
        return "train"
    if scene in (11, 12):
        return "val"
    if scene in (13, 14):
        return "test"
    return "unused"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, help="Local HAMMER ZIP")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--minimum-free-gib", type=float, default=100.0)
    parser.add_argument(
        "--modality",
        action="append",
        choices=DEFAULT_MODALITIES,
        help="Repeat to override the default modality set",
    )
    args = parser.parse_args()

    modalities = set(args.modality or DEFAULT_MODALITIES)
    output = Path(args.output).resolve()
    manifest_path = Path(args.manifest)

    with zipfile.ZipFile(args.archive) as archive:
        members = [info for info in archive.infolist() if selected(info, modalities)]
        total = sum(info.file_size for info in members)
        print(f"selected_files={len(members)} uncompressed_gib={total / 2**30:.3f}")
        if args.dry_run:
            return

        output.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(output).free
        minimum = int(args.minimum_free_gib * 2**30)
        if free - total < minimum:
            raise SystemExit(
                f"Projected free space {(free-total)/2**30:.1f} GiB is below "
                f"the {args.minimum_free_gib:.1f} GiB safety reserve"
            )

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
            writer = csv.writer(manifest_file)
            writer.writerow(
                ["archive_path", "relative_path", "split", "size", "crc32", "status"]
            )
            for index, info in enumerate(members, start=1):
                archive_relative = PurePosixPath(info.filename)
                # Strip the intermediate "polarization" camera-coordinate
                # folder to match PPFT's DATA_ROOT/<trajectory>/<modality>.
                relative = PurePosixPath(
                    archive_relative.parts[0], *archive_relative.parts[2:]
                )
                destination = (output / relative).resolve()
                if output not in destination.parents:
                    raise SystemExit(f"Unsafe archive member: {info.filename}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.stat().st_size == info.file_size:
                    status = "existing"
                else:
                    temporary = destination.with_name(destination.name + ".part")
                    try:
                        with archive.open(info) as source, temporary.open("wb") as target:
                            shutil.copyfileobj(source, target, length=2**20)
                        if temporary.stat().st_size != info.file_size:
                            raise OSError(f"Size mismatch: {info.filename}")
                        temporary.replace(destination)
                    except Exception:
                        temporary.unlink(missing_ok=True)
                        raise
                    status = "extracted"
                split = split_for_trajectory(relative.parts[0])
                writer.writerow(
                    [
                        str(archive_relative),
                        str(relative),
                        split,
                        info.file_size,
                        f"{info.CRC:08x}",
                        status,
                    ]
                )
                if index % 500 == 0:
                    manifest_file.flush()
                    os.fsync(manifest_file.fileno())
                    print(f"progress={index}/{len(members)}")

    print(f"output={output} manifest={manifest_path}")


if __name__ == "__main__":
    main()
