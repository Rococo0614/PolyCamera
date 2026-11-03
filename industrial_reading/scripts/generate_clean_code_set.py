#!/usr/bin/env python3
"""Generate a deterministic clean printed-code sanity set for Offline E0."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import string

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONTS = {
    "dejavu_mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "liberation_mono": "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "noto_mono": "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
}


def _token(rng: random.Random, length: int) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(length))


def _text(rng: random.Random, index: int) -> str:
    selector = index % 4
    if selector == 0:
        return f"LOT {_token(rng, 7)}"
    if selector == 1:
        return f"SN {_token(rng, 10)}"
    if selector == 2:
        year = rng.randint(2026, 2032)
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        return f"EXP {year:04d}-{month:02d}-{day:02d}"
    return f"BATCH {_token(rng, 6)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--font-sizes", default="24,32,48")
    args = parser.parse_args()
    sizes = tuple(int(value) for value in args.font_sizes.split(","))
    rng = random.Random(args.seed)
    texts = [_text(rng, index) for index in range(args.count)]

    image_root = args.output_root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | int]] = []
    for text_index, text in enumerate(texts):
        for font_id, font_path in DEFAULT_FONTS.items():
            if not Path(font_path).is_file():
                raise FileNotFoundError(font_path)
            for font_size in sizes:
                font = ImageFont.truetype(font_path, font_size)
                scratch = Image.new("L", (1, 1), 255)
                box = ImageDraw.Draw(scratch).textbbox((0, 0), text, font=font)
                width = box[2] - box[0]
                height = box[3] - box[1]
                image = Image.new("L", (width + 32, height + 24), 245)
                draw = ImageDraw.Draw(image)
                draw.text((16 - box[0], 12 - box[1]), text, font=font, fill=15)
                sample_id = f"code{text_index:04d}_{font_id}_h{font_size}"
                relative = Path("images") / f"{sample_id}.png"
                image.save(args.output_root / relative)
                rows.append(
                    {
                        "sample_id": sample_id,
                        "code_id": f"code{text_index:04d}",
                        "true_text": text,
                        "font_id": font_id,
                        "font_path": font_path,
                        "font_size": font_size,
                        "image_path": relative.as_posix(),
                    }
                )

    manifest = args.output_root / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    metadata = {
        "dataset": "synthetic-clean-code-v1",
        "proxy_only": True,
        "count_unique_strings": len(texts),
        "images": len(rows),
        "fonts": DEFAULT_FONTS,
        "font_sizes": sizes,
        "seed": args.seed,
        "manifest_sha256": manifest_sha,
        "claim_boundary": "Software/OCR sanity set with ordinary open system fonts; not a physical industrial spray-code dataset.",
    }
    (args.output_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
