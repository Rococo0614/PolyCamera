#!/usr/bin/env python3
"""Resumable, hash-verified PolaRGB processed-release downloader."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

from polrep.polargb import load_metadata, records_for_prefixes


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--repo-id", default="Mingde/PolaRGB")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Repository prefix to download; repeat. Default: train/ and test/.",
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    revision = str(metadata["sha"])
    prefixes = args.prefix or ["train/", "test/"]
    records = records_for_prefixes(metadata, prefixes)
    if not records:
        raise SystemExit(f"No files match prefixes {prefixes}")
    args.root.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/datasets/{args.repo_id}/resolve/{revision}/"

    def fetch(record):
        destination = args.root / record.path
        if destination.exists() and destination.stat().st_size == record.size:
            if not args.verify_existing or sha256(destination) == record.sha256:
                return "existing", record.size
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + f".part.{os.getpid()}")
        last: Exception | None = None
        for attempt in range(args.retries):
            try:
                request = urllib.request.Request(
                    base + urllib.parse.quote(record.path, safe="/"),
                    headers={"User-Agent": "PolyCamera-polar-representation-audit/0.1"},
                )
                with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
                    digest = hashlib.sha256()
                    size = 0
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        handle.write(block)
                        digest.update(block)
                        size += len(block)
                if size != record.size or digest.hexdigest() != record.sha256:
                    raise OSError(
                        f"integrity mismatch for {record.path}: {size}/{record.size}, {digest.hexdigest()}"
                    )
                partial.replace(destination)
                return "downloaded", size
            except Exception as error:  # CDN 5xx/timeouts are retried with bounded backoff.
                last = error
                partial.unlink(missing_ok=True)
                time.sleep(min(90, 2 ** attempt))
        raise RuntimeError(f"failed {record.path}: {last}")

    counts = {"existing": 0, "downloaded": 0}
    bytes_downloaded = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, (status, size) in enumerate(pool.map(fetch, records), start=1):
            counts[status] += 1
            if status == "downloaded":
                bytes_downloaded += size
            if index % 250 == 0 or index == len(records):
                elapsed = max(time.time() - started, 1e-6)
                print(
                    f"{index}/{len(records)} existing={counts['existing']} downloaded={counts['downloaded']} "
                    f"new={bytes_downloaded/1e9:.2f}GB rate={bytes_downloaded/elapsed/1e6:.2f}MB/s",
                    flush=True,
                )


if __name__ == "__main__":
    main()
