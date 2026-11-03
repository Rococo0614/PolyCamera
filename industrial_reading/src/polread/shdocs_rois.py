"""FUNSD-aligned SHDocs ROI discovery and representation loading."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from collections.abc import Sequence

import numpy as np
from PIL import Image

from .polarization import linear_stokes, representation_images, to_uint8, virtual_analyzer


@dataclass(frozen=True)
class SHDocsROI:
    sample_id: str
    document_id: str
    condition_id: str
    region_index: int
    ground_truth: str
    annotation_label: str
    box: tuple[int, int, int, int]
    capture_dir: Path


def discover_annotated_rois(
    images_root: Path,
    annotations_root: Path,
    *,
    conditions: Sequence[str] = tuple("abcdefghijklmno"),
) -> list[SHDocsROI]:
    """Discover aligned text ROIs without copying or modifying images."""

    images_root = Path(images_root)
    annotations_root = Path(annotations_root)
    rois: list[SHDocsROI] = []
    for annotation_path in sorted(annotations_root.glob("*.json")):
        document_id = annotation_path.stem
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        form = payload.get("form")
        if not isinstance(form, list):
            raise ValueError(f"Annotation has no form list: {annotation_path}")
        for condition in conditions:
            capture_id = document_id if condition == "camera" else f"{document_id}_{condition}"
            capture_dir = images_root / capture_id
            capture_major_exists = capture_dir.is_dir()
            method_major_exists = (images_root / "i0" / f"{capture_id}.png").is_file()
            if not (capture_major_exists or method_major_exists):
                continue
            for region_index, element in enumerate(form):
                text = str(element.get("text", ""))
                box = element.get("box")
                if not text or not isinstance(box, list) or len(box) != 4:
                    continue
                x0, y0, x1, y1 = (int(value) for value in box)
                if x1 <= x0 or y1 <= y0:
                    continue
                rois.append(
                    SHDocsROI(
                        sample_id=f"{document_id}_{condition}_{region_index}",
                        document_id=document_id,
                        condition_id=condition,
                        region_index=region_index,
                        ground_truth=text,
                        annotation_label=str(element.get("label", "unknown")),
                        box=(x0, y0, x1, y1),
                        capture_dir=capture_dir,
                    )
                )
    return rois


def _read_grayscale(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as image:
        return np.asarray(image.convert("L"))


def _representation_path(capture_dir: Path, method_id: str) -> Path:
    """Resolve both capture-major and SHDocs processed method-major layouts."""

    capture_major = capture_dir / f"{method_id}.png"
    if capture_major.is_file():
        return capture_major
    method_major = capture_dir.parent / method_id / f"{capture_dir.name}.png"
    if method_major.is_file():
        return method_major
    raise FileNotFoundError(
        f"Could not resolve {method_id} for capture reference {capture_dir}"
    )


def _load_fixed_channels(capture_dir: Path) -> dict[str, np.ndarray]:
    return {
        key: _read_grayscale(_representation_path(capture_dir, key))
        for key in ("i0", "i45", "i90", "i135")
    }


def load_representation(capture_dir: Path, method_id: str) -> np.ndarray:
    """Load or deterministically derive one SHDocs representation."""

    capture_dir = Path(capture_dir)
    if method_id in {"i0", "i45", "i90", "i135", "s0_norm", "deglared"}:
        return _read_grayscale(_representation_path(capture_dir, method_id))

    channels = _load_fixed_channels(capture_dir)
    if method_id in {"analytic_s0", "min", "median", "mean"}:
        key = "s0" if method_id == "analytic_s0" else method_id
        image = representation_images(channels)[key]
        return to_uint8(image, mode="clip")
    if method_id.startswith("virtual_"):
        try:
            angle = float(method_id.removeprefix("virtual_"))
        except ValueError as exc:
            raise ValueError(f"Invalid virtual angle method: {method_id}") from exc
        image = virtual_analyzer(linear_stokes(channels), angle)
        return to_uint8(image, mode="clip")
    raise ValueError(f"Unknown SHDocs representation: {method_id}")


def crop_roi(
    image: np.ndarray,
    box: tuple[int, int, int, int],
    *,
    buffer_pixels: int = 1,
    minimum_size: int = 32,
) -> np.ndarray:
    """Crop a GT ROI and pad it to a recognizer-safe minimum size."""

    if buffer_pixels < 0 or minimum_size <= 0:
        raise ValueError("buffer_pixels must be non-negative and minimum_size positive")
    array = np.asarray(image)
    if array.ndim != 2:
        raise ValueError(f"Expected grayscale HxW image, got {array.shape}")
    x0, y0, x1, y1 = box
    x0 = max(0, x0 - buffer_pixels)
    y0 = max(0, y0 - buffer_pixels)
    x1 = min(array.shape[1], x1 + buffer_pixels)
    y1 = min(array.shape[0], y1 + buffer_pixels)
    crop = array[y0:y1, x0:x1]
    if not crop.size:
        raise ValueError(f"Empty crop for box {box} in image {array.shape}")
    pad_y = max(0, minimum_size - crop.shape[0])
    pad_x = max(0, minimum_size - crop.shape[1])
    if pad_y or pad_x:
        crop = np.pad(
            crop,
            ((pad_y // 2, pad_y - pad_y // 2), (pad_x // 2, pad_x - pad_x // 2)),
            mode="edge",
        )
    return crop
