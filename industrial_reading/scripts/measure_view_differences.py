#!/usr/bin/env python3
"""Pixel-level distance between OCR input views, used to anchor the noise-null doses.

For every selected ROI the four SDK polarization channel crops are turned into
exactly the views the OCR runs use (``polread.views.compute_view``) and the RMS
difference (8-bit gray, native resolution, before the 4x bicubic resize) is
measured between

* the four raw channels (the real polarization differences),
* the histogram-/mean-std-matched views and their raw counterparts,
* noise-only null views (same view names and seeds as the OCR runs): one
  realization versus its base, and two independent realizations versus each other.

The point is to decide *before looking at any OCR result* which noise doses
perturb the pixels by about as much as the real inter-channel differences do.
The ROI selection (frozen split, regions per document, exclusions) is identical
to ``run_shdocs_views_ocr.py``.
"""

from __future__ import annotations

from collections import defaultdict
import argparse
import itertools
import json
from pathlib import Path
import sys

import numpy as np

from polread.noise import NoiseModel
from polread.polarization import ANGLE_KEYS
from polread.protocol import (
    drop_excluded,
    limit_regions_per_document,
    load_excluded_sample_ids,
    load_frozen_split,
)
from polread.shdocs_rois import crop_roi, discover_annotated_rois, load_capture_channels
from polread.views import compute_view, mean_view


def rms(first: np.ndarray, second: np.ndarray) -> float:
    delta = first.astype(np.float64) - second.astype(np.float64)
    return float(np.sqrt(np.mean(delta * delta)))


def describe(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "median": float(np.median(array)),
        "mean": float(array.mean()),
        "p10": float(np.percentile(array, 10)),
        "p90": float(np.percentile(array, 90)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-root", type=Path, required=True)
    parser.add_argument("--annotations-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--noise-model-json", type=Path, required=True)
    parser.add_argument("--conditions", default="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o")
    parser.add_argument("--only-split", choices=("train", "val", "test", "all"), default="test")
    parser.add_argument("--doses", default="0.25,0.5,1,2,4", help="doses for null_mean_*")
    parser.add_argument("--i0-doses", default="0.25,0.5,0.75,1,1.5", help="doses for null_i0_*")
    parser.add_argument("--limit-regions-per-document", type=int, default=10)
    parser.add_argument("--buffer-pixels", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument(
        "--split-file",
        type=Path,
        default=Path("industrial_reading/evidence/shdocs_document_split_v1.json"),
    )
    parser.add_argument(
        "--exclusions-file",
        type=Path,
        default=Path("industrial_reading/evidence/shdocs_excluded_rois_v1.json"),
    )
    args = parser.parse_args()

    payload = json.loads(args.noise_model_json.read_text(encoding="utf-8"))
    noise_model = NoiseModel(a=float(payload["a"]), b=float(payload["b"]))
    doses = [item.strip() for item in args.doses.split(",") if item.strip()]
    i0_doses = [item.strip() for item in args.i0_doses.split(",") if item.strip()]
    conditions = tuple(item.strip() for item in args.conditions.split(",") if item.strip())

    rois = discover_annotated_rois(args.images_root, args.annotations_root, conditions=conditions)
    assignments, split_version, split_hash = load_frozen_split(args.split_file)
    if {roi.document_id for roi in rois} != set(assignments):
        raise SystemExit("Frozen split does not match the annotated documents")
    rois = limit_regions_per_document(rois, args.limit_regions_per_document, args.seed)
    rois = drop_excluded(rois, load_excluded_sample_ids(args.exclusions_file))
    if args.only_split != "all":
        rois = [roi for roi in rois if assignments[roi.document_id] == args.only_split]

    by_capture = defaultdict(list)
    for roi in rois:
        by_capture[f"{roi.document_id}|{roi.condition_id}"].append(roi)

    samples: dict[str, list[float]] = defaultdict(list)
    brightness: list[float] = []
    for capture_rois in by_capture.values():
        images = load_capture_channels(capture_rois[0].capture_dir)
        for roi in capture_rois:
            crops = {
                key: crop_roi(images[key], roi.box, buffer_pixels=args.buffer_pixels)
                for key in ANGLE_KEYS
            }
            base_mean = mean_view(crops)
            brightness.append(float(base_mean.mean()))
            for first, second in itertools.combinations(ANGLE_KEYS, 2):
                samples[f"raw:{first}-{second}"].append(rms(crops[first], crops[second]))
            for key in ANGLE_KEYS:
                samples[f"raw:{key}-mean"].append(rms(crops[key], base_mean))

            def view(name: str) -> np.ndarray:
                return compute_view(
                    name, crops, sample_id=roi.sample_id, seed=args.seed, noise_model=noise_model
                )

            for family in ("hm", "ms"):
                matched = {key: view(f"{family}_{key}") for key in ANGLE_KEYS}
                for key in ANGLE_KEYS:
                    samples[f"{family}:{key}-raw"].append(rms(matched[key], crops[key]))
                for first, second in itertools.combinations(ANGLE_KEYS, 2):
                    samples[f"{family}:{first}-{second}"].append(rms(matched[first], matched[second]))
            for dose in doses:
                first_view = view(f"null_mean_m{dose}_k0")
                second_view = view(f"null_mean_m{dose}_k1")
                samples[f"null_mean_m{dose}:k0-base"].append(rms(first_view, base_mean))
                samples[f"null_mean_m{dose}:k0-k1"].append(rms(first_view, second_view))
            for dose in i0_doses:
                first_view = view(f"null_i0_m{dose}_k0")
                second_view = view(f"null_i0_m{dose}_k1")
                samples[f"null_i0_m{dose}:k0-base"].append(rms(first_view, crops["i0"]))
                samples[f"null_i0_m{dose}:k0-k1"].append(rms(first_view, second_view))

    result = {
        "experiment": "offline-view-difference-rms",
        "proxy_only": True,
        "unit": "RMS difference in 8-bit gray levels, native crop resolution, before 4x bicubic",
        "split": args.only_split,
        "split_version": split_version,
        "split_assignment_sha256": split_hash,
        "rois": len(brightness),
        "captures": len(by_capture),
        "noise_model": {"a": noise_model.a, "b": noise_model.b},
        "seed": args.seed,
        "median_roi_mean_gray": float(np.median(brightness)),
        "pairs": {name: describe(values) for name, values in sorted(samples.items())},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"rois={result['rois']} captures={result['captures']} median ROI gray={result['median_roi_mean_gray']:.1f}")
    for name in sorted(result["pairs"]):
        stats = result["pairs"][name]
        print(f"{name:28s} median {stats['median']:6.2f}  mean {stats['mean']:6.2f}  p10 {stats['p10']:6.2f}  p90 {stats['p90']:6.2f}")


if __name__ == "__main__":
    sys.exit(main())
