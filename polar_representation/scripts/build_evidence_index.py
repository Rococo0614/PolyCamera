#!/usr/bin/env python3
"""Hash P0-P3 source, evidence and external frozen metadata artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository.resolve()
    project = root / "polar_representation"
    sources = sorted(
        [*project.glob("src/**/*.py"), *project.glob("scripts/*.py"), *project.glob("tests/*.py")]
    )
    evidence = sorted(
        path
        for path in (project / "evidence").rglob("*")
        if path.is_file() and path.resolve() != args.output.resolve()
    )
    result = {
        "experiment": "polar-representation-p0-p3-evidence-index-v1",
        "source_sha256": {str(path.relative_to(root)): sha256(path) for path in sources},
        "evidence_sha256": {str(path.relative_to(root)): sha256(path) for path in evidence},
        "external_artifacts": {
            str(args.metadata): {"bytes": args.metadata.stat().st_size, "sha256": sha256(args.metadata)},
            str(args.manifest): {"bytes": args.manifest.stat().st_size, "sha256": sha256(args.manifest)},
        },
        "claim_boundary": (
            "Large images and run records remain outside Git. This index pins the exact release metadata, "
            "processed manifest, source and compact evidence used by P0-P3."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(sources)} sources, {len(evidence)} evidence files)")


if __name__ == "__main__":
    main()
