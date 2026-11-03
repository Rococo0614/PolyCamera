"""Subprocess adapter for a pinned local Tesseract executable."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import csv
import subprocess

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class OCRPrediction:
    text: str
    confidence: float | None


def parse_tesseract_tsv(tsv: str) -> OCRPrediction:
    words: list[str] = []
    weighted_confidence = 0.0
    weight_sum = 0
    for row in csv.DictReader(tsv.splitlines(), delimiter="\t"):
        text = row.get("text", "").strip()
        if not text:
            continue
        try:
            confidence = float(row.get("conf", "-1"))
        except ValueError:
            confidence = -1.0
        words.append(text)
        if confidence >= 0:
            weight = max(1, len(text))
            weighted_confidence += weight * confidence / 100.0
            weight_sum += weight
    return OCRPrediction(
        text=" ".join(words),
        confidence=(weighted_confidence / weight_sum if weight_sum else None),
    )


class TesseractBackend:
    def __init__(
        self,
        *,
        executable: Path,
        tessdata_directory: Path | None = None,
        language: str = "eng",
        page_segmentation_mode: int = 7,
        allowlist: str | None = None,
    ) -> None:
        self.executable = Path(executable)
        if not self.executable.is_file():
            raise FileNotFoundError(self.executable)
        self.tessdata_directory = Path(tessdata_directory) if tessdata_directory else None
        self.language = language
        self.page_segmentation_mode = page_segmentation_mode
        self.allowlist = allowlist

    def recognize_gt_roi(self, image: np.ndarray) -> OCRPrediction:
        array = np.asarray(image)
        if array.ndim != 2:
            raise ValueError(f"GT ROI recognition expects grayscale HxW, got {array.shape}")
        stream = BytesIO()
        Image.fromarray(array.astype(np.uint8)).save(stream, format="PNG")
        command = [
            str(self.executable),
            "stdin",
            "stdout",
            "-l",
            self.language,
            "--psm",
            str(self.page_segmentation_mode),
        ]
        if self.tessdata_directory is not None:
            command.extend(["--tessdata-dir", str(self.tessdata_directory)])
        if self.allowlist is not None:
            command.extend(["-c", f"tessedit_char_whitelist={self.allowlist}"])
        command.append("tsv")
        result = subprocess.run(
            command,
            input=stream.getvalue(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return parse_tesseract_tsv(result.stdout.decode("utf-8", errors="replace"))
