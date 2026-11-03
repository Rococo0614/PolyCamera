"""Aggregation, train-best selection and grouped bootstrap for OCR records."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Iterable

import numpy as np

from .records import OCRRecord
from .text_metrics import TextNormalization, evaluate_text


def _evaluated(record: OCRRecord, normalization: TextNormalization) -> dict[str, object]:
    return evaluate_text(
        record.ground_truth,
        "" if record.rejected else record.prediction,
        normalization=normalization,
    )


def summarize_records(
    records: Iterable[OCRRecord],
    *,
    normalization: TextNormalization | None = None,
) -> dict[str, dict[str, float | int]]:
    cfg = normalization or TextNormalization()
    grouped: dict[str, list[OCRRecord]] = defaultdict(list)
    for record in records:
        grouped[record.method_id].append(record)
    result: dict[str, dict[str, float | int]] = {}
    for method_id, method_records in sorted(grouped.items()):
        valid_records = [record for record in method_records if record.status == "ok"]
        metrics = [_evaluated(record, cfg) for record in valid_records]
        if not metrics:
            result[method_id] = {
                "records": len(method_records),
                "evaluated_records": 0,
                "error_records": len(method_records),
                "raw_exact_read": math.nan,
                "normalized_exact_read": math.nan,
                "macro_cer": math.nan,
                "pooled_cer": math.nan,
                "reject_rate": math.nan,
                "latency_mean_ms": math.nan,
            }
            continue
        character_edits = sum(int(metric["char_edits"]) for metric in metrics)
        reference_characters = sum(int(metric["reference_characters"]) for metric in metrics)
        latencies = [
            float(record.latency_ms)
            for record in valid_records
            if record.latency_ms is not None and math.isfinite(record.latency_ms)
        ]
        result[method_id] = {
            "records": len(method_records),
            "evaluated_records": len(valid_records),
            "error_records": len(method_records) - len(valid_records),
            "raw_exact_read": float(np.mean([metric["raw_exact_read"] for metric in metrics])),
            "normalized_exact_read": float(
                np.mean([metric["normalized_exact_read"] for metric in metrics])
            ),
            "macro_cer": float(np.mean([metric["cer"] for metric in metrics])),
            "pooled_cer": (
                float(character_edits / reference_characters)
                if reference_characters
                else math.nan
            ),
            "reject_rate": float(np.mean([record.rejected for record in valid_records])),
            "latency_mean_ms": float(np.mean(latencies)) if latencies else math.nan,
        }
    return result


def select_train_best(
    records: Iterable[OCRRecord],
    candidate_methods: set[str],
    *,
    normalization: TextNormalization | None = None,
) -> str:
    train_records = [
        record
        for record in records
        if record.split == "train" and record.method_id in candidate_methods
    ]
    summary = summarize_records(train_records, normalization=normalization)
    missing = candidate_methods - set(summary)
    if missing:
        raise ValueError(f"Candidate methods missing from training records: {sorted(missing)}")
    return max(
        sorted(candidate_methods),
        key=lambda method: (
            summary[method]["normalized_exact_read"],
            -summary[method]["macro_cer"],
        ),
    )


def oracle_exact_rate(
    records: Iterable[OCRRecord],
    candidate_methods: set[str],
    *,
    split: str = "test",
    normalization: TextNormalization | None = None,
) -> dict[str, float | int]:
    cfg = normalization or TextNormalization()
    by_sample: dict[str, list[OCRRecord]] = defaultdict(list)
    for record in records:
        if record.split == split and record.method_id in candidate_methods and record.status == "ok":
            by_sample[record.sample_id].append(record)
    if not by_sample:
        raise ValueError(f"No {split} records for oracle candidates")
    successes = 0
    best_cers = []
    incomplete = 0
    for sample_records in by_sample.values():
        present = {record.method_id for record in sample_records}
        if present != candidate_methods:
            incomplete += 1
            continue
        metrics = [_evaluated(record, cfg) for record in sample_records]
        successes += any(bool(metric["normalized_exact_read"]) for metric in metrics)
        best_cers.append(min(float(metric["cer"]) for metric in metrics))
    evaluated = len(best_cers)
    return {
        "samples": evaluated,
        "incomplete_samples": incomplete,
        "normalized_exact_read": float(successes / evaluated) if evaluated else math.nan,
        "macro_cer": float(np.mean(best_cers)) if best_cers else math.nan,
    }


def complementary_success_diagnostics(
    records: Iterable[OCRRecord],
    candidate_methods: set[str],
    *,
    split: str = "test",
    normalization: TextNormalization | None = None,
) -> dict[str, float | int | dict[str, int]]:
    """Count all-fail, exactly-one-success and multi-success samples."""

    cfg = normalization or TextNormalization()
    by_sample: dict[str, list[OCRRecord]] = defaultdict(list)
    for record in records:
        if record.split == split and record.method_id in candidate_methods and record.status == "ok":
            by_sample[record.sample_id].append(record)
    complete = 0
    all_fail = 0
    exactly_one = 0
    multiple = 0
    unique_winner_counts = {method: 0 for method in sorted(candidate_methods)}
    for sample_records in by_sample.values():
        if {record.method_id for record in sample_records} != candidate_methods:
            continue
        complete += 1
        successful = [
            record.method_id
            for record in sample_records
            if bool(_evaluated(record, cfg)["normalized_exact_read"])
        ]
        if not successful:
            all_fail += 1
        elif len(successful) == 1:
            exactly_one += 1
            unique_winner_counts[successful[0]] += 1
        else:
            multiple += 1
    denominator = complete or 1
    return {
        "complete_samples": complete,
        "all_fail_samples": all_fail,
        "all_fail_rate": float(all_fail / denominator),
        "exactly_one_success_samples": exactly_one,
        "exactly_one_success_rate": float(exactly_one / denominator),
        "multiple_success_samples": multiple,
        "multiple_success_rate": float(multiple / denominator),
        "unique_winner_counts": unique_winner_counts,
    }


def confidence_selector_summary(
    records: Iterable[OCRRecord],
    candidate_methods: set[str],
    *,
    split: str = "test",
    normalization: TextNormalization | None = None,
) -> dict[str, object]:
    """Evaluate a deployable four-OCR confidence selector with full latency accounting."""

    cfg = normalization or TextNormalization()
    by_sample: dict[str, list[OCRRecord]] = defaultdict(list)
    for record in records:
        if (
            record.split == split
            and record.status == "ok"
            and record.method_id in candidate_methods
        ):
            by_sample[record.sample_id].append(record)
    metrics: list[dict[str, object]] = []
    selections = {method: 0 for method in sorted(candidate_methods)}
    sequential_latencies: list[float] = []
    incomplete = 0
    for sample_records in by_sample.values():
        if {record.method_id for record in sample_records} != candidate_methods:
            incomplete += 1
            continue
        selected = max(
            sample_records,
            key=lambda record: (
                -math.inf if record.confidence is None else record.confidence,
                record.method_id,
            ),
        )
        selections[selected.method_id] += 1
        metrics.append(_evaluated(selected, cfg))
        latencies = [
            float(record.latency_ms)
            for record in sample_records
            if record.latency_ms is not None and math.isfinite(record.latency_ms)
        ]
        if len(latencies) == len(candidate_methods):
            sequential_latencies.append(sum(latencies))
    return {
        "samples": len(metrics),
        "incomplete_samples": incomplete,
        "normalized_exact_read": (
            float(np.mean([metric["normalized_exact_read"] for metric in metrics]))
            if metrics
            else math.nan
        ),
        "macro_cer": (
            float(np.mean([metric["cer"] for metric in metrics])) if metrics else math.nan
        ),
        "selection_counts": selections,
        "four_ocr_sequential_latency_mean_ms": (
            float(np.mean(sequential_latencies)) if sequential_latencies else math.nan
        ),
    }


def paired_group_bootstrap_exact_delta(
    records: Iterable[OCRRecord],
    method_a: str,
    method_b: str,
    *,
    split: str = "test",
    iterations: int = 2000,
    seed: int = 20261102,
    normalization: TextNormalization | None = None,
) -> dict[str, float | int]:
    """Cluster-bootstrap exact-read delta A-B by ``group_id``."""

    cfg = normalization or TextNormalization()
    selected = [record for record in records if record.split == split and record.status == "ok"]
    lookup = {(record.sample_id, record.method_id): record for record in selected}
    sample_groups: dict[str, str] = {}
    for record in selected:
        sample_groups.setdefault(record.sample_id, record.group_id)
    paired: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for sample_id, group_id in sample_groups.items():
        first = lookup.get((sample_id, method_a))
        second = lookup.get((sample_id, method_b))
        if first is None or second is None:
            continue
        first_exact = int(_evaluated(first, cfg)["normalized_exact_read"])
        second_exact = int(_evaluated(second, cfg)["normalized_exact_read"])
        paired[group_id].append((first_exact, second_exact))
    groups = sorted(paired)
    if not groups:
        raise ValueError("No paired groups found")
    observed_pairs = [pair for group in groups for pair in paired[group]]
    observed = float(np.mean([a - b for a, b in observed_pairs]))
    rng = np.random.default_rng(seed)
    samples = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        chosen = rng.choice(groups, size=len(groups), replace=True)
        pairs = [pair for group in chosen for pair in paired[str(group)]]
        samples[index] = np.mean([a - b for a, b in pairs])
    low, high = np.percentile(samples, (2.5, 97.5))
    return {
        "groups": len(groups),
        "paired_samples": len(observed_pairs),
        "delta_exact_a_minus_b": observed,
        "ci95_low": float(low),
        "ci95_high": float(high),
        "iterations": iterations,
    }


def paired_group_bootstrap_oracle_delta(
    records: Iterable[OCRRecord],
    fixed_method: str,
    candidate_methods: set[str],
    *,
    split: str = "test",
    iterations: int = 5000,
    seed: int = 20261102,
    normalization: TextNormalization | None = None,
) -> dict[str, float | int]:
    """Cluster-bootstrap per-sample oracle minus one deployable fixed method."""

    if fixed_method not in candidate_methods:
        raise ValueError("fixed_method must be included in candidate_methods")
    cfg = normalization or TextNormalization()
    by_sample: dict[str, list[OCRRecord]] = defaultdict(list)
    for record in records:
        if (
            record.split == split
            and record.status == "ok"
            and record.method_id in candidate_methods
        ):
            by_sample[record.sample_id].append(record)
    paired: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for sample_records in by_sample.values():
        if {record.method_id for record in sample_records} != candidate_methods:
            continue
        exact = {
            record.method_id: int(_evaluated(record, cfg)["normalized_exact_read"])
            for record in sample_records
        }
        oracle = max(exact.values())
        paired[sample_records[0].group_id].append((oracle, exact[fixed_method]))
    groups = sorted(paired)
    if not groups:
        raise ValueError("No complete paired groups found for oracle bootstrap")
    observed_pairs = [pair for group in groups for pair in paired[group]]
    observed = float(np.mean([oracle - fixed for oracle, fixed in observed_pairs]))
    rng = np.random.default_rng(seed)
    samples = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        chosen = rng.choice(groups, size=len(groups), replace=True)
        pairs = [pair for group in chosen for pair in paired[str(group)]]
        samples[index] = np.mean([oracle - fixed for oracle, fixed in pairs])
    low, high = np.percentile(samples, (2.5, 97.5))
    oracle_only = sum(oracle == 1 and fixed == 0 for oracle, fixed in observed_pairs)
    return {
        "groups": len(groups),
        "paired_samples": len(observed_pairs),
        "fixed_method": fixed_method,
        "oracle_only_successes": oracle_only,
        "fixed_only_successes": 0,
        "delta_exact_oracle_minus_fixed": observed,
        "ci95_low": float(low),
        "ci95_high": float(high),
        "iterations": iterations,
    }
