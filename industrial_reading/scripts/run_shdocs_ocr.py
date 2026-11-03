#!/usr/bin/env python3
"""Resumable GT-ROI OCR inference over SHDocs representations."""

from __future__ import annotations

import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageOps

from polread.records import OCRRecord, read_jsonl
from polread.shdocs_rois import crop_roi, discover_annotated_rois, load_representation
from polread.splits import grouped_split


def _backend(args: argparse.Namespace):
    if args.backend == "easyocr":
        from polread.easyocr_backend import EasyOCRBackend

        return (
            EasyOCRBackend(
                gpu=not args.cpu,
                model_storage_directory=args.easyocr_model_dir,
                mode=args.easyocr_mode,
            ),
            f"easyocr-1.7.2-{args.easyocr_mode}",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-root", type=Path, required=True)
    parser.add_argument("--annotations-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("easyocr", "tesseract"), required=True)
    parser.add_argument("--methods", default="i0,i45,i90,i135,s0_norm,deglared,min,median")
    parser.add_argument("--conditions", default="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o")
    parser.add_argument("--limit-documents", type=int)
    parser.add_argument("--limit-regions-per-document", type=int)
    parser.add_argument("--buffer-pixels", type=int, default=1)
    parser.add_argument("--scale-factor", type=float, default=1.0)
    parser.add_argument("--autocontrast", action="store_true")
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
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument(
        "--easyocr-model-dir",
        type=Path,
        default=Path("/home/chocbrownie0524/poldepth/cache/models/easyocr"),
    )
    parser.add_argument("--easyocr-mode", choices=("gt-roi", "detect"), default="gt-roi")
    parser.add_argument(
        "--tesseract-executable",
        type=Path,
        default=Path("/home/chocbrownie0524/poldepth/tools/bin/tesseract"),
    )
    parser.add_argument(
        "--tessdata-directory",
        type=Path,
        default=Path("/home/chocbrownie0524/poldepth/tools/share/tessdata"),
    )
    parser.add_argument("--tesseract-psm", type=int, default=7)
    args = parser.parse_args()
    if args.scale_factor <= 0:
        raise SystemExit("--scale-factor must be positive")

    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    conditions = tuple(item.strip() for item in args.conditions.split(",") if item.strip())
    rois = discover_annotated_rois(
        args.images_root,
        args.annotations_root,
        conditions=conditions,
    )
    all_document_ids = sorted({roi.document_id for roi in rois})
    split_version = "generated"
    split_hash = ""
    if args.split_file and args.split_file.is_file():
        split_payload = json.loads(args.split_file.read_text(encoding="utf-8"))
        assignments = {str(key): str(value) for key, value in split_payload["assignments"].items()}
        missing = set(all_document_ids) - set(assignments)
        extra = set(assignments) - set(all_document_ids)
        if missing or extra:
            raise SystemExit(
                f"Frozen split does not match annotations; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        split_version = str(split_payload.get("split_version", "unknown"))
        split_hash = str(split_payload.get("assignment_sha256", ""))
    else:
        assignments = grouped_split(all_document_ids, seed=args.seed)
    selected_document_ids = all_document_ids
    if args.limit_documents is not None:
        selected_document_ids = all_document_ids[: args.limit_documents]
        selected = set(selected_document_ids)
        rois = [roi for roi in rois if roi.document_id in selected]
    if args.limit_regions_per_document is not None:
        by_document: dict[str, list] = defaultdict(list)
        for roi in rois:
            by_document[roi.document_id].append(roi)
        allowed_regions = {
            document: set(
                sorted(
                    {roi.region_index for roi in rows},
                    key=lambda region: hashlib.sha256(
                        f"{args.seed}:{document}:{region}".encode()
                    ).hexdigest(),
                )[: args.limit_regions_per_document]
            )
            for document, rows in by_document.items()
        }
        rois = [roi for roi in rois if roi.region_index in allowed_regions[roi.document_id]]
    excluded_samples: set[str] = set()
    if args.exclusions_file and args.exclusions_file.is_file():
        exclusion_payload = json.loads(args.exclusions_file.read_text(encoding="utf-8"))
        excluded_samples = {str(item) for item in exclusion_payload.get("sample_ids", [])}
        rois = [roi for roi in rois if roi.sample_id not in excluded_samples]

    backend, backend_id = _backend(args)

    @lru_cache(maxsize=max(16, len(methods) * 2))
    def cached_representation(capture_dir: str, method_id: str):
        return load_representation(Path(capture_dir), method_id)

    completed: set[tuple[str, str, str]] = set()
    if args.output.is_file():
        completed = {
            (record.sample_id, record.method_id, record.ocr_backend)
            for record in read_jsonl(args.output)
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output.with_suffix(args.output.suffix + ".metadata.json")
    metadata = {
        "experiment": "offline-shdocs-e0-e2-gt-roi",
        "proxy_only": True,
        "images_root": str(args.images_root.resolve()),
        "annotations_root": str(args.annotations_root.resolve()),
        "all_documents_for_split": len(all_document_ids),
        "selected_documents": len(selected_document_ids),
        "selected_rois": len(rois),
        "excluded_rois": len(excluded_samples),
        "methods": list(methods),
        "conditions": list(conditions),
        "split_seed": args.seed,
        "split_version": split_version,
        "split_assignment_sha256": split_hash,
        "ocr_backend": backend_id,
        "gpu": args.backend == "easyocr" and not args.cpu,
        "buffer_pixels": args.buffer_pixels,
        "scale_factor": args.scale_factor,
        "autocontrast": args.autocontrast,
    }
    canonical = json.dumps(metadata, sort_keys=True)
    metadata["config_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with args.output.open("a", encoding="utf-8") as handle:
        for roi in rois:
            for method_id in methods:
                key = (roi.sample_id, method_id, backend_id)
                if key in completed:
                    continue
                image = cached_representation(str(roi.capture_dir), method_id)
                crop = crop_roi(image, roi.box, buffer_pixels=args.buffer_pixels)
                pil_crop = Image.fromarray(crop.astype(np.uint8))
                if args.autocontrast:
                    pil_crop = ImageOps.autocontrast(pil_crop)
                if args.scale_factor != 1.0:
                    target = (
                        max(1, int(round(pil_crop.width * args.scale_factor))),
                        max(1, int(round(pil_crop.height * args.scale_factor))),
                    )
                    pil_crop = pil_crop.resize(target, Image.Resampling.BICUBIC)
                crop = np.asarray(pil_crop)
                start = time.perf_counter()
                status = "ok"
                error = ""
                try:
                    prediction = (
                        backend.recognize(crop)
                        if args.backend == "easyocr"
                        else backend.recognize_gt_roi(crop)
                    )
                except Exception as exc:
                    status = "error"
                    error = f"{type(exc).__name__}: {exc}"
                    prediction = SimpleNamespace(text="", confidence=None)
                latency_ms = (time.perf_counter() - start) * 1000.0
                record = OCRRecord(
                    sample_id=roi.sample_id,
                    group_id=roi.document_id,
                    split=assignments[roi.document_id],
                    method_id=method_id,
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
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                completed.add(key)


if __name__ == "__main__":
    main()
