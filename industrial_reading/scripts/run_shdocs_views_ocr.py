#!/usr/bin/env python3
"""Resumable, shardable GT-ROI OCR over computed views (dense angles, matched, null).

Unlike ``run_shdocs_ocr.py`` this script derives each view from the four raw
channel *crops* of one ROI (see ``polread.views``), so views such as
histogram-matched or noise-injected inputs, which depend on per-ROI statistics
or a seed, can be evaluated with the exact same ROI sampling, frozen split,
exclusion list and 4x bicubic preprocessing as the first E0/E2 runs.

Records use the shared ``OCRRecord`` JSONL schema. Different shards write
different files, so any number of processes can run in parallel.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from polread.noise import NoiseModel
from polread.polarization import ANGLE_KEYS
from polread.protocol import (
    drop_excluded,
    limit_regions_per_document,
    load_excluded_sample_ids,
    load_frozen_split,
    shard_of,
)
from polread.records import OCRRecord, read_jsonl
from polread.shdocs_rois import (
    SHDocsROI,
    crop_roi,
    discover_annotated_rois,
    load_capture_channels,
)
from polread.views import compute_view, virtual_angle_views


def build_backend(args: argparse.Namespace):
    if args.backend == "easyocr":
        from polread.easyocr_backend import EasyOCRBackend

        return (
            EasyOCRBackend(
                gpu=not args.cpu,
                model_storage_directory=args.easyocr_model_dir,
                mode="gt-roi",
            ),
            "easyocr-1.7.2-gt-roi",
        )
    from polread.tesseract_backend import TesseractBackend

    return (
        TesseractBackend(
            executable=args.tesseract_executable,
            tessdata_directory=args.tessdata_directory,
            page_segmentation_mode=args.tesseract_psm,
        ),
        f"tesseract-5.5.3-psm{args.tesseract_psm}",
    )


def expand_views(spec: str) -> list[str]:
    """Expand comma-separated view tokens; ``dense5`` is the 36-angle grid."""

    views: list[str] = []
    for token in (item.strip() for item in spec.split(",")):
        if not token:
            continue
        if token.startswith("dense"):
            views.extend(virtual_angle_views(int(token.removeprefix("dense"))))
        else:
            views.append(token)
    seen: set[str] = set()
    ordered = [view for view in views if not (view in seen or seen.add(view))]
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-root", type=Path, required=True)
    parser.add_argument("--annotations-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("easyocr", "tesseract"), required=True)
    parser.add_argument(
        "--views",
        required=True,
        help="Comma-separated view names; 'dense5' expands to virtual_0..virtual_175",
    )
    parser.add_argument("--conditions", default="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o")
    parser.add_argument("--limit-regions-per-document", type=int, default=10)
    parser.add_argument("--buffer-pixels", type=int, default=1)
    parser.add_argument("--scale-factor", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument("--noise-a", type=float)
    parser.add_argument("--noise-b", type=float)
    parser.add_argument("--noise-model-json", type=Path)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--only-split", choices=("train", "val", "test"))
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
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--easyocr-model-dir", type=Path)
    parser.add_argument("--tesseract-executable", type=Path)
    parser.add_argument("--tessdata-directory", type=Path)
    parser.add_argument("--tesseract-psm", type=int, default=7)
    parser.add_argument("--max-rois", type=int, help="Debug: stop after this many ROIs")
    args = parser.parse_args()

    if not 0 <= args.shard_index < args.shards:
        raise SystemExit("--shard-index must be in [0, --shards)")
    if args.scale_factor <= 0:
        raise SystemExit("--scale-factor must be positive")
    views = expand_views(args.views)
    if not views:
        raise SystemExit("No views requested")

    noise_model: NoiseModel | None = None
    if args.noise_model_json:
        payload = json.loads(args.noise_model_json.read_text(encoding="utf-8"))
        noise_model = NoiseModel(a=float(payload["a"]), b=float(payload["b"]))
    elif args.noise_a is not None and args.noise_b is not None:
        noise_model = NoiseModel(a=args.noise_a, b=args.noise_b)
    if any(view.startswith("null_") for view in views) and noise_model is None:
        raise SystemExit("null_* views need --noise-model-json or --noise-a/--noise-b")

    conditions = tuple(item.strip() for item in args.conditions.split(",") if item.strip())
    rois = discover_annotated_rois(args.images_root, args.annotations_root, conditions=conditions)
    assignments, split_version, split_hash = load_frozen_split(args.split_file)
    documents = {roi.document_id for roi in rois}
    if documents != set(assignments):
        raise SystemExit("Frozen split does not match the annotated documents")
    rois = limit_regions_per_document(rois, args.limit_regions_per_document, args.seed)
    rois = drop_excluded(rois, load_excluded_sample_ids(args.exclusions_file))
    if args.only_split:
        rois = [roi for roi in rois if assignments[roi.document_id] == args.only_split]
    rois = [roi for roi in rois if shard_of(roi, args.shards) == args.shard_index]
    if args.max_rois:
        rois = rois[: args.max_rois]

    backend, backend_id = build_backend(args)
    completed: set[tuple[str, str]] = set()
    if args.output.is_file():
        completed = {
            (record.sample_id, record.method_id)
            for record in read_jsonl(args.output)
            if record.ocr_backend == backend_id
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "experiment": "offline-shdocs-views-gt-roi",
        "proxy_only": True,
        "images_root": str(args.images_root.resolve()),
        "views": views,
        "conditions": list(conditions),
        "regions_per_document": args.limit_regions_per_document,
        "split_version": split_version,
        "split_assignment_sha256": split_hash,
        "ocr_backend": backend_id,
        "buffer_pixels": args.buffer_pixels,
        "scale_factor": args.scale_factor,
        "autocontrast": False,
        "seed": args.seed,
        "noise_model": None if noise_model is None else {"a": noise_model.a, "b": noise_model.b},
        "shard": [args.shard_index, args.shards],
        "only_split": args.only_split,
        "rois_in_shard": len(rois),
    }
    metadata["config_sha256"] = hashlib.sha256(
        json.dumps(metadata, sort_keys=True).encode()
    ).hexdigest()
    args.output.with_suffix(args.output.suffix + ".metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Group ROIs by capture so the four channel images are decoded once per capture.
    by_capture: dict[str, list[SHDocsROI]] = defaultdict(list)
    for roi in rois:
        by_capture[f"{roi.document_id}|{roi.condition_id}"].append(roi)

    started = time.time()
    done = skipped = 0
    with args.output.open("a", encoding="utf-8") as handle:
        for capture_rois in by_capture.values():
            images = load_capture_channels(capture_rois[0].capture_dir)
            for roi in capture_rois:
                crops = {
                    key: crop_roi(images[key], roi.box, buffer_pixels=args.buffer_pixels)
                    for key in ANGLE_KEYS
                }
                for view in views:
                    if (roi.sample_id, view) in completed:
                        skipped += 1
                        continue
                    status, error = "ok", ""
                    start = time.perf_counter()
                    try:
                        image = compute_view(
                            view, crops, sample_id=roi.sample_id, seed=args.seed,
                            noise_model=noise_model,
                        )
                        pil = Image.fromarray(image)
                        if args.scale_factor != 1.0:
                            size = (
                                max(1, int(round(pil.width * args.scale_factor))),
                                max(1, int(round(pil.height * args.scale_factor))),
                            )
                            pil = pil.resize(size, Image.Resampling.BICUBIC)
                        array = np.asarray(pil)
                        prediction = (
                            backend.recognize(array)
                            if args.backend == "easyocr"
                            else backend.recognize_gt_roi(array)
                        )
                    except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                        status, error = "error", f"{type(exc).__name__}: {exc}"
                        prediction = SimpleNamespace(text="", confidence=None)
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    record = OCRRecord(
                        sample_id=roi.sample_id,
                        group_id=roi.document_id,
                        split=assignments[roi.document_id],
                        method_id=view,
                        ocr_backend=backend_id,
                        ground_truth=roi.ground_truth,
                        prediction=prediction.text,
                        confidence=prediction.confidence,
                        latency_ms=latency_ms,
                        condition_id=roi.condition_id,
                        region_id=str(roi.region_index),
                        status=status,
                        error=error,
                        annotation_label=roi.annotation_label,
                    )
                    handle.write(
                        json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
                    )
                    handle.flush()
                    completed.add((roi.sample_id, view))
                    done += 1
                if done and done % 500 < len(views):
                    print(
                        f"[shard {args.shard_index}/{args.shards}] done={done} skipped={skipped} "
                        f"elapsed={time.time() - started:.0f}s",
                        flush=True,
                    )
    print(f"finished shard {args.shard_index}: wrote {done}, skipped {skipped}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
