#!/usr/bin/env python3
"""Discover SHDocs captures without modifying source data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polread.shdocs import discover_captures, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    captures = discover_captures(args.root)
    write_manifest(captures, args.output)
    summary = {
        "root": str(args.root.resolve()),
        "captures": len(captures),
        "documents": len({capture.document_id for capture in captures}),
        "conditions": sorted({capture.condition_id for capture in captures}),
        "with_s0_norm": sum(bool(capture.s0_norm_path) for capture in captures),
        "with_deglared": sum(bool(capture.deglared_path) for capture in captures),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
