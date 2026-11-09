"""Frozen offline-Gate-P sampling protocol shared by the OCR runners.

This reproduces, as importable and testable functions, the selection that the
first E0/E2 runs used inline: frozen document split, deterministic
"N regions per document" sampling via a seeded hash ordering, and the frozen
out-of-bounds exclusion list. Re-using it guarantees that new controls are
evaluated on exactly the same ROIs as the earlier results.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
import hashlib
import json
from pathlib import Path

from .shdocs_rois import SHDocsROI


def load_frozen_split(path: Path) -> tuple[dict[str, str], str, str]:
    """Return ``(assignments, split_version, assignment_sha256)``."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assignments = {str(key): str(value) for key, value in payload["assignments"].items()}
    return assignments, str(payload.get("split_version", "unknown")), str(
        payload.get("assignment_sha256", "")
    )


def load_excluded_sample_ids(path: Path) -> set[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(item) for item in payload.get("sample_ids", [])}


def limit_regions_per_document(
    rois: Sequence[SHDocsROI], limit: int, seed: int
) -> list[SHDocsROI]:
    """Keep the same ``limit`` regions of each document across all conditions.

    Regions are ranked by ``sha256(f"{seed}:{document}:{region}")`` exactly as in
    the first E0/E2 runs, so the chosen subset does not depend on shard count,
    process order or the set of conditions requested.
    """

    if limit <= 0:
        raise ValueError("limit must be positive")
    by_document: dict[str, list[SHDocsROI]] = defaultdict(list)
    for roi in rois:
        by_document[roi.document_id].append(roi)
    allowed: dict[str, set[int]] = {}
    for document, rows in by_document.items():
        ranked = sorted(
            {roi.region_index for roi in rows},
            key=lambda region: hashlib.sha256(f"{seed}:{document}:{region}".encode()).hexdigest(),
        )
        allowed[document] = set(ranked[:limit])
    return [roi for roi in rois if roi.region_index in allowed[roi.document_id]]


def drop_excluded(rois: Iterable[SHDocsROI], excluded: set[str]) -> list[SHDocsROI]:
    return [roi for roi in rois if roi.sample_id not in excluded]


def capture_key(roi: SHDocsROI) -> str:
    return f"{roi.document_id}|{roi.condition_id}"


def shard_of(roi: SHDocsROI, shards: int) -> int:
    """Stable shard index; all ROIs of one capture land in the same shard."""

    if shards <= 0:
        raise ValueError("shards must be positive")
    digest = hashlib.sha256(capture_key(roi).encode()).digest()
    return int.from_bytes(digest[:8], "little") % shards
