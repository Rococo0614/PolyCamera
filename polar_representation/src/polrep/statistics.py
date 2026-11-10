"""Scene-aware summaries for strongly correlated capture stacks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Sequence

import numpy as np


def scene_summary(groups: Sequence[Hashable], values: np.ndarray) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(groups) != len(array) or not len(array):
        raise ValueError("Need one value and one group per non-empty sample")
    buckets: dict[Hashable, list[float]] = defaultdict(list)
    for group, value in zip(groups, array, strict=True):
        buckets[group].append(float(value))
    scene_means = np.array([np.mean(buckets[key]) for key in sorted(buckets, key=str)])
    return {
        "sample_micro": float(array.mean()),
        "scene_macro": float(scene_means.mean()),
        "samples": int(array.size),
        "scenes": int(scene_means.size),
    }


def scene_cluster_interval(
    groups: Sequence[Hashable],
    values: np.ndarray,
    *,
    iterations: int = 5000,
    seed: int = 20261110,
) -> list[float]:
    """Sample-weighted percentile interval with scenes as resampling units."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(groups) != len(array) or not len(array):
        raise ValueError("Need one value and one group per non-empty sample")
    buckets: dict[Hashable, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        buckets[group].append(index)
    packed = [array[np.asarray(buckets[key])] for key in sorted(buckets, key=str)]
    rng = np.random.default_rng(seed)
    output = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        picked = rng.integers(0, len(packed), size=len(packed))
        output[index] = np.concatenate([packed[item] for item in picked]).mean()
    return [float(x) for x in np.percentile(output, (2.5, 97.5))]


def summarize_with_interval(
    groups: Sequence[Hashable],
    values: np.ndarray,
    *,
    iterations: int = 5000,
    seed: int = 20261110,
) -> dict[str, object]:
    return {
        **scene_summary(groups, values),
        "scene_cluster_ci95": scene_cluster_interval(
            groups, values, iterations=iterations, seed=seed
        ),
    }
