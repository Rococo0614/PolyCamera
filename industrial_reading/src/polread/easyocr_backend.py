"""Thin optional EasyOCR adapter with explicit GT-ROI recognition mode."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class OCRPrediction:
    text: str
    confidence: float | None


class EasyOCRBackend:
    def __init__(
        self,
        *,
        languages: tuple[str, ...] = ("en",),
        gpu: bool = True,
        model_storage_directory: Path | None = None,
        mode: str = "gt-roi",
        allowlist: str | None = None,
    ) -> None:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("Install the optional 'ocr' dependencies to use EasyOCR") from exc
        kwargs: dict[str, Any] = {"gpu": gpu, "verbose": True}
        if model_storage_directory is not None:
            directory = Path(model_storage_directory)
            directory.mkdir(parents=True, exist_ok=True)
            kwargs["model_storage_directory"] = str(directory)
        self.reader = easyocr.Reader(list(languages), **kwargs)
        if mode not in {"gt-roi", "detect"}:
            raise ValueError(f"Unknown EasyOCR mode: {mode}")
        self.mode = mode
        self.allowlist = allowlist

    def recognize(self, image: np.ndarray) -> OCRPrediction:
        if self.mode == "detect":
            return self.recognize_detected_crop(image)
        return self.recognize_gt_roi(image)

    def recognize_gt_roi(self, image: np.ndarray) -> OCRPrediction:
        """Recognize one already-cropped ROI without rerunning text detection."""

        array = np.asarray(image)
        if array.ndim != 2:
            raise ValueError(f"GT ROI recognition expects grayscale HxW, got {array.shape}")
        height, width = array.shape
        results = self.reader.recognize(
            array,
            horizontal_list=[[0, width, 0, height]],
            free_list=[],
            detail=1,
            reformat=False,
            paragraph=False,
            allowlist=self.allowlist,
        )
        if not results:
            return OCRPrediction(text="", confidence=None)
        texts: list[str] = []
        weighted_confidence = 0.0
        weight_sum = 0
        for result in results:
            text = str(result[1])
            confidence = float(result[2])
            texts.append(text)
            weight = max(1, len(text))
            if math.isfinite(confidence):
                weighted_confidence += weight * confidence
                weight_sum += weight
        return OCRPrediction(
            text=" ".join(texts).strip(),
            confidence=(weighted_confidence / weight_sum if weight_sum else None),
        )

    def recognize_detected_crop(self, image: np.ndarray) -> OCRPrediction:
        """Run EasyOCR detection and recognition inside an already-cropped GT ROI."""

        array = np.asarray(image)
        if array.ndim != 2:
            raise ValueError(f"Crop detection expects grayscale HxW, got {array.shape}")
        results = self.reader.readtext(
            array,
            detail=1,
            paragraph=False,
            allowlist=self.allowlist,
        )
        if not results:
            return OCRPrediction(text="", confidence=None)
        results = sorted(
            results,
            key=lambda result: (
                min(point[1] for point in result[0]),
                min(point[0] for point in result[0]),
            ),
        )
        texts = [str(result[1]) for result in results]
        weights = [max(1, len(text)) for text in texts]
        confidences = [float(result[2]) for result in results]
        denominator = sum(weights)
        confidence = (
            sum(weight * score for weight, score in zip(weights, confidences, strict=True))
            / denominator
            if denominator
            else None
        )
        return OCRPrediction(text=" ".join(texts).strip(), confidence=confidence)
