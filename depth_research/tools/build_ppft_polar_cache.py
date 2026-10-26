#!/usr/bin/env python3
"""Build a compact PPFT-compatible polarization feature cache.

The public PPFT preprocessor saves full-resolution float64 ``[I, rho, phi]``
arrays and the loader then subsamples by four. That cache is about 146 GiB for
7,207 frames. This tool subsamples before the pointwise computation and stores
float32 by default, reducing the cache to about 4.6 GiB while preserving the
same spatial samples. Float32 quantization before periodic AoLP encoding can
change final inputs at roundoff scale; use raw preprocessing for a bit-level
author-path check. The PPFT loader must not subsample this cache again.
"""

from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image


def grayscale(rgb: np.ndarray, backend: str) -> np.ndarray:
    if backend == "opencv":
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("Install opencv-python or use --grayscale pillow") from exc
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)
    return np.asarray(Image.fromarray(rgb).convert("L"), dtype=np.float64)


def process_one(task: tuple[str, str, int, str, str]) -> tuple[str, int, str]:
    source_text, destination_text, downsample, dtype_name, gray_backend = task
    source, destination = Path(source_text), Path(destination_text)
    if destination.exists():
        return str(destination), destination.stat().st_size, "existing"

    with Image.open(source) as image:
        composite = np.asarray(image.convert("RGB"))
    height, width = composite.shape[:2]
    if height % 2 or width % 2:
        raise ValueError(f"Odd composite dimensions in {source}: {composite.shape}")
    gray = grayscale(composite, gray_backend)
    half_h, half_w = height // 2, width // 2
    i0 = gray[:half_h:downsample, :half_w:downsample] / 255.0
    i45 = gray[:half_h:downsample, half_w::downsample] / 255.0
    i90 = gray[half_h::downsample, :half_w:downsample] / 255.0
    i135 = gray[half_h::downsample, half_w::downsample] / 255.0

    intensity = 0.5 * (i0 + i45 + i90 + i135)
    q = i0 - i90
    u = i45 - i135
    # Match the public script's in-place substitutions exactly.  Substituted Q
    # participates in rho as well as phi, and substituted I is saved to disk.
    q[q == 0] = 1e-10
    intensity[intensity == 0] = 1e-10
    rho = np.clip(np.sqrt(np.square(q) + np.square(u)) / intensity, 0, 1)

    # Match the public PPFT preprocessing convention rather than changing the
    # checkpoint's expected representation.
    phi = 0.5 * np.arctan(u / q)
    phi[np.cos(2 * phi) * q < 0] += math.pi / 2
    phi = np.mod(phi + math.pi, math.pi)

    output = np.stack((intensity, rho, phi), axis=-1).astype(dtype_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    try:
        with temporary.open("wb") as file:
            np.save(file, output, allow_pickle=False)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return str(destination), destination.stat().st_size, "created"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True)
    parser.add_argument(
        "--output-root",
        help="Defaults to data root and creates <trajectory>/pol_processed",
    )
    parser.add_argument("--downsample", type=int, default=4)
    parser.add_argument("--dtype", choices=("float32", "float16"), default="float32")
    parser.add_argument("--grayscale", choices=("opencv", "pillow"), default="opencv")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.downsample < 1:
        raise SystemExit("--downsample must be >= 1")

    data_root = Path(args.data_root).resolve()
    output_root = Path(args.output_root).resolve() if args.output_root else data_root
    sources = sorted(data_root.glob("*/pol/*.png"))
    if not sources:
        # Also accept the original archive layout used by selective audit data.
        sources = sorted(data_root.glob("*/polarization/pol/*.png"))
    if not sources:
        raise SystemExit(f"No polarization PNGs under {data_root}/*/pol")

    tasks = []
    for source in sources:
        trajectory = (
            source.parent.parent.parent.name
            if source.parent.parent.name == "polarization"
            else source.parent.parent.name
        )
        destination = output_root / trajectory / "pol_processed" / f"{source.stem}.npy"
        tasks.append(
            (str(source), str(destination), args.downsample, args.dtype, args.grayscale)
        )

    created = existing = total_bytes = 0
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, (_, size, status) in enumerate(executor.map(process_one, tasks), start=1):
            total_bytes += size
            created += status == "created"
            existing += status == "existing"
            if index % 250 == 0:
                print(f"progress={index}/{len(tasks)}")

    metadata = {
        "frames": len(tasks),
        "created": created,
        "existing": existing,
        "downsample": args.downsample,
        "dtype": args.dtype,
        "grayscale": args.grayscale,
        "quadrant_order": ["0", "45", "90", "135"],
        "total_bytes": total_bytes,
    }
    metadata_path = output_root / "polar_cache_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(metadata_path)


if __name__ == "__main__":
    main()
