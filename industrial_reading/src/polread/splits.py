"""Deterministic group-level splits that prevent repeated-capture leakage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib


def _score(group: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{group}".encode("utf-8")).hexdigest()


def grouped_split(
    groups: Iterable[str],
    *,
    train_fraction: float = 0.7,
    val_fraction: float = 0.15,
    seed: int = 20261102,
) -> dict[str, str]:
    """Assign each unique group to train/val/test with deterministic balancing."""

    if not (0.0 < train_fraction < 1.0 and 0.0 <= val_fraction < 1.0):
        raise ValueError("Invalid train/validation fractions")
    if train_fraction + val_fraction >= 1.0:
        raise ValueError("train_fraction + val_fraction must be less than one")
    unique = sorted({str(group) for group in groups}, key=lambda item: _score(item, seed))
    count = len(unique)
    if count < 3:
        raise ValueError("At least three unique groups are required")
    train_count = max(1, int(round(count * train_fraction)))
    val_count = max(1, int(round(count * val_fraction))) if val_fraction else 0
    if train_count + val_count >= count:
        train_count = max(1, count - val_count - 1)
    assignments: dict[str, str] = {}
    for index, group in enumerate(unique):
        if index < train_count:
            assignments[group] = "train"
        elif index < train_count + val_count:
            assignments[group] = "val"
        else:
            assignments[group] = "test"
    return assignments


def assert_group_isolation(
    sample_splits: Mapping[str, str], sample_groups: Mapping[str, str]
) -> None:
    observed: dict[str, set[str]] = {}
    for sample_id, split in sample_splits.items():
        group = sample_groups[sample_id]
        observed.setdefault(group, set()).add(split)
    leaking = {group: splits for group, splits in observed.items() if len(splits) > 1}
    if leaking:
        raise ValueError(f"Groups cross splits: {leaking}")
