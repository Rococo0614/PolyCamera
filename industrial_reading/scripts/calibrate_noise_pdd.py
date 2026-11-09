#!/usr/bin/env python3
"""Calibrate Poisson-Gaussian sensor noise on PDD and place SHDocs relative to it.

1. For each PDD noise level (Low/Mid/High) fit ``var = a*x + b`` from the
   noise-free reference ``GT_*`` and the single noisy capture ``Test_*``.
2. Validate the blind redundancy estimator on PDD: it should recover the
   reference-based fit on ``Test`` and return ~0 noise on the noise-free ``GT``
   (that residual is the estimator's systematic floor).
3. Apply the blind estimator to SHDocs captures so the injected null-view noise
   can be compared with the noise already present in the proxy data.

The blind estimator measures variance in the redundancy-residual domain
(``(i0+i90-i45-i135)/2``). SHDocs channels are demosaicked SDK exports, so their
noise is spatially/cross-channel correlated and this is an effective level, not
a sensor datasheet value; the output says so explicitly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from polread.noise import estimate_noise_from_redundancy, fit_variance_model
from polread.pdd import discover_pdd_scenes, load_pdd_channels
from polread.polarization import ANGLE_KEYS
from polread.shdocs_rois import discover_annotated_rois, load_capture_channels

LEVELS = ("Low", "Mid", "High")
SIGMA_POINTS = (0.2, 0.5, 0.8)


def sigma_table(fit) -> dict[str, float]:
    return {f"{x:.1f}": 255.0 * fit.sigma(x) for x in SIGMA_POINTS}


def reference_fit(scenes, *, pixels_per_image: int, seed: int):
    rng = np.random.default_rng(seed)
    intensity: list[np.ndarray] = []
    residual: list[np.ndarray] = []
    for scene in scenes:
        reference = load_pdd_channels(scene, prefix="GT")
        noisy = load_pdd_channels(scene, prefix="Test")
        for key in ANGLE_KEYS:
            x = reference[key].ravel()
            r = (noisy[key] - reference[key]).ravel()
            valid = np.flatnonzero((x > 0.02) & (x < 0.98))  # clipping suppresses variance
            chosen = rng.choice(valid, size=min(pixels_per_image, valid.size), replace=False)
            intensity.append(x[chosen])
            residual.append(r[chosen])
    return fit_variance_model(
        np.concatenate(intensity),
        np.concatenate(residual),
        bins=16,
        minimum_bin_count=2000,
        robust=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdd-root", type=Path, required=True)
    parser.add_argument("--shdocs-images-root", type=Path, required=True)
    parser.add_argument("--shdocs-annotations-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True, help="a,b of the High level")
    parser.add_argument("--pixels-per-image", type=int, default=120_000)
    parser.add_argument("--shdocs-captures", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20261102)
    args = parser.parse_args()

    scenes_all = discover_pdd_scenes(args.pdd_root)
    levels: dict[str, object] = {}
    for level in LEVELS:
        scenes = [scene for scene in scenes_all if scene.noise_level == level]
        reference = reference_fit(scenes, pixels_per_image=args.pixels_per_image, seed=args.seed)
        blind_test = estimate_noise_from_redundancy(
            [load_pdd_channels(scene, prefix="Test") for scene in scenes],
            value_scale=1.0,
            bins=16,
            minimum_bin_count=2000,
        )
        blind_gt = estimate_noise_from_redundancy(
            [load_pdd_channels(scene, prefix="GT") for scene in scenes],
            value_scale=1.0,
            bins=16,
            minimum_bin_count=2000,
        )
        ref_sigma = sigma_table(reference)
        blind_sigma = sigma_table(blind_test)
        levels[level] = {
            "scenes": len(scenes),
            "reference_fit": reference.to_dict(),
            "sigma_gray_reference": ref_sigma,
            "blind_on_test_sigma_gray": blind_sigma,
            "blind_on_gt_sigma_gray_floor": sigma_table(blind_gt),
            "blind_over_reference_ratio": {
                key: blind_sigma[key] / ref_sigma[key] if ref_sigma[key] > 0 else None
                for key in ref_sigma
            },
        }
        print(
            f"{level}: ref sigma@0.5={ref_sigma['0.5']:.2f}  blind-on-test={blind_sigma['0.5']:.2f}  "
            f"blind-on-GT floor={levels[level]['blind_on_gt_sigma_gray_floor']['0.5']:.2f}",
            flush=True,
        )

    high = levels["High"]["reference_fit"]  # type: ignore[index]

    conditions = tuple(["camera"] + list("abcdefghijklmno"))
    rois = discover_annotated_rois(
        args.shdocs_images_root, args.shdocs_annotations_root, conditions=conditions
    )
    captures = sorted({(roi.document_id, roi.condition_id): roi.capture_dir for roi in rois}.items())
    step = max(1, len(captures) // args.shdocs_captures)
    picked = captures[::step][: args.shdocs_captures]
    channel_sets = [load_capture_channels(capture_dir) for _key, capture_dir in picked]

    def per_bin_sigma_gray(fit) -> list[float]:
        return [255.0 * float(np.sqrt(max(v, 0.0))) for v in fit.bin_variances]

    fit_plain = estimate_noise_from_redundancy(
        channel_sets, value_scale=255.0, bins=16, minimum_bin_count=2000, robust=False
    )
    fit_mad = estimate_noise_from_redundancy(
        channel_sets, value_scale=255.0, bins=16, minimum_bin_count=2000, robust=True
    )
    # Bins that carry most of the data; the extreme bins hold <1% of pixels each.
    heavy = [i for i, count in enumerate(fit_plain.bin_counts) if count >= 0.05 * max(fit_plain.bin_counts)]
    plain_sigma_at_half = float(
        np.interp(0.5, fit_plain.bin_centers, per_bin_sigma_gray(fit_plain))
    )
    high_sigma_at_half = 255.0 * float(np.sqrt(high["a"] * 0.5 + high["b"]))  # type: ignore[index]
    shdocs = {
        "captures_used": len(picked),
        "estimator": "blind redundancy residual (i0+i90-i45-i135)/2 on flat, unsaturated pixels",
        "plain_std": {
            "bin_centers": list(fit_plain.bin_centers),
            "bin_sigma_gray": per_bin_sigma_gray(fit_plain),
            "bin_counts": list(fit_plain.bin_counts),
            "sigma_gray_in_populated_range": [
                min(per_bin_sigma_gray(fit_plain)[i] for i in heavy),
                max(per_bin_sigma_gray(fit_plain)[i] for i in heavy),
            ],
            "interpretation": (
                "UPPER BOUND on sensor noise: includes the ~2% orthogonal-pair imbalance, "
                "demosaicking structure and 8-bit rounding."
            ),
        },
        "mad": {
            "bin_sigma_gray": per_bin_sigma_gray(fit_mad),
            "distinct_values": sorted({round(v, 3) for v in per_bin_sigma_gray(fit_mad)}),
            "interpretation": (
                "NOT RESOLVABLE: residuals of 8-bit data move in 0.5-gray steps, so the MAD-based "
                "sigma is quantized to multiples of 0.741 gray; shown only to document that limit."
            ),
        },
        "pdd_noise_free_gt_floor_sigma_gray": {
            level: levels[level]["blind_on_gt_sigma_gray_floor"]["0.5"] for level in LEVELS  # type: ignore[index]
        },
        "caveat": (
            "Effective level in the redundancy-residual domain of demosaicked 8-bit SDK exports; "
            "channel noise is correlated, so this is not a sensor-level noise figure."
        ),
        "plain_sigma_gray_at_x0.5_interpolated": plain_sigma_at_half,
        "pdd_high_sigma_gray_at_x0.5": high_sigma_at_half,
        "null_multiplier_upper_bound_for_shdocs": plain_sigma_at_half / high_sigma_at_half,
        "median_residual_gray": float(
            np.median(
                np.concatenate(
                    [
                        (0.5 * (c["i0"].astype(float) + c["i90"] - c["i45"] - c["i135"])).ravel()[::97]
                        for c in channel_sets
                    ]
                )
            )
        ),
    }
    print(
        f"SHDocs plain-std sigma in populated range = "
        f"{shdocs['plain_std']['sigma_gray_in_populated_range']}  "
        f"-> null multiplier upper bound {shdocs['null_multiplier_upper_bound_for_shdocs']:.3f}",
        flush=True,
    )
    payload = {
        "experiment": "offline-pdd-noise-calibration",
        "proxy_only": True,
        "claim_boundary": (
            "PDD is a different sensor (3-CCD camera + rotating polarizer) and contains no text. "
            "It supplies a measured noise-versus-intensity law, not SHDocs ground truth."
        ),
        "units": "variance in normalized [0,1] intensity; sigma in 8-bit gray levels",
        "pdd_levels": levels,
        "shdocs_blind_estimate": shdocs,
        "null_reference_model": {"source": "PDD High reference_fit", "a": high["a"], "b": high["b"]},
        "settings": {
            "pixels_per_image": args.pixels_per_image,
            "seed": args.seed,
            "pdd_valid_reference_range": [0.02, 0.98],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.model_output.write_text(
        json.dumps({"a": high["a"], "b": high["b"], "source": "PDD High reference_fit"}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
