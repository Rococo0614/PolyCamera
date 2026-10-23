#!/usr/bin/env python3
"""Create an RGB contact sheet with one highlighted label per panel."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load(path: str) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rgb", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--panel-width", type=int, default=360)
    parser.add_argument("--columns", type=int, default=3)
    args = parser.parse_args()

    rgb = load(args.rgb)
    labels = load(args.label).squeeze()
    if rgb.shape[:2] != labels.shape:
        raise ValueError(f"RGB {rgb.shape[:2]} and labels {labels.shape} do not align")
    if rgb.ndim != 3 or rgb.shape[-1] < 3:
        raise ValueError(f"Expected RGB image, got {rgb.shape}")
    rgb = rgb[..., :3].astype(np.uint8)

    panels: list[Image.Image] = []
    font = ImageFont.load_default()
    for label_id in np.unique(labels):
        mask = labels == label_id
        highlighted = (rgb.astype(np.float32) * 0.15).astype(np.uint8)
        highlighted[mask] = rgb[mask]
        image = Image.fromarray(highlighted)
        panel_height = round(args.panel_width * image.height / image.width)
        image = image.resize((args.panel_width, panel_height), Image.Resampling.BILINEAR)
        title_height = 28
        panel = Image.new("RGB", (args.panel_width, panel_height + title_height), "white")
        panel.paste(image, (0, title_height))
        ImageDraw.Draw(panel).text(
            (8, 7),
            f"label={int(label_id)} pixels={int(mask.sum())}",
            fill="black",
            font=font,
        )
        panels.append(panel)

    panel_height = max(panel.height for panel in panels)
    rows = (len(panels) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB", (args.columns * args.panel_width, rows * panel_height), (230, 230, 230)
    )
    for index, panel in enumerate(panels):
        sheet.paste(
            panel,
            ((index % args.columns) * args.panel_width, (index // args.columns) * panel_height),
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main()
