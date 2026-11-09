"""Signal-dependent sensor-noise calibration for the offline null controls.

Two independent estimators are provided so one can validate the other:

``fit_noise_from_pairs``
    Uses a noise-free reference and a single noisy capture of the same scene
    (PDD ``GT_*`` and ``Test_*``). The residual variance is regressed on the
    reference intensity: ``var = a * x + b`` with ``x`` in [0, 1].

``estimate_noise_from_redundancy``
    Blind estimator for images without a reference. The four analyzer channels
    obey ``i0 + i90 = i45 + i135`` for an ideal polarimeter, so the residual
    ``r = (i0 + i90 - i45 - i135) / 2`` has the variance of one channel when the
    channel noise is independent and equal. Only flat, edge-free, unsaturated
    pixels are used because interpolation error at edges breaks the identity
    and is not sensor noise.

Only numpy is required. Both estimators return per-bin diagnostics so the fit
quality is auditable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .polarization import ANGLE_KEYS
from .views import NoiseModel

MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class NoiseFit:
    model: NoiseModel
    bin_centers: tuple[float, ...]
    bin_variances: tuple[float, ...]
    bin_counts: tuple[int, ...]
    r_squared: float

    def sigma(self, x: float) -> float:
        """Noise standard deviation at normalized intensity ``x`` in [0, 1]."""

        return float(np.sqrt(max(self.model.a * x + self.model.b, 0.0)))

    def to_dict(self) -> dict[str, object]:
        return {
            "a": self.model.a,
            "b": self.model.b,
            "r_squared": self.r_squared,
            "sigma_gray_at": {
                f"{x:.1f}": 255.0 * self.sigma(x) for x in (0.2, 0.5, 0.8)
            },
            "bin_centers": list(self.bin_centers),
            "bin_variances": list(self.bin_variances),
            "bin_counts": list(self.bin_counts),
        }


def _robust_variance(values: np.ndarray) -> float:
    """Variance from the median absolute deviation (insensitive to edges)."""

    centered = values - np.median(values)
    return float((MAD_TO_SIGMA * np.median(np.abs(centered))) ** 2)


def fit_variance_model(
    intensity: np.ndarray,
    residual: np.ndarray,
    *,
    bins: int = 16,
    minimum_bin_count: int = 2000,
    robust: bool = True,
) -> NoiseFit:
    """Weighted least squares of ``var(residual | intensity) = a*x + b``.

    ``intensity`` is in [0, 1]. Bins with fewer than ``minimum_bin_count``
    samples are dropped. ``a`` and ``b`` are clipped at zero so the model is a
    valid variance function.
    """

    x = np.asarray(intensity, dtype=np.float64).ravel()
    r = np.asarray(residual, dtype=np.float64).ravel()
    if x.shape != r.shape:
        raise ValueError("intensity and residual must have the same number of elements")
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(x, edges) - 1, 0, bins - 1)
    centers: list[float] = []
    variances: list[float] = []
    counts: list[int] = []
    for bin_index in range(bins):
        in_bin = index == bin_index
        selected = r[in_bin]
        if selected.size < minimum_bin_count:
            continue
        centers.append(float(np.mean(x[in_bin])))
        variances.append(_robust_variance(selected) if robust else float(np.var(selected)))
        counts.append(int(selected.size))
    if len(centers) < 3:
        raise ValueError(
            f"Only {len(centers)} intensity bins have >= {minimum_bin_count} samples; need 3"
        )
    c = np.asarray(centers)
    v = np.asarray(variances)
    w = np.sqrt(np.asarray(counts, dtype=np.float64))
    design = np.stack([c, np.ones_like(c)], axis=1)
    coefficients, *_ = np.linalg.lstsq(design * w[:, None], v * w, rcond=None)
    a, b = (max(float(value), 0.0) for value in coefficients)
    fitted = a * c + b
    total = float(np.sum(w * (v - np.average(v, weights=w)) ** 2))
    residual_ss = float(np.sum(w * (v - fitted) ** 2))
    r_squared = 1.0 - residual_ss / total if total > 0 else float("nan")
    return NoiseFit(
        model=NoiseModel(a=a, b=b),
        bin_centers=tuple(centers),
        bin_variances=tuple(variances),
        bin_counts=tuple(counts),
        r_squared=r_squared,
    )


def fit_noise_from_pairs(
    references: list[Mapping[str, np.ndarray]],
    noisy: list[Mapping[str, np.ndarray]],
    *,
    bins: int = 16,
    minimum_bin_count: int = 2000,
) -> NoiseFit:
    """Fit ``a, b`` from full-channel reference/noisy pairs in [0, 1] units."""

    if len(references) != len(noisy):
        raise ValueError("references and noisy must have the same length")
    intensities: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    for reference, observed in zip(references, noisy, strict=True):
        for key in ANGLE_KEYS:
            ref = np.asarray(reference[key], dtype=np.float64)
            obs = np.asarray(observed[key], dtype=np.float64)
            if ref.shape != obs.shape:
                raise ValueError(f"{key}: reference and noisy shapes differ")
            intensities.append(ref.ravel())
            residuals.append((obs - ref).ravel())
    return fit_variance_model(
        np.concatenate(intensities),
        np.concatenate(residuals),
        bins=bins,
        minimum_bin_count=minimum_bin_count,
        robust=False,
    )


def _gaussian_kernel(sigma: float) -> np.ndarray:
    radius = max(1, int(round(3.0 * sigma)))
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
    return kernel / kernel.sum()


def _convolve_axis(image: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    radius = kernel.size // 2
    padding = [(0, 0)] * image.ndim
    padding[axis] = (radius, radius)
    padded = np.pad(image, padding, mode="reflect")
    output = np.zeros(image.shape, dtype=np.float64)
    for offset, weight in enumerate(kernel):
        window = [slice(None)] * image.ndim
        window[axis] = slice(offset, offset + image.shape[axis])
        output += weight * padded[tuple(window)]
    return output


def gaussian_smooth(image: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur with reflected borders."""

    if sigma <= 0:
        return np.asarray(image, dtype=np.float64).copy()
    kernel = _gaussian_kernel(sigma)
    array = np.asarray(image, dtype=np.float64)
    return _convolve_axis(_convolve_axis(array, kernel, 0), kernel, 1)


def erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    """Binary erosion with a 4-neighbour cross; outside the image counts as False."""

    output = np.asarray(mask, dtype=bool).copy()
    for _ in range(iterations):
        padded = np.pad(output, 1, mode="constant", constant_values=False)
        output = (
            padded[1:-1, 1:-1]
            & padded[:-2, 1:-1]
            & padded[2:, 1:-1]
            & padded[1:-1, :-2]
            & padded[1:-1, 2:]
        )
    return output


def flat_region_mask(
    mean_image: np.ndarray,
    *,
    smoothing_sigma: float = 1.5,
    gradient_quantile: float = 0.5,
    erosion: int = 2,
) -> np.ndarray:
    """Pixels whose smoothed gradient magnitude is below a quantile."""

    smooth = gaussian_smooth(mean_image, smoothing_sigma)
    gradient_y, gradient_x = np.gradient(smooth)
    gradient = np.hypot(gradient_y, gradient_x)
    mask = gradient <= np.quantile(gradient, gradient_quantile)
    return erode(mask, erosion) if erosion > 0 else mask


def redundancy_residual(channels: Mapping[str, np.ndarray]) -> np.ndarray:
    """``(i0 + i90 - i45 - i135) / 2``: one-channel variance under iid noise."""

    i0, i45, i90, i135 = (np.asarray(channels[key], dtype=np.float64) for key in ANGLE_KEYS)
    return 0.5 * (i0 + i90 - i45 - i135)


def estimate_noise_from_redundancy(
    capture_channels: list[Mapping[str, np.ndarray]],
    *,
    value_scale: float = 255.0,
    bins: int = 16,
    minimum_bin_count: int = 2000,
    gradient_quantile: float = 0.5,
    saturation_margin: float = 0.015,
    robust: bool = True,
) -> NoiseFit:
    """Blind ``var = a*x + b`` estimate from many four-channel captures.

    Channels are in the units given by ``value_scale`` (255 for uint8) and are
    converted to [0, 1] before fitting so ``a`` and ``b`` are unit-free and
    directly comparable with :func:`fit_noise_from_pairs`. Pixels where any
    channel is within ``saturation_margin`` of 0 or 1 are discarded because
    clipping suppresses variance. ``robust`` uses a MAD-based variance per
    intensity bin so that residual outliers that survive the flat-region mask
    (for example interpolation error that leaves the mean unchanged) do not
    inflate the estimate; set it to False only to quantify that effect.
    """

    intensities: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    for channels in capture_channels:
        scaled = {key: np.asarray(channels[key], dtype=np.float64) / value_scale for key in ANGLE_KEYS}
        mean_image = 0.25 * sum(scaled[key] for key in ANGLE_KEYS)
        stack = np.stack([scaled[key] for key in ANGLE_KEYS], axis=0)
        valid = np.all((stack > saturation_margin) & (stack < 1.0 - saturation_margin), axis=0)
        mask = flat_region_mask(mean_image, gradient_quantile=gradient_quantile) & valid
        if not mask.any():
            continue
        intensities.append(mean_image[mask])
        residuals.append(redundancy_residual(scaled)[mask])
    if not intensities:
        raise ValueError("No flat, unsaturated pixels found in any capture")
    return fit_variance_model(
        np.concatenate(intensities),
        np.concatenate(residuals),
        bins=bins,
        minimum_bin_count=minimum_bin_count,
        robust=robust,
    )
