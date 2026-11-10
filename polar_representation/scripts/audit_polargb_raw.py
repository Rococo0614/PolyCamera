#!/usr/bin/env python3
"""Compare PolaRGB raw DoFP mosaics with the processed four-direction release."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import permutations
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


KINDS = ("000", "045", "090", "135")
EXPECTED_OFFSETS = ((0, 0), (0, 1), (1, 0), (1, 1))


def load_processed(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def demosaic_bayer_rg(mosaic: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(np.asarray(mosaic, dtype=np.uint8), cv2.COLOR_BayerRG2RGB)
    return np.asarray(rgb, dtype=np.float64) / 255.0


def correlation(first: np.ndarray, second: np.ndarray) -> float:
    a, b = first.ravel(), second.ravel()
    a, b = a - a.mean(), b - b.mean()
    return float(np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12))


def summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p05": float(np.percentile(array, 5)),
        "p95": float(np.percentile(array, 95)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--processed-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--side", choices=("input", "gt"), default="input")
    parser.add_argument("--mapping-limit", type=int, default=40)
    args = parser.parse_args()

    files = sorted((args.raw_root / "test" / args.side).glob("*/*.[Bb][Mm][Pp]"))
    if not files:
        raise SystemExit("No raw BMP files found")
    metrics: dict[str, list[float]] = defaultdict(list)
    mapping_votes: Counter[tuple[str, ...]] = Counter()
    shape_counts: Counter[str] = Counter()
    for index, raw_path in enumerate(files, start=1):
        scene, capture_id = raw_path.parent.name, raw_path.stem
        raw = np.asarray(Image.open(raw_path).convert("L"), dtype=np.uint8)
        shape_counts[str(tuple(raw.shape))] += 1
        raw_channels = [demosaic_bayer_rg(raw[row::2, column::2]) for row, column in EXPECTED_OFFSETS]
        processed = [
            load_processed(args.processed_root / "test" / args.side / scene / f"{capture_id}_{kind}.png")
            for kind in KINDS
        ]
        direct_mae = [float(np.mean(np.abs(first - second))) for first, second in zip(raw_channels, processed)]
        direct_corr = [correlation(first.mean(axis=-1), second.mean(axis=-1)) for first, second in zip(raw_channels, processed)]
        metrics["processed_reconstruction_mae"].append(float(np.mean(direct_mae)))
        metrics["processed_reconstruction_correlation"].append(float(np.mean(direct_corr)))
        metrics["raw_saturated_share"].append(float(np.mean(raw >= 255)))
        metrics["raw_dark_share"].append(float(np.mean(raw <= 1)))
        if index <= args.mapping_limit:
            scores = {}
            for assignment in permutations(KINDS):
                score = np.mean(
                    [
                        correlation(raw_channels[position].mean(axis=-1), processed[KINDS.index(kind)].mean(axis=-1))
                        for position, kind in enumerate(assignment)
                    ]
                )
                scores[assignment] = float(score)
            mapping_votes[max(scores, key=scores.get)] += 1
        if index % 50 == 0:
            print(f"audited {index}/{len(files)}", flush=True)

    result = {
        "experiment": "polargb-raw-processed-audit-v1",
        "side": args.side,
        "files": len(files),
        "raw_shapes": dict(shape_counts),
        "expected_parity_mapping": dict(zip(("00", "01", "10", "11"), KINDS)),
        "mapping_votes": {"/".join(key): value for key, value in mapping_votes.most_common()},
        "metrics": {name: summary(values) for name, values in metrics.items()},
        "claim_boundary": (
            "OpenCV bilinear Bayer demosaicing is not the release's Malvar2004 pipeline. Correlation and "
            "mapping votes audit channel identity and response trends; MAE is not a reproduction metric."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
