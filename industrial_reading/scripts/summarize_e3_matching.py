#!/usr/bin/env python3
"""E3: does the four-channel headroom survive intensity matching?

Compares, on the frozen SHDocs test split (highlight conditions a-o), the
fixed/oracle/headroom of

* ``raw4``  the four raw SDK channels i0/i45/i90/i135 (the earlier E2),
* ``hm4``   the same channels after pooled-histogram matching within each ROI,
* ``ms4``   the same channels after per-ROI mean/std matching.

Matching removes global brightness/contrast differences between the channels
while keeping their spatial structure. If the oracle gap were only an exposure
or contrast artefact it should shrink sharply. If it survives, global
brightness/contrast differences are not the explanation; that alone does not
separate spatially different glare structure from OCR instability under small
perturbations (see ``summarize_noise_null.py`` for that). Paired
document-cluster intervals are reported for headroom differences and for the
matched-versus-raw fixed baseline. All fixed methods are chosen on train only.

Mean/std matching is an affine intensity map. ``same_channel_outcome_agreement``
reports empirically how often the read of a channel changes under each matching;
when that is small the control is weak, so mean/std matching is a sanity check
and histogram matching (non-affine) is the more demanding control.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import numpy as np

from polread.analysis import (
    contrast_with_ci,
    exact_delta_with_ci,
    exact_rate_by_view,
    fixed_gain_sample,
    outcome_agreement,
    summarize_gain,
)
from polread.headroom import build_success_matrix
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization

RAW = ("i0", "i45", "i90", "i135")
HM = tuple(f"hm_{key}" for key in RAW)
MS = tuple(f"ms_{key}" for key in RAW)
CONDITIONS = set("abcdefghijklmno")


def expand(patterns: list[str]) -> list[str]:
    paths = sorted({path for pattern in patterns for path in glob.glob(pattern)})
    if not paths:
        raise SystemExit(f"No files match {patterns}")
    return paths


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", nargs="+", required=True, help="glob(s) of raw i0..i135 JSONL")
    parser.add_argument("--matched", nargs="+", required=True, help="glob(s) of hm_*/ms_* JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend-label", required=True)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument(
        "--eval-split",
        choices=("test", "all"),
        default="test",
        help="test = held-out analysis; all = pooled 50 documents (fixed method still chosen on "
        "train only, so optimistic on train documents), a robustness check with narrower intervals",
    )
    args = parser.parse_args()

    split = None if args.eval_split == "all" else args.eval_split
    raw_files, matched_files = expand(args.raw), expand(args.matched)
    records = []
    for path in raw_files + matched_files:
        records.extend(read_jsonl(Path(path)))
    records = [
        record
        for record in records
        if record.condition_id in CONDITIONS and record.method_id in set(RAW + HM + MS)
    ]
    backends = {record.ocr_backend for record in records}
    if len(backends) != 1:
        raise SystemExit(f"Mixed OCR backends in inputs: {sorted(backends)}")

    norm = TextNormalization()
    methods = list(RAW + HM + MS)
    matrix = build_success_matrix(records, methods, normalization=norm)
    if not len(matrix.sample_ids):
        raise SystemExit("No sample has every raw and matched view")
    rows = matrix.condition_mask(CONDITIONS)
    evaluated = rows if split is None else rows & matrix.split_mask(split)
    iterations = args.iterations

    sets = {
        "raw4": fixed_gain_sample(matrix, RAW, rows=rows, split=split, label="raw4"),
        "hm4": fixed_gain_sample(matrix, HM, rows=rows, split=split, label="hm4"),
        "ms4": fixed_gain_sample(matrix, MS, rows=rows, split=split, label="ms4"),
    }
    result: dict[str, object] = {
        "experiment": "offline-shdocs-e3-intensity-matching",
        "proxy_only": True,
        "claim_boundary": (
            "SHDocs flat FUNSD document proxy with GT text boxes. Matching removes global "
            "brightness/contrast differences between the four SDK channels only; it does not "
            "model glare physics and is not an industrial spray-code result."
        ),
        "ocr_backend": sorted(backends)[0],
        "label": args.backend_label,
        "normalization": norm.to_dict(),
        "bootstrap_iterations": iterations,
        "evaluation_scope": "all documents (fixed method chosen on train; not held out)"
        if split is None
        else f"{split} split only (fixed method chosen on train)",
        "samples_total": int(rows.sum()),
        "samples_evaluated": int(evaluated.sum()),
        "documents_evaluated": len(
            {g for g, s in zip(matrix.groups, matrix.splits) if split is None or s == split}
        ),
        "exact_rate_evaluated": exact_rate_by_view(matrix, methods, rows=rows, split=split),
        "candidate_sets": {
            name: summarize_gain(matrix, sample, iterations=iterations)
            for name, sample in sets.items()
        },
        "headroom_difference_vs_raw4": {
            name: contrast_with_ci(matrix, sets[name], sets["raw4"], iterations=iterations)
            for name in ("hm4", "ms4")
        },
        "fixed_i0_matched_minus_raw": {
            "hm_i0_minus_i0": exact_delta_with_ci(
                matrix, "hm_i0", "i0", rows=rows, split=split, iterations=iterations
            ),
            "ms_i0_minus_i0": exact_delta_with_ci(
                matrix, "ms_i0", "i0", rows=rows, split=split, iterations=iterations
            ),
        },
        "same_channel_outcome_agreement": {
            f"{family}_{key}_vs_{key}": outcome_agreement(
                matrix, f"{family}_{key}", key, rows=rows, split=split
            )
            for family in ("hm", "ms")
            for key in RAW
        },
        "artifacts": {
            "raw_records_sha256": {Path(p).name: sha256_of(p) for p in raw_files},
            "matched_records_sha256": {Path(p).name: sha256_of(p) for p in matched_files},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"== {args.backend_label}: {result['samples_evaluated']} samples evaluated "
          f"({result['documents_evaluated']} documents, scope {args.eval_split})")
    for name, summary in result["candidate_sets"].items():
        low, high = summary["gain_ci95"]
        print(f"  {name}: fixed={summary['train_best']:8s} {100 * summary['single_exact']:5.2f}%  "
              f"oracle {100 * summary['oracle_exact']:5.2f}%  headroom {100 * summary['gain']:+.2f} pp "
              f"[{100 * low:+.2f}, {100 * high:+.2f}]")
    for name, contrast in result["headroom_difference_vs_raw4"].items():
        low, high = contrast["ci95"]
        print(f"  headroom({name}) - headroom(raw4) = {100 * contrast['delta_gain']:+.2f} pp "
              f"[{100 * low:+.2f}, {100 * high:+.2f}]")
    for name, delta in result["fixed_i0_matched_minus_raw"].items():
        low, high = delta["ci95"]
        print(f"  {name}: {100 * delta['delta_exact_a_minus_b']:+.2f} pp [{100 * low:+.2f}, {100 * high:+.2f}]")


if __name__ == "__main__":
    main()
