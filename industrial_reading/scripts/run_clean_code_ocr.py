#!/usr/bin/env python3
"""Run one pinned OCR backend on the deterministic clean-code sanity set."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from polread.easyocr_backend import EasyOCRBackend
from polread.records import OCRRecord, write_jsonl
from polread.splits import grouped_split
from polread.tesseract_backend import TesseractBackend


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("easyocr", "tesseract"), required=True)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--allowlist")
    args = parser.parse_args()
    rows = list(csv.DictReader(args.manifest.open(encoding="utf-8")))
    assignments = grouped_split((row["code_id"] for row in rows), seed=20261103)
    if args.backend == "easyocr":
        backend = EasyOCRBackend(
            gpu=not args.cpu,
            model_storage_directory=Path("/home/chocbrownie0524/poldepth/cache/models/easyocr"),
            mode="gt-roi",
            allowlist=args.allowlist,
        )
        backend_id = "easyocr-1.7.2-gt-roi"
        recognize = backend.recognize
    else:
        backend = TesseractBackend(
            executable=Path("/home/chocbrownie0524/poldepth/tools/bin/tesseract"),
            tessdata_directory=Path("/home/chocbrownie0524/poldepth/tools/share/tessdata"),
            page_segmentation_mode=7,
            allowlist=args.allowlist,
        )
        backend_id = "tesseract-5.5.3-psm7"
        recognize = backend.recognize_gt_roi
    root = args.manifest.parent
    records: list[OCRRecord] = []
    for row in rows:
        with Image.open(root / row["image_path"]) as image:
            array = np.asarray(image.convert("L"))
        start = time.perf_counter()
        prediction = recognize(array)
        latency = (time.perf_counter() - start) * 1000.0
        records.append(
            OCRRecord(
                sample_id=row["sample_id"],
                group_id=row["code_id"],
                split=assignments[row["code_id"]],
                method_id="clean",
                ocr_backend=backend_id,
                ground_truth=row["true_text"],
                prediction=prediction.text,
                confidence=prediction.confidence,
                latency_ms=latency,
                condition_id=f"{row['font_id']}_h{row['font_size']}",
                annotation_label="synthetic_printed_code",
            )
        )
    write_jsonl(records, args.output)
    print(json.dumps({"records": len(records), "backend": backend_id}, indent=2))


if __name__ == "__main__":
    main()
