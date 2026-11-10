"""PolaRGB release metadata, grouping and frozen scene splits.

The processed release has five PNGs per capture: four analyzer directions and an
unpolarized RGB reconstruction.  This module deliberately indexes the Hugging Face
metadata rather than inferring the paper split from directory names: the current
release and the paper describe different train/test scene counts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

KINDS = ("000", "045", "090", "135", "rgb")
ANGLE_KINDS = KINDS[:4]
CAPTURE_PATTERN = re.compile(
    r"^(train/(?:easy|hard)|test)/(input|gt)/(\d+)/(\d+)_(000|045|090|135|rgb)\.png$"
)


@dataclass(frozen=True)
class ReleaseFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CaptureGroup:
    subset: str
    side: str
    scene: str
    capture_id: str
    files: Mapping[str, ReleaseFile]

    @property
    def key(self) -> str:
        return f"{self.subset}/{self.side}/{self.scene}/{self.capture_id}"


def load_metadata(path: Path) -> dict[str, Any]:
    """Load one Hugging Face dataset metadata response."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def metadata_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def release_files(metadata: Mapping[str, Any]) -> dict[str, ReleaseFile]:
    """Return all LFS-backed files keyed by repository-relative path."""

    result: dict[str, ReleaseFile] = {}
    for entry in metadata.get("siblings", []):
        lfs = entry.get("lfs") or {}
        digest = lfs.get("sha256")
        size = entry.get("size")
        if digest is None or size is None:
            continue
        record = ReleaseFile(path=str(entry["rfilename"]), size=int(size), sha256=str(digest))
        result[record.path] = record
    return result


def capture_groups(metadata: Mapping[str, Any]) -> list[CaptureGroup]:
    """Group the five processed PNG representations of every capture."""

    grouped: dict[tuple[str, str, str, str], dict[str, ReleaseFile]] = {}
    for record in release_files(metadata).values():
        match = CAPTURE_PATTERN.match(record.path)
        if not match:
            continue
        subset, side, scene, capture_id, kind = match.groups()
        grouped.setdefault((subset, side, scene, capture_id), {})[kind] = record
    return [
        CaptureGroup(subset=subset, side=side, scene=scene, capture_id=capture_id, files=files)
        for (subset, side, scene, capture_id), files in sorted(grouped.items())
    ]


def validate_groups(groups: Iterable[CaptureGroup]) -> None:
    expected = set(KINDS)
    seen: set[str] = set()
    for group in groups:
        if group.key in seen:
            raise ValueError(f"Duplicate capture group: {group.key}")
        seen.add(group.key)
        actual = set(group.files)
        if actual != expected:
            raise ValueError(f"{group.key}: expected {sorted(expected)}, got {sorted(actual)}")


def _group_index(groups: Iterable[CaptureGroup]) -> dict[tuple[str, str, str, str], CaptureGroup]:
    return {(g.subset, g.side, g.scene, g.capture_id): g for g in groups}


def release_summary(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and summarize the current processed release."""

    groups = capture_groups(metadata)
    validate_groups(groups)
    files = release_files(metadata)
    by_subset: dict[str, dict[str, Any]] = {}
    for subset in ("train/easy", "train/hard", "test"):
        item: dict[str, Any] = {}
        for side in ("input", "gt"):
            selected = [g for g in groups if g.subset == subset and g.side == side]
            item[side] = {
                "groups": len(selected),
                "scenes": sorted({g.scene for g in selected}),
                "bytes": sum(record.size for group in selected for record in group.files.values()),
                "identical_045_090": sum(
                    group.files["045"].sha256 == group.files["090"].sha256 for group in selected
                ),
            }
        by_subset[subset] = item

    index = _group_index(groups)
    overlap = sorted(
        set(by_subset["train/easy"]["gt"]["scenes"])
        & set(by_subset["train/hard"]["gt"]["scenes"])
    )
    overlap_equal = 0
    for scene in overlap:
        easy = index[("train/easy", "gt", scene, "0000")]
        hard = index[("train/hard", "gt", scene, "0000")]
        if all(easy.files[kind].sha256 == hard.files[kind].sha256 for kind in KINDS):
            overlap_equal += 1

    train_scenes = sorted(
        set(by_subset["train/easy"]["input"]["scenes"])
        | set(by_subset["train/hard"]["input"]["scenes"])
    )
    test_scenes = by_subset["test"]["input"]["scenes"]
    train_gt_signatures = set()
    for scene in train_scenes:
        subset = "train/easy" if ("train/easy", "gt", scene, "0000") in index else "train/hard"
        group = index[(subset, "gt", scene, "0000")]
        train_gt_signatures.add(tuple(group.files[kind].sha256 for kind in KINDS))
    test_gt_signatures = {
        tuple(index[("test", "gt", scene, "0000")].files[kind].sha256 for kind in KINDS)
        for scene in test_scenes
    }
    return {
        "repository_revision": metadata.get("sha"),
        "last_modified": metadata.get("lastModified"),
        "license": (metadata.get("cardData") or {}).get("license"),
        "lfs_files": len(files),
        "lfs_bytes": sum(record.size for record in files.values()),
        "processed_capture_groups": len(groups),
        "subsets": by_subset,
        "train_scene_ids": train_scenes,
        "test_scene_ids": test_scenes,
        "unique_train_scenes": len(train_scenes),
        "unique_test_scenes": len(test_scenes),
        "overlapping_train_test_directory_labels": len(set(train_scenes) & set(test_scenes)),
        "exact_gt_signature_overlap_train_test": len(train_gt_signatures & test_gt_signatures),
        "overlapping_easy_hard_gt_scenes": len(overlap),
        "overlapping_easy_hard_gt_identical": overlap_equal,
        "input_captures": sum(g.side == "input" for g in groups),
    }


def frozen_scene_split(
    train_scene_ids: Iterable[str],
    test_scene_ids: Iterable[str],
    *,
    validation_scenes: int = 10,
    seed: int = 20261110,
) -> dict[str, Any]:
    """Create a deterministic scene-level fit/validation split.

    The release test scenes remain untouched.  Validation scenes are selected by a
    stable SHA-256 ranking so the result does not depend on Python hash randomization.
    """

    train = sorted(set(train_scene_ids))
    test = sorted(set(test_scene_ids))
    if not 0 < validation_scenes < len(train):
        raise ValueError("validation_scenes must be between 1 and len(train)-1")
    ranked = sorted(train, key=lambda scene: hashlib.sha256(f"{seed}:{scene}".encode()).hexdigest())
    validation = sorted(ranked[:validation_scenes])
    fit = sorted(set(train) - set(validation))
    return {
        "protocol": "polargb-release-scene-split-v1",
        "seed": seed,
        "fit": fit,
        "validation": validation,
        "test": test,
        "scene_id_namespaces": {
            "fit_validation": "release train/ scene directory",
            "test": "release test/ scene directory; numeric labels are not shared identities",
        },
        "counts": {"fit": len(fit), "validation": len(validation), "test": len(test)},
    }


def records_for_prefixes(
    metadata: Mapping[str, Any], prefixes: Iterable[str]
) -> list[ReleaseFile]:
    wanted = tuple(prefixes)
    return sorted(
        (record for record in release_files(metadata).values() if record.path.startswith(wanted)),
        key=lambda record: record.path,
    )


def local_file(root: Path, record: ReleaseFile) -> Path:
    return Path(root) / record.path
