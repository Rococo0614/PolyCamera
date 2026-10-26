#!/usr/bin/env python3
"""Inventory HAMMER storage without extracting the archive."""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remote_zip import HTTPRangeReader  # noqa: E402


def add(stats: dict[str, list[int]], key: str, info: zipfile.ZipInfo) -> None:
    row = stats[key]
    row[0] += 1
    row[1] += info.file_size
    row[2] += info.compress_size


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", help="Local ZIP path")
    source.add_argument("--url", help="Remote HTTP ZIP with Range support")
    parser.add_argument("--output", required=True)
    parser.add_argument("--block-size-mib", type=int, default=16)
    parser.add_argument(
        "--cache-dir",
        default=str(Path(__file__).resolve().parents[1] / ".cache" / "remote_zip"),
    )
    args = parser.parse_args()

    if args.archive:
        archive_source = args.archive
    else:
        archive_source = HTTPRangeReader(
            args.url,
            block_size=args.block_size_mib * 2**20,
            disk_cache=Path(args.cache_dir) if args.cache_dir else None,
        )

    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    with zipfile.ZipFile(archive_source) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            add(groups, "archive/all", info)
            if len(parts) >= 2:
                add(groups, f"camera_group/{parts[1]}", info)
            if len(parts) >= 3 and parts[1] == "polarization":
                add(groups, f"polarization_all/{parts[2]}", info)
                if "naked" not in parts[0]:
                    add(groups, "polarization_non_naked/all", info)
                    add(groups, f"polarization_non_naked/{parts[2]}", info)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "scope",
                "name",
                "files",
                "uncompressed_bytes",
                "compressed_bytes",
                "uncompressed_gib",
                "compressed_gib",
            ]
        )
        for key, values in sorted(groups.items()):
            scope, name = key.split("/", 1)
            count, uncompressed, compressed = values
            writer.writerow(
                [
                    scope,
                    name,
                    count,
                    uncompressed,
                    compressed,
                    f"{uncompressed / 2**30:.3f}",
                    f"{compressed / 2**30:.3f}",
                ]
            )
    print(output)


if __name__ == "__main__":
    main()
