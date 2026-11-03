"""Stable JSONL schema for OCR predictions independent of OCR backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class OCRRecord:
    sample_id: str
    group_id: str
    split: str
    method_id: str
    ocr_backend: str
    ground_truth: str
    prediction: str
    confidence: float | None = None
    latency_ms: float | None = None
    rejected: bool = False
    condition_id: str = ""
    region_id: str = ""
    status: str = "ok"
    error: str = ""
    annotation_label: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def read_jsonl(path: Path) -> list[OCRRecord]:
    records: list[OCRRecord] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                records.append(OCRRecord(**payload))
            except Exception as exc:
                raise ValueError(f"Invalid OCR record at line {line_number}: {exc}") from exc
    return records


def write_jsonl(records: Iterable[OCRRecord], path: Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
