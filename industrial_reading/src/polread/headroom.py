"""Vectorized success-matrix analysis for fixed-vs-adaptive headroom controls.

Everything operates on a boolean success matrix ``S[sample, method]`` (exact
read of that OCR input) plus a ``group`` label per sample (document) so that
uncertainty accounts for the repeated captures of one document.

Core definitions (all selection of a "fixed" method uses the *train* split only;
all reported numbers use the *test* split only):

``fixed``
    ``argmax_method mean(S[train, method])`` among a candidate set, evaluated on test.
``oracle``
    ``mean(any(S[test, candidates], axis=1))`` -- per-sample best, not deployable.
``headroom``
    ``oracle - fixed`` for the *same* candidate set. Comparing headrooms of two
    candidate sets of different size is only meaningful together with a
    matched-null reference, which :func:`selection_floor` provides.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from .records import OCRRecord
from .text_metrics import TextNormalization, evaluate_text


@dataclass(frozen=True)
class SuccessMatrix:
    sample_ids: tuple[str, ...]
    groups: tuple[str, ...]
    splits: tuple[str, ...]
    conditions: tuple[str, ...]
    methods: tuple[str, ...]
    success: np.ndarray  # bool [samples, methods]
    cer: np.ndarray  # float [samples, methods]

    def column(self, method: str) -> np.ndarray:
        return self.success[:, self.methods.index(method)]

    def split_mask(self, split: str) -> np.ndarray:
        return np.asarray([item == split for item in self.splits])

    def condition_mask(self, conditions: Iterable[str] | None) -> np.ndarray:
        if conditions is None:
            return np.ones(len(self.sample_ids), dtype=bool)
        allowed = set(conditions)
        return np.asarray([item in allowed for item in self.conditions])


def build_success_matrix(
    records: Iterable[OCRRecord],
    methods: Sequence[str],
    *,
    normalization: TextNormalization | None = None,
    errors_as_failures: bool = False,
) -> SuccessMatrix:
    """Pivot OCR records; only samples observed for *every* method are kept.

    Records whose ``status`` is not ``"ok"`` (e.g. an OCR engine crash) are skipped,
    which makes their sample incomplete and drops it. With
    ``errors_as_failures=True`` they are instead kept as failed reads (empty
    prediction, exact-read false, CER 1), the same as a rejected read; callers
    that use this must report how many records were affected.
    """

    cfg = normalization or TextNormalization()
    wanted = set(methods)
    table: dict[str, dict[str, tuple[bool, float]]] = defaultdict(dict)
    meta: dict[str, tuple[str, str, str]] = {}
    for record in records:
        if record.method_id not in wanted:
            continue
        failed = record.status != "ok"
        if failed and not errors_as_failures:
            continue
        metrics = evaluate_text(
            record.ground_truth,
            "" if (record.rejected or failed) else record.prediction,
            normalization=cfg,
        )
        table[record.sample_id][record.method_id] = (
            bool(metrics["normalized_exact_read"]),
            float(metrics["cer"]),
        )
        meta[record.sample_id] = (record.group_id, record.split, record.condition_id)
    complete = sorted(sample for sample, row in table.items() if set(row) == wanted)
    ordered = tuple(methods)
    success = np.zeros((len(complete), len(ordered)), dtype=bool)
    cer = np.zeros((len(complete), len(ordered)), dtype=np.float64)
    for row_index, sample in enumerate(complete):
        for column_index, method in enumerate(ordered):
            success[row_index, column_index], cer[row_index, column_index] = table[sample][method]
    return SuccessMatrix(
        sample_ids=tuple(complete),
        groups=tuple(meta[sample][0] for sample in complete),
        splits=tuple(meta[sample][1] for sample in complete),
        conditions=tuple(meta[sample][2] for sample in complete),
        methods=ordered,
        success=success,
        cer=cer,
    )


def train_best(matrix: SuccessMatrix, candidates: Sequence[str], *, rows: np.ndarray) -> str:
    """Candidate with the highest train exact rate; ties -> lower mean CER -> name."""

    train = rows & matrix.split_mask("train")
    if not train.any():
        raise ValueError("No train samples in the requested rows")
    columns = [matrix.methods.index(name) for name in candidates]
    exact = matrix.success[train][:, columns].mean(axis=0)
    cer = matrix.cer[train][:, columns].mean(axis=0)
    order = sorted(range(len(columns)), key=lambda i: (-exact[i], cer[i], candidates[i]))
    return candidates[order[0]]


def fixed_and_oracle(
    matrix: SuccessMatrix,
    candidates: Sequence[str],
    *,
    rows: np.ndarray,
    split: str = "test",
) -> dict[str, object]:
    chosen = train_best(matrix, candidates, rows=rows)
    test = rows & matrix.split_mask(split)
    columns = [matrix.methods.index(name) for name in candidates]
    fixed = matrix.column(chosen)[test].mean()
    oracle = matrix.success[test][:, columns].any(axis=1).mean()
    return {
        "candidates": len(candidates),
        "train_best": chosen,
        "samples": int(test.sum()),
        "fixed_exact": float(fixed),
        "oracle_exact": float(oracle),
        "headroom": float(oracle - fixed),
    }


def cluster_bootstrap(
    values_by_group: dict[str, np.ndarray],
    statistic,
    *,
    iterations: int = 2000,
    seed: int = 20261102,
) -> tuple[float, float]:
    """95% percentile interval over groups; ``statistic`` maps stacked rows -> float."""

    groups = sorted(values_by_group)
    rng = np.random.default_rng(seed)
    out = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        picked = rng.integers(0, len(groups), size=len(groups))
        out[index] = statistic(np.concatenate([values_by_group[groups[i]] for i in picked]))
    low, high = np.percentile(out, (2.5, 97.5))
    return float(low), float(high)


def split_by_group(matrix: SuccessMatrix, mask: np.ndarray) -> dict[str, np.ndarray]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for index in np.flatnonzero(mask):
        buckets[matrix.groups[index]].append(int(index))
    return {group: np.asarray(indices) for group, indices in buckets.items()}


def headroom_with_ci(
    matrix: SuccessMatrix,
    candidates: Sequence[str],
    *,
    rows: np.ndarray,
    iterations: int = 2000,
    seed: int = 20261102,
) -> dict[str, object]:
    """Point estimate plus a document-cluster interval; the fixed method stays frozen."""

    point = fixed_and_oracle(matrix, candidates, rows=rows)
    test = rows & matrix.split_mask("test")
    columns = [matrix.methods.index(name) for name in candidates]
    fixed_column = matrix.methods.index(str(point["train_best"]))
    buckets = split_by_group(matrix, test)
    packed = {
        group: np.stack(
            [matrix.success[indices][:, columns].any(axis=1), matrix.success[indices, fixed_column]],
            axis=1,
        ).astype(np.float64)
        for group, indices in buckets.items()
    }
    low, high = cluster_bootstrap(
        packed,
        lambda stacked: float(stacked[:, 0].mean() - stacked[:, 1].mean()),
        iterations=iterations,
        seed=seed,
    )
    return {**point, "headroom_ci95": [low, high], "groups": len(buckets)}


def paired_delta_with_ci(
    matrix: SuccessMatrix,
    method_a: str,
    method_b: str,
    *,
    rows: np.ndarray,
    iterations: int = 2000,
    seed: int = 20261102,
) -> dict[str, object]:
    """``exact(a) - exact(b)`` on test with a document-cluster interval."""

    test = rows & matrix.split_mask("test")
    buckets = split_by_group(matrix, test)
    column_a, column_b = matrix.methods.index(method_a), matrix.methods.index(method_b)
    packed = {
        group: np.stack(
            [matrix.success[indices, column_a], matrix.success[indices, column_b]], axis=1
        ).astype(np.float64)
        for group, indices in buckets.items()
    }
    delta = float(matrix.success[test, column_a].mean() - matrix.success[test, column_b].mean())
    low, high = cluster_bootstrap(
        packed,
        lambda stacked: float(stacked[:, 0].mean() - stacked[:, 1].mean()),
        iterations=iterations,
        seed=seed,
    )
    return {
        "a": method_a,
        "b": method_b,
        "delta_exact_a_minus_b": delta,
        "ci95": [low, high],
        "samples": int(test.sum()),
        "groups": len(buckets),
    }


def selection_floor(
    success_by_view: np.ndarray,
    *,
    view_count: int,
    permutations: int = 200,
    seed: int = 20261102,
) -> dict[str, float]:
    """Expected best-of-``view_count`` gain when views carry NO distinct content.

    ``success_by_view`` is ``[samples, views]`` for views that are exchangeable
    noise realizations of the same content. The estimate resamples ``view_count``
    columns without replacement and reports the mean of
    ``mean(any(.)) - mean(first column)``.
    """

    samples, available = success_by_view.shape
    if view_count > available:
        raise ValueError("view_count exceeds the number of available views")
    rng = np.random.default_rng(seed)
    gains = np.empty(permutations, dtype=np.float64)
    for index in range(permutations):
        picked = rng.permutation(available)[:view_count]
        block = success_by_view[:, picked]
        gains[index] = block.any(axis=1).mean() - block[:, 0].mean()
    return {
        "mean_gain": float(gains.mean()),
        "std_gain": float(gains.std()),
        "view_count": int(view_count),
    }
