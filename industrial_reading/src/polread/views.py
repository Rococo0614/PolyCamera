"""Deterministic OCR input views for the offline E2/E3 controls.

Every view is a pure function of the four SDK-exported polarization channel
crops (uint8) of one ROI, plus a seed for the noise-only null views.

Raw, ``virtual_*`` and ``mean`` views are pointwise, so computing them on crops
is identical to computing the whole image and cropping afterwards (a unit test
asserts this, which is what makes them comparable with the earlier whole-image
``load_representation`` results). The matching views (``hm_*``, ``ms_*``) use
per-ROI statistics by design, and the null views draw noise per crop from a
seed derived from ``(seed, sample_id, view_name)``.

Note that ``virtual_<angle>`` is *not* the raw channel even at 0/45/90/135:
the Stokes synthesis uses all four channels, so it partly denoises. Controls
therefore compare against the canonical virtual angles, not only raw channels.

View names
----------
``i0|i45|i90|i135``
    Raw channel crop.
``virtual_<angle>``
    Ideal linear analyzer at ``angle`` degrees synthesized from the Stokes
    estimate of all four channels.
``hm_<key>``
    Raw channel ``key`` after exact-as-possible histogram matching to the
    pooled histogram of the four raw crops of the same ROI.
``ms_<key>``
    Raw channel ``key`` after per-crop mean/std matching to the mean of the
    four crops' means and standard deviations.
``null_<base>_m<multiplier>_k<index>``
    Noise-only null view: ``base`` (``mean`` of the four channels or one raw
    channel) plus independent heteroscedastic Gaussian noise whose strength is
    ``multiplier`` times a calibrated Poisson-Gaussian model. ``index``
    selects an independent noise realization. All four ``k`` carry identical
    polarization content, so any best-of-four gain is pure selection effect.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import re

import numpy as np

from .polarization import ANGLE_KEYS, linear_stokes, to_uint8, virtual_analyzer

_VIRTUAL = re.compile(r"^virtual_(-?[0-9]+(?:\.[0-9]+)?)$")
_HM = re.compile(r"^hm_(i0|i45|i90|i135)$")
_MS = re.compile(r"^ms_(i0|i45|i90|i135)$")
_NULL = re.compile(r"^null_(mean|i0|i45|i90|i135)_m([0-9]+(?:\.[0-9]+)?)_k([0-9]+)$")


@dataclass(frozen=True)
class NoiseModel:
    """Poisson-Gaussian variance ``a * x + b`` for ``x`` in [0, 1]."""

    a: float
    b: float

    def sigma_gray(self, gray: np.ndarray, multiplier: float = 1.0) -> np.ndarray:
        """Per-pixel noise standard deviation in 8-bit gray levels."""

        x = np.clip(np.asarray(gray, dtype=np.float64) / 255.0, 0.0, 1.0)
        variance = np.maximum(self.a * x + self.b, 0.0)
        return 255.0 * float(multiplier) * np.sqrt(variance)


def view_seed(seed: int, sample_id: str, view_name: str) -> int:
    """Stable 64-bit seed independent of sharding, backend and process order."""

    digest = hashlib.sha256(f"{seed}|{sample_id}|{view_name}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


def _as_uint8_channels(crops: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    channels: dict[str, np.ndarray] = {}
    shape = None
    for key in ANGLE_KEYS:
        if key not in crops:
            raise ValueError(f"Missing polarization channel crop: {key}")
        array = np.asarray(crops[key])
        if array.dtype != np.uint8 or array.ndim != 2:
            raise ValueError(f"{key} crop must be a uint8 HxW array, got {array.dtype} {array.shape}")
        if shape is None:
            shape = array.shape
        elif array.shape != shape:
            raise ValueError("Polarization channel crops must have identical shapes")
        channels[key] = array
    return channels


def virtual_view(crops: Mapping[str, np.ndarray], angle_deg: float) -> np.ndarray:
    channels = _as_uint8_channels(crops)
    floats = {key: array.astype(np.float64) for key, array in channels.items()}
    return to_uint8(virtual_analyzer(linear_stokes(floats), angle_deg), mode="clip")


def mean_view(crops: Mapping[str, np.ndarray]) -> np.ndarray:
    channels = _as_uint8_channels(crops)
    stack = np.stack([channels[key].astype(np.float64) for key in ANGLE_KEYS], axis=0)
    return to_uint8(np.mean(stack, axis=0), mode="clip")


def pooled_histogram_match(images: Sequence[np.ndarray]) -> list[np.ndarray]:
    """Map every uint8 image onto the pooled (mean-CDF) histogram of all inputs.

    The mapping is monotone non-decreasing, so pixel ordering is preserved and
    only the gray-level distribution is equalized. Identical inputs are returned
    unchanged.
    """

    if not images:
        raise ValueError("At least one image is required")
    arrays = [np.asarray(image) for image in images]
    for array in arrays:
        if array.dtype != np.uint8:
            raise ValueError("Histogram matching expects uint8 images")
    cdfs = []
    for array in arrays:
        histogram = np.bincount(array.ravel(), minlength=256).astype(np.float64)
        cdfs.append(np.cumsum(histogram) / histogram.sum())
    target = np.mean(cdfs, axis=0)
    matched: list[np.ndarray] = []
    for array, cdf in zip(arrays, cdfs, strict=True):
        mapping = np.clip(np.searchsorted(target, cdf, side="left"), 0, 255).astype(np.uint8)
        matched.append(mapping[array])
    return matched


def mean_std_match(images: Sequence[np.ndarray]) -> list[np.ndarray]:
    """Affine-match each uint8 image to the mean of the inputs' mean and std."""

    if not images:
        raise ValueError("At least one image is required")
    arrays = [np.asarray(image, dtype=np.float64) for image in images]
    means = np.array([array.mean() for array in arrays])
    stds = np.array([array.std() for array in arrays])
    target_mean = float(means.mean())
    target_std = float(stds.mean())
    matched: list[np.ndarray] = []
    for array, mean, std in zip(arrays, means, stds, strict=True):
        if std < 1e-9:
            output = np.full(array.shape, target_mean)
        else:
            output = (array - mean) / std * target_std + target_mean
        matched.append(np.clip(np.rint(output), 0, 255).astype(np.uint8))
    return matched


def inject_noise(
    base: np.ndarray,
    model: NoiseModel,
    multiplier: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Add heteroscedastic Gaussian noise to a uint8 image; 0 leaves it unchanged."""

    array = np.asarray(base)
    if array.dtype != np.uint8:
        raise ValueError("Noise injection expects a uint8 base image")
    if multiplier < 0:
        raise ValueError("multiplier must be non-negative")
    if multiplier == 0:
        return array.copy()
    sigma = model.sigma_gray(array, multiplier)
    noisy = array.astype(np.float64) + sigma * rng.standard_normal(array.shape)
    return np.clip(np.rint(noisy), 0, 255).astype(np.uint8)


def compute_view(
    view_name: str,
    crops: Mapping[str, np.ndarray],
    *,
    sample_id: str = "",
    seed: int = 0,
    noise_model: NoiseModel | None = None,
) -> np.ndarray:
    """Compute one named uint8 view from the four raw channel crops."""

    if view_name in ANGLE_KEYS:
        return _as_uint8_channels(crops)[view_name].copy()

    match = _VIRTUAL.match(view_name)
    if match:
        return virtual_view(crops, float(match.group(1)))

    match = _HM.match(view_name)
    if match:
        channels = _as_uint8_channels(crops)
        matched = pooled_histogram_match([channels[key] for key in ANGLE_KEYS])
        return matched[ANGLE_KEYS.index(match.group(1))]

    match = _MS.match(view_name)
    if match:
        channels = _as_uint8_channels(crops)
        matched = mean_std_match([channels[key] for key in ANGLE_KEYS])
        return matched[ANGLE_KEYS.index(match.group(1))]

    match = _NULL.match(view_name)
    if match:
        if noise_model is None:
            raise ValueError("Null views require a calibrated NoiseModel")
        base_name, multiplier, _index = match.group(1), float(match.group(2)), int(match.group(3))
        base = mean_view(crops) if base_name == "mean" else _as_uint8_channels(crops)[base_name]
        rng = np.random.default_rng(view_seed(seed, sample_id, view_name))
        return inject_noise(base, noise_model, multiplier, rng)

    raise ValueError(f"Unknown view name: {view_name}")


def virtual_angle_views(step_deg: int = 5) -> tuple[str, ...]:
    """Names of the dense virtual-analyzer grid over [0, 180)."""

    if step_deg <= 0 or 180 % step_deg:
        raise ValueError("step_deg must be a positive divisor of 180")
    return tuple(f"virtual_{angle}" for angle in range(0, 180, step_deg))
