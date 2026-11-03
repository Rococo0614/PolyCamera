#!/usr/bin/env python3
"""Freeze the document-level SHDocs split used by Offline Gate P."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from polread.splits import grouped_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261102)
    args = parser.parse_args()

    documents = sorted(path.stem for path in args.annotations_root.glob("*.json"))
    assignments = grouped_split(documents, seed=args.seed)
    payload = {
        "split_version": "shdocs-document-v1",
        "proxy_only": True,
        "group_key": "document_id",
        "seed": args.seed,
        "train_fraction_requested": 0.7,
        "val_fraction_requested": 0.15,
        "documents": len(documents),
        "counts": dict(sorted(Counter(assignments.values()).items())),
        "assignments": dict(sorted(assignments.items())),
    }
    canonical = json.dumps(payload, sort_keys=True)
    payload["assignment_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "assignments"}, indent=2))


if __name__ == "__main__":
    main()
