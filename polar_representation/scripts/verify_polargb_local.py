#!/usr/bin/env python3
"""Hash and decode-verify a local PolaRGB release against frozen HF metadata."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from PIL import Image

from polrep.polargb import load_metadata, metadata_sha256, records_for_prefixes


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", action="append", default=[])
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    prefixes = args.prefix or ["train/", "test/"]
    records = records_for_prefixes(metadata, prefixes)

    def check(record):
        path = args.root / record.path
        if not path.exists():
            return "missing", record.path
        if path.stat().st_size != record.size:
            return "size_mismatch", record.path
        if digest(path) != record.sha256:
            return "hash_mismatch", record.path
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception:
            return "decode_error", record.path
        return "ok", record.path

    counts = {name: 0 for name in ("ok", "missing", "size_mismatch", "hash_mismatch", "decode_error")}
    examples = {name: [] for name in counts if name != "ok"}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, (status, path) in enumerate(pool.map(check, records), start=1):
            counts[status] += 1
            if status != "ok" and len(examples[status]) < 20:
                examples[status].append(path)
            if index % 1000 == 0:
                print(f"verified {index}/{len(records)}", flush=True)
    result = {
        "experiment": "polargb-local-integrity-v1",
        "repository_revision": metadata.get("sha"),
        "metadata_sha256": metadata_sha256(args.metadata),
        "prefixes": prefixes,
        "records": len(records),
        "counts": counts,
        "examples": examples,
        "pass": counts["ok"] == len(records),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}; pass={result['pass']}")


if __name__ == "__main__":
    main()
