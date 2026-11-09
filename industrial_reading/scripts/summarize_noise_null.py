#!/usr/bin/env python3
"""Noise-only null control for the four-channel headroom.

A null view is the 4-channel mean (or raw I0) plus independent heteroscedastic
Gaussian noise of strength ``m`` times the PDD-High noise model. Re-draws of one
base carry *identical* content and differ only by noise, so any "best-of" gain
they show is pure selection / OCR-instability effect. Two null statistics are
compared, on the frozen test split (conditions a-o), with the real four-channel
headroom ``oracle(raw4) - fixed(raw4)`` (fixed = train-best, which is I0):

``exchangeable``
    four noisy re-draws, ``mean(any) - mean(single)``. All four views are noisy,
    so the single-view accuracy is lower than the real clean I0.

``clean_base``
    the clean base plus three noisy re-draws, ``any - base`` averaged over the
    four triples. Same form as the real set {I0, I45, I90, I135}: identical
    baseline accuracy, alternatives carry no new content.

Doses are anchored on pixel statistics (``measure_view_differences.py``), not on
OCR results: a dose "matches" when the pixel distance between its views is
comparable to the distance between the real polarization channels.

A null built from iid Gaussian noise differs from real inter-channel differences
(which are spatially structured), so it bounds how much of the headroom a
perturbation of the same size can create; it does not model glare.
"""

from __future__ import annotations

import argparse
from collections import Counter
import glob
import hashlib
import json
from pathlib import Path
import re

from polread.analysis import (
    bracket_doses,
    clean_base_gain_sample,
    contrast_with_ci,
    exact_delta_with_ci,
    exact_rate_by_view,
    exchangeable_gain_sample,
    fixed_gain_sample,
    summarize_gain,
)
from polread.headroom import build_success_matrix
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization

RAW = ("i0", "i45", "i90", "i135")
CONDITIONS = set("abcdefghijklmno")
NULL_NAME = re.compile(r"^null_(mean|i0)_m([0-9]+(?:\.[0-9]+)?)_k([0-9]+)$")
NOISE_FREE_MEAN = "null_mean_m0_k0"


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


def group_null_views(names: set[str]) -> dict[tuple[str, float], list[str]]:
    """``(base, dose) -> sorted realization names`` for doses > 0."""

    grouped: dict[tuple[str, float], list[tuple[int, str]]] = {}
    for name in names:
        match = NULL_NAME.match(name)
        if not match:
            continue
        dose = float(match.group(2))
        if dose == 0.0:
            continue
        grouped.setdefault((match.group(1), dose), []).append((int(match.group(3)), name))
    return {key: [name for _, name in sorted(items)] for key, items in sorted(grouped.items())}


def position(value: float, reference: list[float]) -> str:
    if not reference:
        return "unknown"
    if value < min(reference):
        return "below"
    if value > max(reference):
        return "above"
    return "within"


def real_distances(differences: dict, base: str) -> list[float]:
    """Median pixel distances between the real clean base and the real alternatives."""

    pairs = differences["pairs"]
    if base == "i0":
        return [pairs[f"raw:i0-{key}"]["median"] for key in ("i45", "i90", "i135")]
    return [pairs[f"raw:{key}-mean"]["median"] for key in RAW]


def fmt_interval(value: dict, key: str = "gain_ci95") -> str:
    low, high = value[key]
    return f"[{100 * low:+.2f}, {100 * high:+.2f}]"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", nargs="+", required=True)
    parser.add_argument("--null", nargs="+", required=True)
    parser.add_argument("--view-differences", type=Path, help="output of measure_view_differences.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend-label", required=True)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--realizations", type=int, default=4)
    parser.add_argument(
        "--eval-split",
        choices=("test", "all"),
        default="test",
        help=(
            "'test' (default) is the held-out analysis. 'all' scores the 50 documents pooled "
            "to narrow intervals; the fixed baseline is still chosen on train only, so the "
            "baseline is optimistic on train documents. Use it only as a robustness check."
        ),
    )
    parser.add_argument(
        "--error-policy",
        choices=("fail", "drop"),
        default="fail",
        help=(
            "OCR calls that crashed (status != ok): 'fail' scores them as failed reads, "
            "'drop' removes every sample with at least one crashed view"
        ),
    )
    args = parser.parse_args()

    split = None if args.eval_split == "all" else args.eval_split
    raw_files, null_files = expand(args.raw), expand(args.null)
    raw_records = [r for p in raw_files for r in read_jsonl(Path(p))]
    null_records = [r for p in null_files for r in read_jsonl(Path(p))]
    records = [r for r in raw_records if r.method_id in RAW and r.condition_id in CONDITIONS]
    records += [
        r for r in null_records if NULL_NAME.match(r.method_id) and r.condition_id in CONDITIONS
    ]
    backends = {record.ocr_backend for record in records}
    if len(backends) != 1:
        raise SystemExit(f"Mixed OCR backends in inputs: {sorted(backends)}")

    present = {r.method_id for r in records if r.method_id not in RAW}
    grouped = group_null_views(present)
    for key, names in grouped.items():
        if len(names) != args.realizations:
            raise SystemExit(f"{key}: expected {args.realizations} realizations, found {names}")
    methods = list(RAW) + sorted(present)
    norm = TextNormalization()
    crashed = [r for r in records if r.status != "ok"]
    crashed_samples = {r.sample_id for r in crashed}
    matrix = build_success_matrix(
        records, methods, normalization=norm, errors_as_failures=args.error_policy == "fail"
    )
    seen = {r.sample_id for r in records}
    expected = len(seen) - (len(crashed_samples) if args.error_policy == "drop" else 0)
    if len(matrix.sample_ids) != expected:
        raise SystemExit(
            f"{expected - len(matrix.sample_ids)} samples lack at least one view; "
            "wait for all shards to finish"
        )
    error_handling = {
        "policy": args.error_policy,
        "crashed_ocr_calls": len(crashed),
        "crashed_samples": len(crashed_samples),
        "samples_dropped": len(seen) - len(matrix.sample_ids),
        "total_ocr_calls": len(records),
        "crashed_by_view": dict(Counter(r.method_id for r in crashed)),
        "crash_signatures": sorted({r.error.split(" died with ")[-1] for r in crashed}),
        "test_samples_with_a_crash": len(
            {r.sample_id for r in crashed if r.split == "test"}
        ),
        "samples_with_a_crash_by_split": {
            name: len({r.sample_id for r in crashed if r.split == name})
            for name in ("train", "val", "test")
        },
    }
    rows = matrix.condition_mask(CONDITIONS)
    iterations = args.iterations

    real = fixed_gain_sample(matrix, RAW, rows=rows, split=split, label="real_raw4_fixed")
    if real.chosen != "i0":
        print(f"note: train-best raw channel is {real.chosen}, not i0")
    # Same statistic as the exchangeable null (oracle minus the *mean* single view).
    real_mean_single = exchangeable_gain_sample(
        matrix, RAW, rows=rows, split=split, label="real_raw4_vs_mean_single"
    )
    differences = (
        json.loads(args.view_differences.read_text(encoding="utf-8"))
        if args.view_differences
        else None
    )
    real_pair_medians = (
        [
            stats["median"]
            for name, stats in differences["pairs"].items()
            if name.startswith("raw:") and not name.endswith("-mean")
        ]
        if differences
        else []
    )

    clean_views = {"i0": "i0", "mean": NOISE_FREE_MEAN}
    doses: dict[str, object] = {}
    for (base, dose), names in grouped.items():
        tag = f"null_{base}_m{dose:g}"
        exchangeable = exchangeable_gain_sample(
            matrix, names, rows=rows, split=split, label=f"{tag}_exchangeable"
        )
        entry: dict[str, object] = {
            "base": base,
            "dose_multiplier_of_pdd_high": dose,
            "views": names,
            "exchangeable": {
                "null": summarize_gain(matrix, exchangeable, iterations=iterations),
                "real_fixed_minus_null": contrast_with_ci(
                    matrix, real, exchangeable, iterations=iterations
                ),
                "real_oracle_minus_mean_single_minus_null": contrast_with_ci(
                    matrix, real_mean_single, exchangeable, iterations=iterations
                ),
            },
        }
        clean_view = clean_views[base]
        if clean_view in matrix.methods:
            clean = clean_base_gain_sample(
                matrix, clean_view, names, alternatives=3, rows=rows, split=split, label=f"{tag}_clean_base"
            )
            entry["clean_base"] = {
                "clean_base_view": clean_view,
                "null": summarize_gain(matrix, clean, iterations=iterations),
                "real_fixed_minus_null": contrast_with_ci(matrix, real, clean, iterations=iterations),
            }
        if differences is not None:
            pair = differences["pairs"].get(f"{tag}:k0-k1")
            to_base = differences["pairs"].get(f"{tag}:k0-base")
            entry["pixel_distance"] = {
                "pair_rms_median_gray": pair["median"] if pair else None,
                "pair_vs_real_raw_pairs": position(pair["median"], real_pair_medians) if pair else None,
                "to_base_rms_median_gray": to_base["median"] if to_base else None,
                "to_base_vs_real_distances": (
                    position(to_base["median"], real_distances(differences, base)) if to_base else None
                ),
            }
        doses[f"{base}_m{dose:g}"] = entry

    # Dose anchors for the I0-based clean-base null, fixed by rule (never by looking at gains):
    #  * pixel distance: noisy copy to its base vs real I0 to the other three channels;
    #  * readability: exact rate of a noisy copy vs mean exact rate of the real I45/I90/I135.
    anchors: dict[str, object] | None = None
    i0_entries = {
        entry["dose_multiplier_of_pdd_high"]: (key, entry)
        for key, entry in doses.items()
        if entry["base"] == "i0" and "clean_base" in entry
    }
    if differences is not None and i0_entries:
        alternatives_exact = exact_rate_by_view(
            matrix, ("i45", "i90", "i135"), rows=rows, split=split
        )
        alternatives_mean = sum(alternatives_exact.values()) / len(alternatives_exact)
        i0_distances = real_distances(differences, "i0")
        by_distance = bracket_doses(
            [
                (dose, entry["pixel_distance"]["to_base_rms_median_gray"])
                for dose, (_, entry) in i0_entries.items()
            ],
            min(i0_distances),
            max(i0_distances),
        )
        by_accuracy = bracket_doses(
            [
                (dose, entry["exchangeable"]["null"]["single_exact"])
                for dose, (_, entry) in i0_entries.items()
            ],
            alternatives_mean,
            alternatives_mean,
        )
        anchors = {
            "pixel_distance": {
                "criterion": "to-base RMS of the noisy copy within the real I0-to-other-channel "
                "median RMS range (nearest dose on each side if none inside)",
                "real_i0_to_other_channels_gray": i0_distances,
                "doses": by_distance,
                "entries": [i0_entries[dose][0] for dose in by_distance],
            },
            "alternative_accuracy": {
                "criterion": "exact rate of the noisy copy bracketing the mean exact rate of the "
                "real I45/I90/I135 (selected post hoc, after the dose-response was visible)",
                "real_alternatives_exact": alternatives_exact,
                "real_alternatives_mean_exact": alternatives_mean,
                "doses": by_accuracy,
                "entries": [i0_entries[dose][0] for dose in by_accuracy],
            },
        }

    result: dict[str, object] = {
        "experiment": "offline-shdocs-noise-only-null-control",
        "proxy_only": True,
        "claim_boundary": (
            "SHDocs flat FUNSD document proxy with GT text boxes. The null perturbs identical "
            "content with iid heteroscedastic Gaussian noise calibrated on PDD High; it bounds "
            "selection/instability effects of a given pixel-perturbation size but is not a model "
            "of glare or of real re-capture variability."
        ),
        "ocr_backend": sorted(backends)[0],
        "label": args.backend_label,
        "normalization": norm.to_dict(),
        "bootstrap_iterations": iterations,
        "realizations_per_dose": args.realizations,
        "error_handling": error_handling,
        "evaluation_scope": "all documents (fixed method chosen on train; not held out)"
        if split is None
        else f"{split} split only (fixed method chosen on train)",
        "samples_total": int(rows.sum()),
        "samples_evaluated": int(
            (rows if split is None else rows & matrix.split_mask(split)).sum()
        ),
        "documents_evaluated": len(
            {
                g
                for g, s in zip(matrix.groups, matrix.splits)
                if split is None or s == split
            }
        ),
        "real_raw4": summarize_gain(matrix, real, iterations=iterations),
        "real_raw4_oracle_minus_mean_single": summarize_gain(
            matrix, real_mean_single, iterations=iterations
        ),
        "real_pixel_distance_gray": (
            {
                "raw_pair_median_range": [min(real_pair_medians), max(real_pair_medians)],
                "i0_to_other_channels_median": dict(
                    zip(("i45", "i90", "i135"), real_distances(differences, "i0"))
                ),
                "channels_to_mean_median": dict(zip(RAW, real_distances(differences, "mean"))),
            }
            if differences
            else None
        ),
        "doses": doses,
        "anchors": anchors,
        "noise_free_mean_view_minus_i0": (
            exact_delta_with_ci(
                matrix, NOISE_FREE_MEAN, "i0", rows=rows, split=split, iterations=iterations
            )
            if NOISE_FREE_MEAN in present
            else None
        ),
        "exact_rate_evaluated": exact_rate_by_view(matrix, methods, rows=rows, split=split),
        "artifacts": {
            "raw_records_sha256": {Path(p).name: sha256_of(p) for p in raw_files},
            "null_records_sha256": {Path(p).name: sha256_of(p) for p in null_files},
            "view_differences_sha256": (
                sha256_of(str(args.view_differences)) if args.view_differences else None
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    real_summary = result["real_raw4"]
    mean_single = result["real_raw4_oracle_minus_mean_single"]
    print(f"== {args.backend_label}: {result['samples_evaluated']} samples evaluated ({result['documents_evaluated']} documents, scope {args.eval_split})"
          f"  [error policy: {args.error_policy}; crashed OCR calls {len(crashed)} of {len(records)}, "
          f"samples dropped {error_handling['samples_dropped']}]")
    print(f"  real raw4: fixed {real_summary['train_best']} {100 * real_summary['single_exact']:.2f}%  "
          f"oracle {100 * real_summary['oracle_exact']:.2f}%  headroom {100 * real_summary['gain']:+.2f} pp "
          f"{fmt_interval(real_summary)}")
    print(f"  real raw4 oracle minus MEAN single channel ({100 * mean_single['single_exact']:.2f}%): "
          f"{100 * mean_single['gain']:+.2f} pp {fmt_interval(mean_single)}")
    delta = result["noise_free_mean_view_minus_i0"]
    if delta:
        print(f"  noise-free mean view minus I0: {100 * delta['delta_exact_a_minus_b']:+.2f} pp "
              f"[{100 * delta['ci95'][0]:+.2f}, {100 * delta['ci95'][1]:+.2f}]")
    for key, entry in doses.items():
        distance = entry.get("pixel_distance") or {}
        exch = entry["exchangeable"]
        null = exch["null"]
        contrast = exch["real_fixed_minus_null"]
        print(f"  {key}")
        print(f"    exchangeable  pair RMS {distance.get('pair_rms_median_gray', float('nan')):5.2f} "
              f"({distance.get('pair_vs_real_raw_pairs')})  single {100 * null['single_exact']:5.2f}%  "
              f"oracle {100 * null['oracle_exact']:5.2f}%  gain {100 * null['gain']:+.2f} {fmt_interval(null)}  "
              f"real-null {100 * contrast['delta_gain']:+.2f} {fmt_interval(contrast, 'ci95')}")
        clean = entry.get("clean_base")
        if clean:
            null = clean["null"]
            contrast = clean["real_fixed_minus_null"]
            print(f"    clean base    to-base RMS {distance.get('to_base_rms_median_gray', float('nan')):5.2f} "
                  f"({distance.get('to_base_vs_real_distances')})  base {100 * null['single_exact']:5.2f}%  "
                  f"oracle {100 * null['oracle_exact']:5.2f}%  gain {100 * null['gain']:+.2f} {fmt_interval(null)}  "
                  f"real-null {100 * contrast['delta_gain']:+.2f} {fmt_interval(contrast, 'ci95')}")
    if anchors:
        print("  anchors (I0-based clean-base null; real headroom "
              f"{100 * real_summary['gain']:+.2f} pp):")
        for name, anchor in anchors.items():
            print(f"    {name}: doses {anchor['doses']}")
            for key in anchor["entries"]:
                clean = doses[key]["clean_base"]
                gain, contrast = clean["null"], clean["real_fixed_minus_null"]
                print(f"      {key:9s} null gain {100 * gain['gain']:+.2f} {fmt_interval(gain)}  "
                      f"real-null {100 * contrast['delta_gain']:+.2f} {fmt_interval(contrast, 'ci95')}")


if __name__ == "__main__":
    main()
