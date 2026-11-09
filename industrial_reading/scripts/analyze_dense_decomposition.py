#!/usr/bin/env python3
"""Decompose the dense-sweep headroom into 'more candidates' vs 'more distinct content'.

Two analyses on the already computed dense-sweep OCR records (no new OCR):

1. Spacing control. For every window of 4 virtual angles with spacing s degrees
   (s = 5, 10, ..., 45, plus the canonical 45-degree window), compute
   fixed/oracle/headroom on test with the fixed angle frozen on train. If
   headroom is mostly "more shots at the dice", narrow windows of nearly
   identical angles should already give a large headroom; if it needs distinct
   polarization content, headroom must grow with spacing.

2. Per-condition best angle. For each of the 15 highlight conditions, the best
   virtual angle on the *test* documents (hindsight) and on *train* documents,
   and how much a per-condition angle would beat the single global fixed angle
   (also frozen on train). Condition-dependent best angles are what an adaptive
   method would need to exploit; a constant best angle would mean a fixed
   analyzer is enough.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

from polread.headroom import (
    build_success_matrix,
    cluster_bootstrap,
    fixed_and_oracle,
    split_by_group,
    train_best,
)
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization
from polread.views import virtual_angle_views

CONDITIONS = tuple("abcdefghijklmno")


def load(patterns: list[str]):
    records = []
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            records.extend(read_jsonl(Path(path)))
    return records


def window(views: tuple[str, ...], start_index: int, spacing_steps: int, count: int = 4) -> list[str]:
    return [views[(start_index + i * spacing_steps) % len(views)] for i in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--iterations", type=int, default=2000)
    args = parser.parse_args()

    views = virtual_angle_views(5)
    records = [r for r in load(args.dense) if r.condition_id in set(CONDITIONS)]
    matrix = build_success_matrix(records, list(views), normalization=TextNormalization())
    rows = matrix.condition_mask(set(CONDITIONS))
    test_rows = rows & matrix.split_mask("test")

    # ---- 1. spacing control -------------------------------------------------
    spacing_results = {}
    for spacing_deg in (5, 10, 15, 20, 25, 30, 35, 40, 45):
        steps = spacing_deg // 5
        per_window = []
        for start in range(len(views)):
            candidates = window(views, start, steps)
            if len(set(candidates)) < 4:
                continue
            result = fixed_and_oracle(matrix, candidates, rows=rows)
            per_window.append(
                (result["headroom"], result["oracle_exact"], result["fixed_exact"], start * 5)
            )
        headrooms = np.array([item[0] for item in per_window])
        oracles = np.array([item[1] for item in per_window])
        spacing_results[str(spacing_deg)] = {
            "windows": len(per_window),
            "headroom_mean": float(headrooms.mean()),
            "headroom_min": float(headrooms.min()),
            "headroom_max": float(headrooms.max()),
            "oracle_mean": float(oracles.mean()),
        }
    canonical = fixed_and_oracle(matrix, ["virtual_0", "virtual_45", "virtual_90", "virtual_135"], rows=rows)

    # ---- 2. per-condition best angle ---------------------------------------
    global_fixed = train_best(matrix, list(views), rows=rows)
    per_condition = {}
    gains = []
    for condition in CONDITIONS:
        mask = matrix.condition_mask({condition})
        train = mask & matrix.split_mask("train")
        test = mask & matrix.split_mask("test")
        train_curve = matrix.success[train].mean(axis=0)
        test_curve = matrix.success[test].mean(axis=0)
        best_train = int(np.argmax(train_curve))
        best_test = int(np.argmax(test_curve))
        global_column = matrix.methods.index(global_fixed)
        cond_fixed_on_test = float(matrix.success[test][:, best_train].mean())
        per_condition[condition] = {
            "train_samples": int(train.sum()),
            "test_samples": int(test.sum()),
            "best_angle_train_deg": best_train * 5,
            "best_angle_test_deg": best_test * 5,
            "train_exact_at_best": float(train_curve[best_train]),
            "test_exact_at_train_best": cond_fixed_on_test,
            "test_exact_at_global_fixed": float(matrix.success[test][:, global_column].mean()),
            "test_exact_at_test_best_hindsight": float(test_curve[best_test]),
            "test_oracle36": float(matrix.success[test].any(axis=1).mean()),
        }
        gains.append(cond_fixed_on_test - float(matrix.success[test][:, global_column].mean()))
    angle_train = np.array([v["best_angle_train_deg"] for v in per_condition.values()])
    angle_test = np.array([v["best_angle_test_deg"] for v in per_condition.values()])

    def circular_spread(angles_deg: np.ndarray) -> float:
        doubled = np.deg2rad(2.0 * angles_deg)  # axial data: period 180
        resultant = np.hypot(np.cos(doubled).mean(), np.sin(doubled).mean())
        return float(1.0 - resultant)  # 0 = all identical, 1 = uniform

    # per-condition fixed angle (train-selected) pooled over test, versus global fixed
    pooled_cond = []
    pooled_global = []
    global_column = matrix.methods.index(global_fixed)
    for condition in CONDITIONS:
        test = matrix.condition_mask({condition}) & matrix.split_mask("test")
        best_train = per_condition[condition]["best_angle_train_deg"] // 5
        pooled_cond.append(matrix.success[test][:, best_train])
        pooled_global.append(matrix.success[test][:, global_column])
    pooled_cond_arr = np.concatenate(pooled_cond)
    pooled_global_arr = np.concatenate(pooled_global)
    # cluster bootstrap by document over the same test rows
    buckets = split_by_group(matrix, test_rows)
    packed = {}
    for group, indices in buckets.items():
        cond_pick = np.array(
            [
                matrix.success[i, per_condition[matrix.conditions[i]]["best_angle_train_deg"] // 5]
                for i in indices
            ]
        )
        packed[group] = np.stack([cond_pick, matrix.success[indices, global_column]], axis=1).astype(float)
    low, high = cluster_bootstrap(
        packed,
        lambda stacked: float(stacked[:, 0].mean() - stacked[:, 1].mean()),
        iterations=args.iterations,
    )

    payload = {
        "experiment": "offline-dense-sweep-decomposition",
        "label": args.label,
        "proxy_only": True,
        "samples_test": int(test_rows.sum()),
        "canonical_4_angle_window": {
            k: canonical[k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom")
        },
        "spacing_control": {
            "description": "4-angle windows with the given spacing in degrees; headroom = oracle - train-best fixed on the same 4 angles",
            "by_spacing_deg": spacing_results,
        },
        "per_condition_best_angle": {
            "global_fixed_train_best": global_fixed,
            "conditions": per_condition,
            "circular_spread_train_best": circular_spread(angle_train),
            "circular_spread_test_best": circular_spread(angle_test),
            "distinct_train_best_angles": sorted({int(a) for a in angle_train}),
            "per_condition_fixed_minus_global_fixed_test": {
                "delta": float(pooled_cond_arr.mean() - pooled_global_arr.mean()),
                "ci95_document_cluster": [low, high],
                "note": "Condition label is known at selection time (an upper bound on a deployable condition-aware rule).",
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"== {args.label}: 4-angle window headroom (pp) by spacing; canonical 0/45/90/135 = "
          f"{100 * canonical['headroom']:+.2f}")
    for spacing, v in spacing_results.items():
        print(f"  spacing {int(spacing):2d} deg: mean {100 * v['headroom_mean']:+.2f}  "
              f"[{100 * v['headroom_min']:+.2f}, {100 * v['headroom_max']:+.2f}]  oracle mean {100 * v['oracle_mean']:.2f}%  ({v['windows']} windows)")
    pc = payload["per_condition_best_angle"]
    print(f"== per-condition best angle: train {sorted(angle_train.tolist())}")
    print(f"   test (hindsight) {sorted(angle_test.tolist())}")
    print(f"   distinct train-best angles: {pc['distinct_train_best_angles']}  spread(train)={pc['circular_spread_train_best']:.3f}  spread(test)={pc['circular_spread_test_best']:.3f}")
    d = pc["per_condition_fixed_minus_global_fixed_test"]
    print(f"   per-condition fixed minus global fixed (test): {100 * d['delta']:+.2f} pp  CI95 [{100 * d['ci95_document_cluster'][0]:+.2f}, {100 * d['ci95_document_cluster'][1]:+.2f}]")


if __name__ == "__main__":
    main()
