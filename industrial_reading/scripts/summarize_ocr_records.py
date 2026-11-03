#!/usr/bin/env python3
"""Summarize backend-independent OCR JSONL records."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from polread.evaluation import (
    complementary_success_diagnostics,
    confidence_selector_summary,
    oracle_exact_rate,
    paired_group_bootstrap_oracle_delta,
    select_train_best,
    summarize_records,
)
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fixed-methods", default="i0,i45,i90,i135", help="Comma-separated oracle candidates"
    )
    parser.add_argument("--backend", help="Required when the JSONL contains multiple OCR backends")
    parser.add_argument(
        "--conditions",
        help="Optional comma-separated condition subset, e.g. camera or a,b,...,o",
    )
    parser.add_argument(
        "--exclusions-file",
        type=Path,
        default=Path("industrial_reading/evidence/shdocs_excluded_rois_v1.json"),
    )
    parser.add_argument("--annotations-root", type=Path)
    parser.add_argument(
        "--labels",
        help="Optional comma-separated FUNSD labels, e.g. question,header",
    )
    parser.add_argument("--whitespace", choices=("preserve", "collapse", "remove"), default="collapse")
    args = parser.parse_args()

    records = read_jsonl(args.records)
    if args.annotations_root:
        annotation_lookup: dict[tuple[str, str], str] = {}
        for annotation_path in args.annotations_root.glob("*.json"):
            form = json.loads(annotation_path.read_text(encoding="utf-8")).get("form", [])
            for region_index, element in enumerate(form):
                annotation_lookup[(annotation_path.stem, str(region_index))] = str(
                    element.get("label", "unknown")
                )
        records = [
            record
            if record.annotation_label
            else replace(
                record,
                annotation_label=annotation_lookup.get(
                    (record.group_id, record.region_id), "unknown"
                ),
            )
            for record in records
        ]
    excluded_samples: set[str] = set()
    if args.exclusions_file and args.exclusions_file.is_file():
        exclusion_payload = json.loads(args.exclusions_file.read_text(encoding="utf-8"))
        excluded_samples = {str(item) for item in exclusion_payload.get("sample_ids", [])}
        records = [record for record in records if record.sample_id not in excluded_samples]
    backends = sorted({record.ocr_backend for record in records})
    if args.backend:
        if args.backend not in backends:
            raise SystemExit(f"Backend {args.backend!r} not found; available: {backends}")
        records = [record for record in records if record.ocr_backend == args.backend]
        backend = args.backend
    elif len(backends) == 1:
        backend = backends[0]
    else:
        raise SystemExit(f"Multiple OCR backends found; select --backend from {backends}")
    selected_conditions = None
    if args.conditions:
        selected_conditions = {
            item.strip() for item in args.conditions.split(",") if item.strip()
        }
        records = [record for record in records if record.condition_id in selected_conditions]
        if not records:
            raise SystemExit(f"No records remain for conditions {sorted(selected_conditions)}")
    selected_labels = None
    if args.labels:
        selected_labels = {item.strip() for item in args.labels.split(",") if item.strip()}
        records = [record for record in records if record.annotation_label in selected_labels]
        if not records:
            raise SystemExit(f"No records remain for labels {sorted(selected_labels)}")
    normalization = TextNormalization(whitespace=args.whitespace)
    fixed = {item.strip() for item in args.fixed_methods.split(",") if item.strip()}
    train_best = select_train_best(records, fixed, normalization=normalization)
    split_summaries = {
        split: summarize_records(
            [record for record in records if record.split == split],
            normalization=normalization,
        )
        for split in ("train", "val", "test")
    }
    oracle = oracle_exact_rate(records, fixed, split="test", normalization=normalization)
    fixed_test = split_summaries["test"][train_best]
    condition_summaries = {
        condition: summarize_records(
            [
                record
                for record in records
                if record.split == "test" and record.condition_id == condition
            ],
            normalization=normalization,
        )
        for condition in sorted(
            {record.condition_id for record in records if record.split == "test"}
        )
    }
    label_summaries = {
        label: summarize_records(
            [
                record
                for record in records
                if record.split == "test" and record.annotation_label == label
            ],
            normalization=normalization,
        )
        for label in sorted(
            {record.annotation_label for record in records if record.split == "test"}
        )
    }
    train_best_condition_exact = {
        condition: float(summary[train_best]["normalized_exact_read"])
        for condition, summary in condition_summaries.items()
        if train_best in summary
    }
    worst_condition = min(
        train_best_condition_exact,
        key=train_best_condition_exact.get,
    )
    payload = {
        "records_path": str(args.records.resolve()),
        "excluded_sample_ids": len(excluded_samples),
        "ocr_backend": backend,
        "conditions": sorted(selected_conditions) if selected_conditions else "all",
        "labels": sorted(selected_labels) if selected_labels else "all",
        "normalization": normalization.to_dict(),
        "split_summaries": split_summaries,
        "test_condition_summaries": condition_summaries,
        "test_label_summaries": label_summaries,
        "train_best_fixed": train_best,
        "test_train_best_fixed": fixed_test,
        "test_train_best_condition_exact": train_best_condition_exact,
        "test_train_best_worst_condition": {
            "condition": worst_condition,
            "normalized_exact_read": train_best_condition_exact[worst_condition],
        },
        "test_four_angle_oracle": oracle,
        "test_adaptation_headroom_exact": float(
            oracle["normalized_exact_read"] - fixed_test["normalized_exact_read"]
        ),
        "test_adaptation_headroom_cluster_bootstrap": paired_group_bootstrap_oracle_delta(
            records,
            train_best,
            fixed,
            split="test",
            normalization=normalization,
        ),
        "test_complementarity": complementary_success_diagnostics(
            records, fixed, split="test", normalization=normalization
        ),
        "test_confidence_selector": confidence_selector_summary(
            records, fixed, split="test", normalization=normalization
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
