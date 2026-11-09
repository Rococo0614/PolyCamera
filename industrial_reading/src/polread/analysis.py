"""Per-sample gains and paired contrasts for the offline headroom controls.

Everything here is a pure function of a :class:`~polread.headroom.SuccessMatrix`.
A "fixed" method is always chosen on the *train* split of the supplied rows and
every reported number is evaluated on the *test* split, with document-cluster
bootstrap intervals (documents, not ROIs, are the resampling unit because the
15 captures and 10 ROIs of one document are strongly dependent).

Two kinds of per-sample gain are supported:

``fixed gain``
    ``any(S[sample, candidates]) - S[sample, train_best]``. For non-exchangeable
    candidates (e.g. the four raw polarization channels) this is the fraction of
    samples that the best single fixed method misses but another candidate reads,
    i.e. the headroom of ``oracle - fixed``.

``exchangeable gain``
    ``any(S[sample, columns]) - mean(S[sample, columns])``. For views that carry
    identical content and differ only by an independent noise realization every
    column is interchangeable, so "the fixed method" is any column in
    expectation and the gain is the pure selection effect of picking the best of
    ``len(columns)`` re-draws.

``clean-base gain``
    ``any(base, k noisy re-draws) - base``, averaged over all subsets of ``k``
    re-draws. Same form as the real fixed gain (a clean fixed baseline plus
    alternatives) but the alternatives carry no new content, so the baseline
    accuracy is identical to the real one and only the alternatives differ.

Because both gains are plain per-sample vectors on identical test rows, any two
of them can be contrasted with a paired document-cluster interval
(:func:`contrast_with_ci`), which is how real polarization views are compared
with matched noise-only nulls.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .headroom import SuccessMatrix, cluster_bootstrap, train_best

DEFAULT_SEED = 20261102


@dataclass(frozen=True)
class GainSample:
    """Per-sample gains on the evaluation rows, aligned with matrix indices."""

    label: str
    indices: np.ndarray  # row indices into the SuccessMatrix (evaluation split only)
    values: np.ndarray  # float64 gain per sample
    columns: tuple[str, ...]  # candidate / view names used
    chosen: str | None  # train-selected fixed method; None for exchangeable gains
    single_exact: float  # exact-read rate of the reference single method (chosen or mean)
    any_exact: float  # oracle (best-of-columns) exact-read rate


def _evaluation_indices(matrix: SuccessMatrix, rows: np.ndarray, split: str | None) -> np.ndarray:
    """Row indices to evaluate; ``split=None`` evaluates every selected row.

    A fixed method is *always* chosen on the train rows regardless of ``split``;
    ``split=None`` therefore includes the train rows in the evaluation, which makes
    the fixed baseline optimistic (selected on the data it is scored on). It is only
    meant for checking that a conclusion does not hinge on the 7-document test split.
    """

    mask = np.asarray(rows, dtype=bool)
    if split is not None:
        mask = mask & matrix.split_mask(split)
    indices = np.flatnonzero(mask)
    if not len(indices):
        raise ValueError(f"No {split or 'selected'} samples in the requested rows")
    return indices


def _columns(matrix: SuccessMatrix, names: Sequence[str]) -> list[int]:
    if not names:
        raise ValueError("At least one method is required")
    if len(set(names)) != len(names):
        raise ValueError("Duplicate method names")
    return [matrix.methods.index(name) for name in names]


def fixed_gain_sample(
    matrix: SuccessMatrix,
    candidates: Sequence[str],
    *,
    rows: np.ndarray,
    split: str | None = "test",
    label: str = "",
) -> GainSample:
    """``any - train-best fixed`` per evaluation sample (values are 0 or 1)."""

    columns = _columns(matrix, candidates)  # validates before any selection happens
    chosen = train_best(matrix, list(candidates), rows=rows)
    indices = _evaluation_indices(matrix, rows, split)
    block = matrix.success[np.ix_(indices, columns)]
    any_success = block.any(axis=1)
    fixed_success = matrix.column(chosen)[indices]
    return GainSample(
        label=label or "fixed",
        indices=indices,
        values=any_success.astype(np.float64) - fixed_success.astype(np.float64),
        columns=tuple(candidates),
        chosen=chosen,
        single_exact=float(fixed_success.mean()),
        any_exact=float(any_success.mean()),
    )


def exchangeable_gain_sample(
    matrix: SuccessMatrix,
    views: Sequence[str],
    *,
    rows: np.ndarray,
    split: str | None = "test",
    label: str = "",
) -> GainSample:
    """``any - mean single`` per evaluation sample for interchangeable views."""

    if len(views) < 2:
        raise ValueError("An exchangeable gain needs at least two views")
    columns = _columns(matrix, views)
    indices = _evaluation_indices(matrix, rows, split)
    block = matrix.success[np.ix_(indices, columns)]
    any_success = block.any(axis=1)
    mean_single = block.mean(axis=1)
    return GainSample(
        label=label or "exchangeable",
        indices=indices,
        values=any_success.astype(np.float64) - mean_single,
        columns=tuple(views),
        chosen=None,
        single_exact=float(block.mean()),
        any_exact=float(any_success.mean()),
    )


def clean_base_gain_sample(
    matrix: SuccessMatrix,
    base: str,
    noisy_views: Sequence[str],
    *,
    alternatives: int = 3,
    rows: np.ndarray,
    split: str | None = "test",
    label: str = "",
) -> GainSample:
    """Gain of a clean baseline plus ``alternatives`` noisy re-draws of the same content.

    This mirrors the real set ``{i0, i45, i90, i135}``: one fixed clean baseline and
    ``alternatives`` other inputs. Per sample the value is
    ``any(base, subset) - base`` averaged over *every* subset of ``alternatives``
    views drawn from ``noisy_views`` (the re-draws are exchangeable, so the result
    cannot depend on which realization is called which).
    """

    if alternatives < 1 or alternatives > len(noisy_views):
        raise ValueError("alternatives must be between 1 and the number of noisy views")
    if base in noisy_views:
        raise ValueError("The clean base must not be one of the noisy views")
    base_column = matrix.methods.index(base)
    noisy_columns = _columns(matrix, noisy_views)
    indices = _evaluation_indices(matrix, rows, split)
    base_success = matrix.success[indices, base_column]
    noisy = matrix.success[np.ix_(indices, noisy_columns)]
    gains = np.zeros(len(indices), dtype=np.float64)
    oracle = 0.0
    subsets = list(combinations(range(len(noisy_columns)), alternatives))
    for subset in subsets:
        any_success = base_success | noisy[:, list(subset)].any(axis=1)
        gains += any_success.astype(np.float64) - base_success.astype(np.float64)
        oracle += float(any_success.mean())
    return GainSample(
        label=label or "clean_base",
        indices=indices,
        values=gains / len(subsets),
        columns=(base, *noisy_views),
        chosen=base,
        single_exact=float(base_success.mean()),
        any_exact=oracle / len(subsets),
    )


def cluster_mean_ci(
    groups: Sequence[Hashable],
    values: np.ndarray,
    *,
    iterations: int = 2000,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Mean of per-sample ``values`` with a 95% document-cluster percentile interval."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(groups) != len(array):
        raise ValueError("values must be a 1-D vector with one entry per group label")
    if not len(array):
        raise ValueError("No values")
    buckets: dict[Hashable, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        buckets[group].append(index)
    packed = {group: array[np.asarray(items)][:, None] for group, items in buckets.items()}
    low, high = cluster_bootstrap(
        packed, lambda stacked: float(stacked[:, 0].mean()), iterations=iterations, seed=seed
    )
    return {
        "mean": float(array.mean()),
        "ci95": [low, high],
        "samples": int(len(array)),
        "groups": len(buckets),
    }


def _groups(matrix: SuccessMatrix, indices: np.ndarray) -> list[str]:
    return [matrix.groups[index] for index in indices]


def summarize_gain(
    matrix: SuccessMatrix,
    sample: GainSample,
    *,
    iterations: int = 2000,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Point estimate and cluster interval of a gain, plus its two exact-read rates."""

    interval = cluster_mean_ci(
        _groups(matrix, sample.indices), sample.values, iterations=iterations, seed=seed
    )
    return {
        "label": sample.label,
        "columns": list(sample.columns),
        "train_best": sample.chosen,
        "single_exact": sample.single_exact,
        "oracle_exact": sample.any_exact,
        "gain": interval["mean"],
        "gain_ci95": interval["ci95"],
        "samples": interval["samples"],
        "groups": interval["groups"],
    }


def contrast_with_ci(
    matrix: SuccessMatrix,
    first: GainSample,
    second: GainSample,
    *,
    iterations: int = 2000,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Paired ``first - second`` gain difference over identical evaluation rows."""

    if not np.array_equal(first.indices, second.indices):
        raise ValueError("Contrasted gains must be defined on identical samples")
    interval = cluster_mean_ci(
        _groups(matrix, first.indices),
        first.values - second.values,
        iterations=iterations,
        seed=seed,
    )
    return {
        "first": first.label,
        "second": second.label,
        "delta_gain": interval["mean"],
        "ci95": interval["ci95"],
        "samples": interval["samples"],
        "groups": interval["groups"],
    }


def exact_delta_with_ci(
    matrix: SuccessMatrix,
    method_a: str,
    method_b: str,
    *,
    rows: np.ndarray,
    split: str | None = "test",
    iterations: int = 2000,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Paired ``exact(a) - exact(b)`` with a document-cluster interval (any split or all)."""

    indices = _evaluation_indices(matrix, rows, split)
    delta = matrix.column(method_a)[indices].astype(np.float64) - matrix.column(method_b)[
        indices
    ].astype(np.float64)
    interval = cluster_mean_ci(_groups(matrix, indices), delta, iterations=iterations, seed=seed)
    return {
        "a": method_a,
        "b": method_b,
        "delta_exact_a_minus_b": interval["mean"],
        "ci95": interval["ci95"],
        "samples": interval["samples"],
        "groups": interval["groups"],
    }


def bracket_doses(
    points: Sequence[tuple[float, float]], low: float, high: float
) -> list[float]:
    """Doses whose monotone response ``value`` matches the target interval ``[low, high]``.

    ``points`` are ``(dose, value)`` pairs where ``value`` rises or falls
    monotonically with dose (pixel distance rises, exact-read rate falls). Every
    dose whose value lies inside the interval is returned; if none does, the
    nearest dose on each side of the interval is returned instead, so a target
    that falls between two grid points is always bracketed rather than snapped.
    """

    if low > high:
        raise ValueError("low must not exceed high")
    if not points:
        raise ValueError("No dose points")
    ordered = sorted(points)
    inside = [dose for dose, value in ordered if low <= value <= high]
    if inside:
        return inside
    below = [(low - value, dose) for dose, value in ordered if value < low]
    above = [(value - high, dose) for dose, value in ordered if value > high]
    picked = [min(side)[1] for side in (below, above) if side]
    return sorted(picked)


def exact_rate_by_view(
    matrix: SuccessMatrix, views: Sequence[str], *, rows: np.ndarray, split: str | None = "test"
) -> dict[str, float]:
    indices = _evaluation_indices(matrix, rows, split)
    return {view: float(matrix.column(view)[indices].mean()) for view in views}


def outcome_agreement(
    matrix: SuccessMatrix,
    first: str,
    second: str,
    *,
    rows: np.ndarray,
    split: str | None = "test",
) -> dict[str, float]:
    """How often two OCR inputs of the same ROI have the same read outcome.

    ``both`` / ``only_first`` / ``only_second`` / ``neither`` are fractions of the
    evaluation samples; ``agreement`` is ``both + neither``.
    """

    indices = _evaluation_indices(matrix, rows, split)
    a = matrix.column(first)[indices]
    b = matrix.column(second)[indices]
    return {
        "both": float(np.mean(a & b)),
        "only_first": float(np.mean(a & ~b)),
        "only_second": float(np.mean(~a & b)),
        "neither": float(np.mean(~a & ~b)),
        "agreement": float(np.mean(a == b)),
        "samples": int(len(indices)),
    }
