#!/usr/bin/env python3
"""Summarize the dense virtual-analyzer sweep against the four-angle E2 baseline.

Inputs are the raw four-channel records (``i0..i135``) and the 36-angle
``virtual_*`` records produced by ``run_shdocs_views_ocr.py``. All "fixed"
choices are made on the train split; every reported number is test-only.

Reported comparisons
--------------------
raw4            oracle(raw4)               - fixed(raw4)           (the earlier E2)
virtual4        oracle(virtual 0/45/90/135) - fixed(virtual 4)      same pipeline as dense
dense36         oracle(virtual x36)         - fixed(virtual x36)
oracle4_vs_dense_fixed  oracle(raw4) - fixed(virtual x36)           key quantity: does a
                four-direction oracle still beat the strongest *continuous* fixed angle?
selection ladder  headroom for k evenly spaced virtual angles, k in {1,2,3,4,6,9,12,18,36},
                showing how much of the headroom is just "more candidates".
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import glob
import json
from pathlib import Path

import numpy as np

from polread.headroom import (
    build_success_matrix,
    fixed_and_oracle,
    headroom_with_ci,
    paired_delta_with_ci,
)
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization
from polread.views import virtual_angle_views

RAW = ("i0", "i45", "i90", "i135")
CANONICAL_VIRTUAL = ("virtual_0", "virtual_45", "virtual_90", "virtual_135")
LADDER = (1, 2, 3, 4, 6, 9, 12, 18, 36)


def load_records(patterns: list[str]):
    paths = sorted({path for pattern in patterns for path in glob.glob(pattern)})
    if not paths:
        raise SystemExit(f"No files match {patterns}")
    records = []
    for path in paths:
        records.extend(read_jsonl(Path(path)))
    return records, paths


def evenly_spaced(views: tuple[str, ...], count: int) -> list[str]:
    if 36 % count:
        raise ValueError("ladder counts must divide 36")
    return [views[index] for index in range(0, len(views), 36 // count)]


def curve(matrix, views, rows, split):
    mask = rows & matrix.split_mask(split)
    return {
        view: float(matrix.column(view)[mask].mean()) if mask.any() else None for view in views
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", nargs="+", required=True, help="glob(s) of dense-sweep JSONL")
    parser.add_argument("--raw", nargs="+", required=True, help="glob(s) of raw-four JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend-label", required=True)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--whitespace", choices=("preserve", "collapse", "remove"), default="collapse")
    args = parser.parse_args()

    norm = TextNormalization(whitespace=args.whitespace)
    dense_records, dense_files = load_records(args.dense)
    raw_records, raw_files = load_records(args.raw)
    backends = {record.ocr_backend for record in dense_records} | {
        record.ocr_backend for record in raw_records
    }
    if len(backends) != 1:
        raise SystemExit(f"Mixed OCR backends in inputs: {sorted(backends)}")
    views = virtual_angle_views(5)

    result: dict[str, object] = {
        "experiment": "offline-shdocs-dense-virtual-angle-sweep",
        "proxy_only": True,
        "claim_boundary": (
            "SHDocs flat FUNSD document proxy with GT text boxes; virtual angles are synthesized "
            "from 8-bit SDK-exported I0/I45/I90/I135 via linear Stokes. Not an industrial "
            "spray-code result and not a physical polarizer sweep."
        ),
        "ocr_backend": sorted(backends)[0],
        "label": args.backend_label,
        "normalization": norm.to_dict(),
        "input_files": {"dense": len(dense_files), "raw": len(raw_files)},
        "dense_angles_deg": [int(name.removeprefix("virtual_")) for name in views],
    }

    # Combine raw + dense into one record list; sample_id sets must coincide.
    combined = [r for r in raw_records if r.method_id in RAW] + [
        r for r in dense_records if r.method_id in views
    ]
    for slice_name, conditions in (
        ("highlight_a_to_o", set("abcdefghijklmno")),
        ("camera_clear", {"camera"}),
    ):
        subset = [r for r in combined if r.condition_id in conditions]
        if not subset:
            continue
        matrix = build_success_matrix(subset, list(RAW) + list(views), normalization=norm)
        rows = matrix.condition_mask(conditions)
        if not len(matrix.sample_ids):
            present = sorted({r.method_id for r in subset})
            raise SystemExit(
                f"Slice {slice_name!r}: no sample has every one of the {len(RAW) + len(views)} "
                f"required views. Views present for this slice: {present[:6]}... "
                "Run the missing views (raw i0/i45/i90/i135 and virtual_0..175) for these conditions."
            )
        section: dict[str, object] = {
            "samples_total": int(rows.sum()),
            "samples_test": int((rows & matrix.split_mask("test")).sum()),
            "documents_test": len({g for g, s in zip(matrix.groups, matrix.splits) if s == "test"}),
        }
        section["exact_curve_train"] = curve(matrix, list(RAW) + list(views), rows, "train")
        section["exact_curve_val"] = curve(matrix, list(RAW) + list(views), rows, "val")
        section["exact_curve_test"] = curve(matrix, list(RAW) + list(views), rows, "test")

        section["raw4"] = headroom_with_ci(matrix, list(RAW), rows=rows, iterations=args.iterations)
        section["virtual4_same_pipeline"] = headroom_with_ci(
            matrix, list(CANONICAL_VIRTUAL), rows=rows, iterations=args.iterations
        )
        section["dense36"] = headroom_with_ci(matrix, list(views), rows=rows, iterations=args.iterations)

        dense_fixed = fixed_and_oracle(matrix, list(views), rows=rows)["train_best"]
        raw_fixed = section["raw4"]["train_best"]
        section["dense_fixed_vs_raw_fixed"] = paired_delta_with_ci(
            matrix, dense_fixed, raw_fixed, rows=rows, iterations=args.iterations
        )
        section["dense_fixed_vs_virtual_canonical_fixed"] = paired_delta_with_ci(
            matrix,
            dense_fixed,
            section["virtual4_same_pipeline"]["train_best"],
            rows=rows,
            iterations=args.iterations,
        )
        # oracle over raw4 versus the strongest continuous fixed angle
        test = rows & matrix.split_mask("test")
        raw_columns = [matrix.methods.index(name) for name in RAW]
        oracle_raw = matrix.success[test][:, raw_columns].any(axis=1).mean()
        dense_fixed_exact = matrix.column(dense_fixed)[test].mean()
        # build a synthetic paired comparison through the generic bootstrap
        from polread.headroom import cluster_bootstrap, split_by_group

        buckets = split_by_group(matrix, test)
        dense_column = matrix.methods.index(dense_fixed)
        packed = {
            group: np.stack(
                [
                    matrix.success[indices][:, raw_columns].any(axis=1),
                    matrix.success[indices, dense_column],
                ],
                axis=1,
            ).astype(np.float64)
            for group, indices in buckets.items()
        }
        low, high = cluster_bootstrap(
            packed,
            lambda stacked: float(stacked[:, 0].mean() - stacked[:, 1].mean()),
            iterations=args.iterations,
        )
        section["oracle4_vs_dense_fixed"] = {
            "dense_fixed_angle": dense_fixed,
            "oracle_raw4_exact": float(oracle_raw),
            "dense_fixed_exact": float(dense_fixed_exact),
            "headroom": float(oracle_raw - dense_fixed_exact),
            "ci95": [low, high],
        }
        ladder = {}
        for count in LADDER:
            subset_views = evenly_spaced(views, count)
            ladder[str(count)] = {
                "angles_deg": [int(name.removeprefix("virtual_")) for name in subset_views],
                **fixed_and_oracle(matrix, subset_views, rows=rows),
            }
        section["selection_ladder_evenly_spaced"] = ladder
        result[slice_name] = section

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    focus = result.get("highlight_a_to_o")
    if focus:
        print(
            json.dumps(
                {
                    "label": args.backend_label,
                    "samples_test": focus["samples_test"],
                    "raw4": {k: focus["raw4"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
                    "virtual4": {k: focus["virtual4_same_pipeline"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
                    "dense36": {k: focus["dense36"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
                    "oracle4_vs_dense_fixed": focus["oracle4_vs_dense_fixed"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
