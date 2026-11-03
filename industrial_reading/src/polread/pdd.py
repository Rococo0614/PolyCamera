"""PDD 2025 PNG inventory and channel loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PDDScene:
    noise_level: str
    scene_id: str
    directory: Path


def discover_pdd_scenes(root: Path) -> list[PDDScene]:
    root = Path(root)
    scenes: list[PDDScene] = []
    for level_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for scene_dir in sorted(path for path in level_dir.iterdir() if path.is_dir()):
            expected = {
                scene_dir / f"{prefix}_{angle}.png"
                for prefix in ("GT", "Test")
                for angle in (0, 45, 90, 135)
            }
            if all(path.is_file() for path in expected):
                scenes.append(
                    PDDScene(
                        noise_level=level_dir.name,
                        scene_id=scene_dir.name,
                        directory=scene_dir,
                    )
                )
    return scenes


def load_pdd_channels(
    scene: PDDScene,
    *,
    prefix: str,
    color_channel: int = 1,
) -> dict[str, np.ndarray]:
    if prefix not in {"GT", "Test"}:
        raise ValueError("prefix must be GT or Test")
    channels: dict[str, np.ndarray] = {}
    for angle in (0, 45, 90, 135):
        path = scene.directory / f"{prefix}_{angle}.png"
        with Image.open(path) as image:
            array = np.asarray(image)
        if array.ndim != 3 or array.shape[2] <= color_channel:
            raise ValueError(f"Expected RGB image at {path}, got {array.shape}")
        channels[f"i{angle}"] = array[..., color_channel].astype(np.float64) / 255.0
    return channels
