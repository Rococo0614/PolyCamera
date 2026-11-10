#!/usr/bin/env python3
"""Freeze PolaRGB release metadata, processed manifest and a scene-level split."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from polrep.polargb import (
    CAPTURE_PATTERN,
    frozen_scene_split,
    load_metadata,
    metadata_sha256,
    release_files,
    release_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--validation-scenes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261110)
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    summary = release_summary(metadata)
    split = frozen_scene_split(
        summary["train_scene_ids"],
        summary["test_scene_ids"],
        validation_scenes=args.validation_scenes,
        seed=args.seed,
    )

    records = [
        record
        for record in release_files(metadata).values()
        if CAPTURE_PATTERN.match(record.path)
    ]
    records.sort(key=lambda item: item.path)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    if args.manifest.suffix == ".gz":
        with args.manifest.open("wb") as raw_handle:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gzip_handle:
                with io.TextIOWrapper(gzip_handle, encoding="utf-8", newline="") as handle:
                    handle.write("path\tbytes\tsha256\n")
                    for record in records:
                        handle.write(f"{record.path}\t{record.size}\t{record.sha256}\n")
    else:
        with args.manifest.open("w", encoding="utf-8", newline="") as handle:
            handle.write("path\tbytes\tsha256\n")
            for record in records:
                handle.write(f"{record.path}\t{record.size}\t{record.sha256}\n")
    manifest_digest = hashlib.sha256(args.manifest.read_bytes()).hexdigest()

    summary.update(
        {
            "protocol": "polargb-processed-release-v1",
            "metadata_file": str(args.metadata),
            "metadata_sha256": metadata_sha256(args.metadata),
            "manifest_file": str(args.manifest),
            "manifest_sha256": manifest_digest,
            "manifest_records": len(records),
            "paper_claim": {"train_scenes": 56, "test_scenes": 11, "samples": 6500},
            "release_observation": {
                "train_scenes": summary["unique_train_scenes"],
                "test_scenes": summary["unique_test_scenes"],
                "samples": summary["input_captures"],
            },
            "claim_boundary": (
                "The paper/config/release scene counts and names differ. This protocol freezes the "
                "observed Hugging Face release and does not claim to reproduce the paper split."
            ),
        }
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.split.write_text(json.dumps(split, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.summary}")
    print(f"wrote {args.manifest} ({len(records)} records, sha256 {manifest_digest})")
    print(f"wrote {args.split}: {split['counts']}")


if __name__ == "__main__":
    main()
