#!/usr/bin/env python3
"""Condense the offline-extension summaries into one small, committed evidence file.

Inputs are the full summary JSONs written by the summarize_* scripts (kept outside the
repository because of size). The output keeps every number a statement in the docs rests
on, the exact pipeline settings, and SHA-256 of the full summaries, the per-run JSONL
records, the OCR-independent pixel-distance measurements and the source files that
produced them, so a reader can verify or regenerate any figure.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
import sys

DOSE_KEYS_I0 = ("i0_m0.25", "i0_m0.5", "i0_m0.75", "i0_m1", "i0_m1.5")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def interval(value: dict, key: str = "ci95") -> list[float]:
    return [float(value[key][0]), float(value[key][1])]


def condense_e3(full: dict) -> dict:
    sets = full["candidate_sets"]
    return {
        "scope": full["evaluation_scope"],
        "samples_evaluated": full["samples_evaluated"],
        "documents_evaluated": full["documents_evaluated"],
        "candidate_sets": {
            name: {
                key: summary[key]
                for key in ("train_best", "single_exact", "oracle_exact", "gain", "gain_ci95")
            }
            for name, summary in sets.items()
        },
        "headroom_difference_vs_raw4": {
            name: {"delta": value["delta_gain"], "ci95": interval(value)}
            for name, value in full["headroom_difference_vs_raw4"].items()
        },
        "fixed_i0_matched_minus_raw": {
            name: {"delta": value["delta_exact_a_minus_b"], "ci95": interval(value)}
            for name, value in full["fixed_i0_matched_minus_raw"].items()
        },
        "same_channel_outcome_agreement": {
            name: value["agreement"]
            for name, value in full["same_channel_outcome_agreement"].items()
        },
    }


def condense_null(full: dict) -> dict:
    doses = {}
    for key, entry in full["doses"].items():
        clean = entry.get("clean_base")
        exchangeable = entry["exchangeable"]
        doses[key] = {
            "base": entry["base"],
            "dose_multiplier_of_pdd_high": entry["dose_multiplier_of_pdd_high"],
            "pixel_distance": entry.get("pixel_distance"),
            "exchangeable": {
                "single_exact": exchangeable["null"]["single_exact"],
                "oracle_exact": exchangeable["null"]["oracle_exact"],
                "gain": exchangeable["null"]["gain"],
                "gain_ci95": exchangeable["null"]["gain_ci95"],
                "real_fixed_minus_null": {
                    "delta": exchangeable["real_fixed_minus_null"]["delta_gain"],
                    "ci95": interval(exchangeable["real_fixed_minus_null"]),
                },
                "real_oracle_minus_mean_single_minus_null": {
                    "delta": exchangeable["real_oracle_minus_mean_single_minus_null"]["delta_gain"],
                    "ci95": interval(exchangeable["real_oracle_minus_mean_single_minus_null"]),
                },
            },
        }
        if clean:
            doses[key]["clean_base"] = {
                "base_exact": clean["null"]["single_exact"],
                "oracle_exact": clean["null"]["oracle_exact"],
                "gain": clean["null"]["gain"],
                "gain_ci95": clean["null"]["gain_ci95"],
                "share_of_real_headroom": clean["null"]["gain"] / full["real_raw4"]["gain"],
                "real_fixed_minus_null": {
                    "delta": clean["real_fixed_minus_null"]["delta_gain"],
                    "ci95": interval(clean["real_fixed_minus_null"]),
                },
            }
    anchors = full.get("anchors")
    condensed_anchors = None
    if anchors:
        condensed_anchors = {}
        for name, value in anchors.items():
            entries = value["entries"]
            shares = [doses[entry]["clean_base"]["share_of_real_headroom"] for entry in entries]
            condensed_anchors[name] = {
                "criterion": value["criterion"],
                "doses": value["doses"],
                "entries": entries,
                "null_share_of_real_headroom": {"min": min(shares), "max": max(shares)},
                "real_minus_null_delta_range": [
                    min(doses[entry]["clean_base"]["real_fixed_minus_null"]["delta"] for entry in entries),
                    max(doses[entry]["clean_base"]["real_fixed_minus_null"]["delta"] for entry in entries),
                ],
                "real_minus_null_ci_includes_zero": [
                    doses[entry]["clean_base"]["real_fixed_minus_null"]["ci95"][0] <= 0.0
                    <= doses[entry]["clean_base"]["real_fixed_minus_null"]["ci95"][1]
                    for entry in entries
                ],
            }
    delta = full.get("noise_free_mean_view_minus_i0")
    return {
        "scope": full["evaluation_scope"],
        "samples_evaluated": full["samples_evaluated"],
        "documents_evaluated": full["documents_evaluated"],
        "error_handling": {
            key: full["error_handling"][key]
            for key in (
                "policy",
                "crashed_ocr_calls",
                "total_ocr_calls",
                "crashed_samples",
                "samples_dropped",
                "samples_with_a_crash_by_split",
                "crash_signatures",
            )
            if key in full["error_handling"]
        },
        "real_raw4": {
            key: full["real_raw4"][key]
            for key in ("train_best", "single_exact", "oracle_exact", "gain", "gain_ci95")
        },
        "real_raw4_oracle_minus_mean_single": {
            key: full["real_raw4_oracle_minus_mean_single"][key]
            for key in ("single_exact", "oracle_exact", "gain", "gain_ci95")
        },
        "real_pixel_distance_gray": full.get("real_pixel_distance_gray"),
        "noise_free_mean_view_minus_i0": (
            None
            if not delta
            else {"delta": delta["delta_exact_a_minus_b"], "ci95": interval(delta)}
        ),
        "anchors": condensed_anchors,
        "doses": doses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-dir", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--noise-model", type=Path, required=True)
    parser.add_argument("--noise-calibration", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summaries = args.summary_dir
    calibration = load(args.noise_calibration)
    backends = {"tesseract": "tesseract", "easyocr": "easyocr"}
    result: dict[str, object] = {
        "experiment": "offline-gate-p-extension-controls",
        "date": "2026-11-09",
        "proxy_only": True,
        "claim_boundary": (
            "SHDocs flat FUNSD documents with ground-truth text boxes and 8-bit SDK channel "
            "exports; virtual angles are synthesized from the four exported channels, noise is "
            "injected, not recorded. Nothing here is an industrial spray-code, curved-surface, "
            "polarized-source or dynamic-line result, and none of it opens the formal Gate 1."
        ),
        "protocol": {
            "split_version": "shdocs-document-v1",
            "documents": {"train": 35, "val": 8, "test": 7},
            "regions_per_document": 10,
            "conditions": "a-o (highlight); camera excluded from all headline numbers here",
            "preprocessing": "4x bicubic, no autocontrast",
            "normalization": "NFKC + uppercase + collapsed whitespace; no dictionary correction",
            "fixed_method_selection": "train split only",
            "reported_split": "test (7 documents, 1,034 ROI) unless the scope says all documents",
            "uncertainty": "document-cluster bootstrap, 95% percentile interval, 5,000 resamples",
            "seed": 20261102,
            "ocr_backends": {
                "tesseract": "Tesseract 5.5.3, PSM 7, eng, GT-ROI",
                "easyocr": "EasyOCR 1.7.2, GT-ROI recognizer",
            },
        },
        "noise_model": {
            **{k: v for k, v in load(args.noise_model).items() if k in ("a", "b", "source")},
            "form": "variance = a*x + b with x in [0,1]; sigma in 8-bit gray = 255*multiplier*sqrt(var)",
            "caveat": (
                "Calibrated on PDD High (a different sensor, no text). The blind redundancy "
                "estimate on SHDocs exports gives an effective level far below PDD High, so the "
                "doses are anchored on pixel distance to the real channels, not on sensor noise."
            ),
            "calibration_file": "noise_calibration_pdd_high.json",
            "pdd_high_sigma_gray_at_x0.5": calibration["shdocs_blind_estimate"]["pdd_high_sigma_gray_at_x0.5"],
            "shdocs_blind_sigma_gray_at_x0.5": calibration["shdocs_blind_estimate"][
                "plain_sigma_gray_at_x0.5_interpolated"
            ],
            "shdocs_multiplier_upper_bound_of_pdd_high": calibration["shdocs_blind_estimate"][
                "null_multiplier_upper_bound_for_shdocs"
            ],
        },
        "replication_of_first_round_e2": {},
        "dense_sweep_and_decomposition": {},
        "e3_intensity_matching": {},
        "noise_only_null": {},
        "artifacts": {},
    }

    files = {
        "dense_sweep": {b: summaries / f"dense_sweep_{b}.json" for b in backends},
        "decomposition": {b: summaries / f"decomposition_{b}.json" for b in backends},
        "e3_test": {b: summaries / f"e3_matching_{b}.json" for b in backends},
        "e3_all": {b: summaries / f"e3_matching_{b}_all_documents.json" for b in backends},
        "null_test": {b: summaries / f"noise_null_{b}.json" for b in backends},
        "null_all": {b: summaries / f"noise_null_{b}_all_documents.json" for b in backends},
    }
    null_drop = summaries / "noise_null_tesseract_drop_sensitivity.json"
    pixel_files = {
        "test": summaries / "view_difference_rms_test.json",
        "all": summaries / "view_difference_rms_all.json",
    }

    # The new runner re-derived the first-round raw-channel E2 from scratch; compare it against the
    # committed first-round evidence instead of asserting equality in prose.
    replication: dict[str, object] = {}
    first_round = {"tesseract": "e0_e2_shdocs_tesseract_scale4.json", "easyocr": "e0_e2_shdocs_easyocr_scale4.json"}
    for backend, filename in first_round.items():
        old = load(args.repository / "industrial_reading" / "evidence" / filename)["e2_highlight_test_all_labels"]
        new = load(files["e3_test"][backend])
        raw = new["candidate_sets"]["raw4"]
        differences = {
            "fixed_exact": abs(raw["single_exact"] - old["method_exact"][raw["train_best"]]),
            "oracle_exact": abs(raw["oracle_exact"] - old["four_angle_oracle_exact"]),
            "headroom": abs(raw["gain"] - old["oracle_minus_fixed_exact"]),
            "ci95_low": abs(raw["gain_ci95"][0] - old["cluster_bootstrap_ci95"][0]),
            "ci95_high": abs(raw["gain_ci95"][1] - old["cluster_bootstrap_ci95"][1]),
            "per_channel_exact": max(
                abs(new["exact_rate_evaluated"][key] - old["method_exact"][key]) for key in ("i0", "i45", "i90", "i135")
            ),
        }
        replication[backend] = {
            "first_round_file": filename,
            "same_train_best": raw["train_best"] == old["train_best_fixed"],
            "same_test_samples": new["samples_evaluated"] == old["samples"],
            "max_abs_difference_by_quantity": differences,
            "max_abs_difference_overall": max(differences.values()),
            "note": (
                "Raw-channel E2 re-derived end to end by the new runner and analysis code (same split, "
                "ROI sampling, exclusions, 4x bicubic, seeds, 5,000 bootstrap resamples) and compared "
                "against the committed first-round file; the intervals are only comparable because the "
                "resample count and seed are the same"
            ),
        }
    result["replication_of_first_round_e2"] = replication

    dense: dict[str, object] = {}
    for backend, path in files["dense_sweep"].items():
        full = load(path)["highlight_a_to_o"]
        decomposition = load(files["decomposition"][backend])
        spacing = decomposition["spacing_control"]["by_spacing_deg"]
        per_condition = decomposition["per_condition_best_angle"]
        dense[backend] = {
            "raw4": {k: full["raw4"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
            "virtual4_same_pipeline": {k: full["virtual4_same_pipeline"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
            "dense36": {k: full["dense36"][k] for k in ("train_best", "fixed_exact", "oracle_exact", "headroom", "headroom_ci95")},
            "dense_fixed_vs_raw_fixed": {k: full["dense_fixed_vs_raw_fixed"][k] for k in ("a", "b", "delta_exact_a_minus_b", "ci95")},
            "oracle4_vs_dense_fixed": full["oracle4_vs_dense_fixed"],
            "selection_ladder_headroom": {
                count: {"headroom": entry["headroom"], "oracle_exact": entry["oracle_exact"]}
                for count, entry in full["selection_ladder_evenly_spaced"].items()
            },
            "spacing_control_headroom_mean": {deg: value["headroom_mean"] for deg, value in sorted(spacing.items(), key=lambda item: int(item[0]))},
            "per_condition_fixed_minus_global_fixed": per_condition["per_condition_fixed_minus_global_fixed_test"],
            "distinct_train_best_angles": per_condition["distinct_train_best_angles"],
        }
    result["dense_sweep_and_decomposition"] = dense

    result["e3_intensity_matching"] = {
        scope: {backend: condense_e3(load(path)) for backend, path in group.items()}
        for scope, group in (("test", files["e3_test"]), ("all_documents", files["e3_all"]))
    }
    result["noise_only_null"] = {
        "test": {backend: condense_null(load(path)) for backend, path in files["null_test"].items()},
        "all_documents": {backend: condense_null(load(path)) for backend, path in files["null_all"].items()},
        "tesseract_crash_drop_sensitivity_test": condense_null(load(null_drop)),
    }

    artifacts: dict[str, object] = {"summaries_sha256": {}, "records": {}, "pixel_distance_sha256": {}, "source_sha256": {}}
    for group in files.values():
        for path in group.values():
            artifacts["summaries_sha256"][path.name] = sha256_of(path)
    artifacts["summaries_sha256"][null_drop.name] = sha256_of(null_drop)
    artifacts["summaries_sha256"][args.noise_calibration.name] = sha256_of(args.noise_calibration)
    for scope, path in pixel_files.items():
        artifacts["pixel_distance_sha256"][path.name] = sha256_of(path)
    for run in ("dense", "e3", "null", "null_i0_fine"):
        for backend in ("tess", "easy"):
            shard_files = sorted(Path(item) for item in glob.glob(str(args.runs_dir / run / f"{backend}_shard*.jsonl")))
            if not shard_files:
                continue
            rows = sum(1 for path in shard_files for _ in path.open("rb"))
            artifacts["records"][f"{run}/{backend}"] = {
                "shards": len(shard_files),
                "rows": rows,
                "sha256_per_shard": {path.name: sha256_of(path) for path in shard_files},
            }
    for relative in (
        "industrial_reading/src/polread/views.py",
        "industrial_reading/src/polread/noise.py",
        "industrial_reading/src/polread/protocol.py",
        "industrial_reading/src/polread/headroom.py",
        "industrial_reading/src/polread/analysis.py",
        "industrial_reading/scripts/run_shdocs_views_ocr.py",
        "industrial_reading/scripts/measure_view_differences.py",
        "industrial_reading/scripts/summarize_dense_sweep.py",
        "industrial_reading/scripts/analyze_dense_decomposition.py",
        "industrial_reading/scripts/summarize_e3_matching.py",
        "industrial_reading/scripts/summarize_noise_null.py",
        "industrial_reading/scripts/calibrate_noise_pdd.py",
    ):
        artifacts["source_sha256"][relative] = sha256_of(args.repository / relative)
    result["artifacts"] = artifacts

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
