#!/usr/bin/env python3
"""Run P3 analytical layer-separation and failure-boundary sweeps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from polrep.physics import fresnel_reflection_unpolarized
from polrep.simulation import SimulationConfig, score_simulation, simulate


def heat_color(value: float, lower: float, upper: float) -> tuple[int, int, int]:
    scaled = float(np.clip((value - lower) / max(upper - lower, 1e-9), 0.0, 1.0))
    return (int(220 * (1 - scaled) + 35 * scaled), int(55 * (1 - scaled) + 160 * scaled), 80)


def write_heatmap(path: Path, matrix: np.ndarray, rows: list[str], columns: list[str], title: str) -> None:
    cell, left, top = 88, 150, 70
    image = Image.new("RGB", (left + cell * len(columns), top + cell * len(rows)), "white")
    draw = ImageDraw.Draw(image)
    lower, upper = float(np.percentile(matrix, 5)), float(np.percentile(matrix, 95))
    draw.text((8, 8), title, fill="black")
    for column, label in enumerate(columns):
        draw.text((left + column * cell + 5, 42), label, fill="black")
    for row, label in enumerate(rows):
        draw.text((5, top + row * cell + 30), label, fill="black")
        for column in range(len(columns)):
            value = float(matrix[row, column])
            x, y = left + column * cell, top + row * cell
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=heat_color(value, lower, upper))
            draw.text((x + 7, y + 32), f"{value:+.1f}", fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-dir", type=Path, required=True)
    args = parser.parse_args()

    ratios = [0.1, 0.25, 0.5, 1.0, 1.5]
    reflection_dolps = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]
    transmission_dolps = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9]
    ambiguity_ratios = [0.05, 0.1, 0.25, 0.5, 0.75, 1.5]
    angle_differences = [0.0, 15.0, 30.0, 45.0, 60.0, 90.0]
    noise_levels = [0.0, 0.005, 0.01, 0.02, 0.04]

    main_rows = []
    main_matrix = np.empty((len(reflection_dolps), len(ratios)))
    for row, dolp in enumerate(reflection_dolps):
        for column, ratio in enumerate(ratios):
            config = SimulationConfig(reflection_ratio=ratio, reflection_dolp=dolp)
            score = score_simulation(simulate(config))
            main_rows.append({"config": config.__dict__, "score": score})
            main_matrix[row, column] = score["virtual_min_gain_db"]

    ambiguity_rows = []
    ambiguity_matrix = np.empty((len(transmission_dolps), len(ambiguity_ratios)))
    for row, transmission_dolp in enumerate(transmission_dolps):
        for column, ratio in enumerate(ambiguity_ratios):
            config = SimulationConfig(
                reflection_ratio=ratio,
                reflection_dolp=0.75,
                transmission_dolp=transmission_dolp,
                aolp_difference_deg=45.0,
            )
            score = score_simulation(simulate(config))
            ambiguity_rows.append({"config": config.__dict__, "score": score})
            ambiguity_matrix[row, column] = score["virtual_min_gain_db"]

    angle_rows = []
    for difference in angle_differences:
        config = SimulationConfig(
            reflection_ratio=0.5,
            reflection_dolp=0.75,
            transmission_dolp=0.6,
            aolp_difference_deg=difference,
        )
        angle_rows.append({"config": config.__dict__, "score": score_simulation(simulate(config))})

    noise_rows = []
    for noise in noise_levels:
        config = SimulationConfig(
            reflection_ratio=0.1,
            reflection_dolp=0.75,
            noise_sigma=noise,
        )
        noise_rows.append({"config": config.__dict__, "score": score_simulation(simulate(config))})

    instrument_rows = []
    for label, updates in (
        ("ideal", {}),
        ("gain_offset", {"gains": (1.03, 0.97, 1.02, 0.98), "offsets": (0.005, -0.003, 0.002, 0.0)}),
        ("angle_error", {"angle_error_deg": (1.3, -1.2, 1.1, 1.7)}),
        ("mpfa_bilinear", {"mpfa_bilinear": True}),
    ):
        config = SimulationConfig(
            reflection_ratio=0.05,
            reflection_dolp=0.75,
            **updates,
        )
        instrument_rows.append({"label": label, "config": config.__dict__, "score": score_simulation(simulate(config))})

    incidence_angles = [0.0, 15.0, 30.0, 45.0, 55.0, float(np.rad2deg(np.arctan(1.5))), 65.0, 75.0, 80.0]
    fresnel_rows = []
    for incidence in incidence_angles:
        fresnel = fresnel_reflection_unpolarized(incidence)
        config = SimulationConfig(
            reflection_ratio=0.25,
            reflection_dolp=float(fresnel["reflected_dolp"]),
        )
        fresnel_rows.append(
            {
                "incidence_deg": incidence,
                "mean_reflectance": float(fresnel["mean_reflectance"]),
                "reflected_dolp": float(fresnel["reflected_dolp"]),
                "fixed_observed_reflection_ratio": 0.25,
                "score": score_simulation(simulate(config)),
            }
        )

    write_heatmap(
        args.image_dir / "virtual_min_gain_reflection_sweep.png",
        main_matrix,
        [f"DoLP_R={x:g}" for x in reflection_dolps],
        [f"R/T={x:g}" for x in ratios],
        "virtual_min minus RGB PSNR (dB): unpolarized transmission",
    )
    write_heatmap(
        args.image_dir / "virtual_min_gain_ambiguity_sweep.png",
        ambiguity_matrix,
        [f"DoLP_T={x:g}" for x in transmission_dolps],
        [f"R/T={x:g}" for x in ambiguity_ratios],
        "virtual_min minus RGB PSNR (dB): polarized transmission failure boundary",
    )

    result = {
        "experiment": "p3-analytical-polarization-layer-sweep-v1",
        "reflection_sweep": main_rows,
        "transmission_ambiguity_sweep": ambiguity_rows,
        "aolp_difference_sweep": angle_rows,
        "noise_sweep": noise_rows,
        "instrument_and_mpfa_sweep": instrument_rows,
        "fresnel_incidence_sweep": fresnel_rows,
        "summary": {
            "positive_gain_threshold_db": 0.1,
            "reflection_sweep_positive_share_gt_0p1db": float(np.mean(main_matrix > 0.1)),
            "reflection_sweep_gain_range_db": [float(main_matrix.min()), float(main_matrix.max())],
            "ambiguity_sweep_positive_share_gt_0p1db": float(np.mean(ambiguity_matrix > 0.1)),
            "ambiguity_sweep_gain_range_db": [float(ambiguity_matrix.min()), float(ambiguity_matrix.max())],
        },
        "claim_boundary": (
            "Analytical grayscale Stokes layer simulation. It establishes implementation sanity and "
            "identifiability trends, not real-camera performance or uniqueness of layer separation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"wrote {args.output} and {args.image_dir}")


if __name__ == "__main__":
    main()
