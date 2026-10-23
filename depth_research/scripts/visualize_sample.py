#!/usr/bin/env python3
"""Create a compact visual audit sheet for one aligned sample."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from poldepth.polarization import polarization_features, split_polar_quadrants


def load(path: str) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image)


def parse_named_path(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected NAME=PATH")
    return tuple(value.split("=", 1))  # type: ignore[return-value]


def turbo_like(values: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Small dependency-free blue/cyan/yellow/red map for values in [0, 1]."""

    x = np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4.0 * x - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * x - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * x - 1.0), 0.0, 1.0)
    rgb = (255.0 * np.stack((red, green, blue), axis=-1)).astype(np.uint8)
    if valid is not None:
        rgb[~valid] = 0
    return rgb


def depth_color(depth: np.ndarray, near: float, far: float) -> np.ndarray:
    valid = np.isfinite(depth) & (depth > 0)
    normalized = (np.asarray(depth, dtype=np.float64) - near) / max(far - near, 1e-8)
    return turbo_like(normalized, valid)


def error_color(prediction: np.ndarray, gt: np.ndarray, maximum: float) -> np.ndarray:
    valid = np.isfinite(gt) & (gt > 0) & np.isfinite(prediction) & (prediction > 0)
    error = np.abs(np.asarray(prediction, dtype=np.float64) - gt) / maximum
    rgb = turbo_like(error, valid)
    missing = (gt > 0) & ~(np.isfinite(prediction) & (prediction > 0))
    rgb[missing] = np.array([255, 0, 255], dtype=np.uint8)
    return rgb


def label_color(labels: np.ndarray) -> np.ndarray:
    ids = np.asarray(labels, dtype=np.uint32)
    return np.stack(
        ((ids * 37) % 255, (ids * 73) % 255, (ids * 109) % 255), axis=-1
    ).astype(np.uint8)


def rgb_image(array: np.ndarray) -> np.ndarray:
    if array.ndim == 2:
        return np.repeat(array[..., None], 3, axis=-1).astype(np.uint8)
    if array.shape[-1] >= 3:
        return array[..., :3].astype(np.uint8)
    raise ValueError(f"Unsupported RGB shape: {array.shape}")


def make_panel(array: np.ndarray, title: str, width: int) -> Image.Image:
    image = Image.fromarray(rgb_image(array))
    height = round(width * image.height / image.width)
    image = image.resize((width, height), Image.Resampling.BILINEAR)
    title_height = 28
    panel = Image.new("RGB", (width, height + title_height), "white")
    panel.paste(image, (0, title_height))
    draw = ImageDraw.Draw(panel)
    draw.text((8, 7), title, fill="black", font=ImageFont.load_default())
    return panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rgb", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--depth", action="append", type=parse_named_path, default=[])
    parser.add_argument("--polar", required=True)
    parser.add_argument("--label")
    parser.add_argument("--polar-order", default="0,45,90,135")
    parser.add_argument("--error-max-mm", type=float, default=300.0)
    parser.add_argument("--panel-width", type=int, default=420)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gt = load(args.gt).astype(np.float64).squeeze()
    valid_gt = gt[np.isfinite(gt) & (gt > 0)]
    if not valid_gt.size:
        raise ValueError("Ground-truth depth has no valid pixels")
    near, far = np.percentile(valid_gt, (1, 99))

    panels: list[tuple[np.ndarray, str]] = [
        (load(args.rgb), "RGB"),
        (depth_color(gt, float(near), float(far)), f"GT depth [{near:.0f}, {far:.0f}] mm"),
    ]
    for name, path in args.depth:
        prediction = load(path).astype(np.float64).squeeze()
        panels.append((depth_color(prediction, float(near), float(far)), f"{name} depth"))
        panels.append(
            (
                error_color(prediction, gt, args.error_max_mm),
                f"{name} abs error (magenta=missing)",
            )
        )

    composite = load(args.polar)
    order = tuple(item.strip() for item in args.polar_order.split(","))
    features = polarization_features(
        split_polar_quadrants(composite, order=order),
        saturation_value=float(np.iinfo(composite.dtype).max)
        if np.issubdtype(composite.dtype, np.integer)
        else None,
    )
    panels.extend(
        [
            (
                turbo_like(features["dolp"], features["valid"]),
                "DoLP (black=invalid; quadrant hypothesis)",
            ),
            (turbo_like(features["confidence"]), "Polar heuristic confidence"),
            (
                turbo_like(features["pair_residual"] / 0.25, features["valid"]),
                "Pair residual (black=invalid; 0.25=max)",
            ),
        ]
    )
    if args.label:
        panels.append((label_color(load(args.label).squeeze()), "Instance IDs"))

    rendered = [make_panel(array, title, args.panel_width) for array, title in panels]
    panel_height = max(panel.height for panel in rendered)
    rows = (len(rendered) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB", (args.columns * args.panel_width, rows * panel_height), (230, 230, 230)
    )
    for index, panel in enumerate(rendered):
        x = (index % args.columns) * args.panel_width
        y = (index // args.columns) * panel_height
        sheet.paste(panel, (x, y))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main()
