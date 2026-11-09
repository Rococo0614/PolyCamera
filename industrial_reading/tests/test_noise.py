import unittest

import numpy as np

from polread.noise import (
    NoiseFit,
    erode,
    estimate_noise_from_redundancy,
    fit_noise_from_pairs,
    fit_variance_model,
    flat_region_mask,
    gaussian_smooth,
    redundancy_residual,
)


def _poisson_gaussian(clean: np.ndarray, a: float, b: float, rng) -> np.ndarray:
    return clean + np.sqrt(a * clean + b) * rng.standard_normal(clean.shape)


class NoiseFitTests(unittest.TestCase):
    def test_recovers_known_parameters_from_reference_pairs(self):
        a, b = 0.0006, 0.00003
        rng = np.random.default_rng(0)
        # smooth ramp so every intensity bin is populated
        x = np.linspace(0.05, 0.95, 400)
        clean = np.tile(x, (300, 1))
        references = [{k: clean for k in ("i0", "i45", "i90", "i135")}]
        noisy = [{k: _poisson_gaussian(clean, a, b, rng) for k in ("i0", "i45", "i90", "i135")}]
        fit = fit_noise_from_pairs(references, noisy, bins=12, minimum_bin_count=500)
        self.assertAlmostEqual(fit.model.a, a, delta=0.2 * a)
        self.assertAlmostEqual(fit.model.b, b, delta=0.6 * b + 2e-5)
        self.assertGreater(fit.r_squared, 0.9)
        self.assertIn("0.5", fit.to_dict()["sigma_gray_at"])

    def test_coefficients_are_clipped_to_valid_variance(self):
        rng = np.random.default_rng(1)
        x = rng.uniform(0, 1, 60000)
        residual = rng.standard_normal(x.size) * 0.01  # constant variance, a ~ 0
        fit = fit_variance_model(x, residual, bins=8, minimum_bin_count=500)
        self.assertGreaterEqual(fit.model.a, 0.0)
        self.assertGreaterEqual(fit.model.b, 0.0)
        self.assertAlmostEqual(fit.model.b, 1e-4, delta=3e-5)

    def test_too_few_populated_bins_raises(self):
        with self.assertRaises(ValueError):
            fit_variance_model(np.full(5000, 0.5), np.zeros(5000), bins=8, minimum_bin_count=100)

    def test_mismatched_shapes_raise(self):
        with self.assertRaises(ValueError):
            fit_variance_model(np.zeros(10), np.zeros(9))


class BlindEstimatorTests(unittest.TestCase):
    def _capture(self, rng, a, b, size=(160, 200)):
        # unpolarized-ish smooth scene: i0 + i90 == i45 + i135 holds exactly
        yy, xx = np.mgrid[0 : size[0], 0 : size[1]]
        base = 0.2 + 0.6 * (xx / size[1])
        pol = 0.1 * np.sin(yy / 25.0)
        clean = {
            "i0": base * 0.5 + pol,
            "i90": base * 0.5 - pol,
            "i45": base * 0.5 + 0.5 * pol,
            "i135": base * 0.5 - 0.5 * pol,
        }
        return {k: np.clip(_poisson_gaussian(v, a, b, rng), 0.0, 1.0) * 255.0 for k, v in clean.items()}

    def test_redundancy_residual_cancels_signal(self):
        rng = np.random.default_rng(3)
        clean = {"i0": 0.7, "i90": 0.3, "i45": 0.55, "i135": 0.45}
        channels = {k: np.full((2000,), v) + 0.01 * rng.standard_normal(2000) for k, v in clean.items()}
        residual = redundancy_residual(channels)
        self.assertAlmostEqual(float(residual.mean()), 0.0, delta=2e-3)
        self.assertAlmostEqual(float(residual.std()), 0.01, delta=1.5e-3)

    def test_blind_estimate_matches_injected_noise_level(self):
        a, b = 0.0003, 0.00004
        rng = np.random.default_rng(4)
        captures = [self._capture(rng, a, b) for _ in range(6)]
        fit = estimate_noise_from_redundancy(captures, bins=10, minimum_bin_count=800)
        self.assertIsInstance(fit, NoiseFit)
        for x in (0.3, 0.5, 0.7):
            expected = np.sqrt(a * x + b)
            self.assertAlmostEqual(fit.sigma(x), expected, delta=0.35 * expected)

    def test_robust_default_resists_residual_outliers(self):
        """Mean-preserving channel disagreements must not inflate the estimate.

        Moving +d into i0 and -d/2 into each of i45/i135 leaves the mean image
        untouched, so the flat-region mask cannot remove these pixels, yet the
        redundancy residual jumps by d. Plain variance is dragged up; the MAD
        based default is not.
        """

        a, b = 0.0003, 0.00004
        rng = np.random.default_rng(9)
        delta = 0.08 * 255.0
        captures = []
        for _ in range(8):
            capture = self._capture(rng, a, b, size=(160, 200))
            spikes = rng.random(capture["i0"].shape) < 0.03
            capture["i0"] = np.where(spikes, np.minimum(capture["i0"] + delta, 255.0), capture["i0"])
            for key in ("i45", "i135"):
                capture[key] = np.where(spikes, np.maximum(capture[key] - 0.5 * delta, 0.0), capture[key])
            captures.append(capture)
        robust = estimate_noise_from_redundancy(captures, bins=16, minimum_bin_count=500)
        plain = estimate_noise_from_redundancy(
            captures, bins=16, minimum_bin_count=500, robust=False
        )
        expected = np.sqrt(a * 0.25 + b)
        self.assertAlmostEqual(robust.sigma(0.25), expected, delta=0.2 * expected)
        self.assertGreater(plain.sigma(0.25), 1.35 * expected)

    def test_no_usable_pixels_raises(self):
        flat = {k: np.full((20, 20), 255.0) for k in ("i0", "i45", "i90", "i135")}
        with self.assertRaises(ValueError):
            estimate_noise_from_redundancy([flat])

    def test_saturated_white_paper_does_not_bias_the_estimate(self):
        """Clipped pixels have zero residual variance; they must be excluded."""

        a, b = 0.0003, 0.00004
        rng = np.random.default_rng(6)
        captures = []
        for _ in range(6):
            capture = self._capture(rng, a, b, size=(160, 200))
            for key in capture:
                capture[key][:, 100:] = 255.0  # right half: clipped white background
            captures.append(capture)
        fit = estimate_noise_from_redundancy(
            captures, bins=20, minimum_bin_count=500, gradient_quantile=0.95
        )
        # No intensity bin may be built from the clipped (x ~ 1) background.
        self.assertLess(max(fit.bin_centers), 0.97)
        expected = np.sqrt(a * 0.2 + b)
        self.assertAlmostEqual(fit.sigma(0.2), expected, delta=0.4 * expected)

    def test_misregistered_edges_are_excluded_by_the_flat_mask(self):
        """Demosaicking-style channel offsets break the identity only at edges."""

        a, b = 0.0003, 0.00004
        rng = np.random.default_rng(8)
        height, width = 160, 200
        yy, xx = np.mgrid[0:height, 0:width]
        ramp = 0.25 + 0.5 * (xx / width)
        stripes = 0.35 + 0.3 * ((xx // 2) % 2)  # period-4 vertical stripes
        scene = np.where(xx < 110, ramp, stripes)
        captures = []
        for _ in range(5):
            clean = {key: 0.5 * scene for key in ("i0", "i45", "i90", "i135")}
            clean["i0"] = np.roll(clean["i0"], 1, axis=1)  # one-pixel channel offset
            captures.append(
                {k: np.clip(_poisson_gaussian(v, a, b, rng), 0.0, 1.0) * 255.0 for k, v in clean.items()}
            )
        fit = estimate_noise_from_redundancy(
            captures, bins=16, minimum_bin_count=500, gradient_quantile=0.5
        )
        expected = np.sqrt(a * 0.2 + b)
        self.assertAlmostEqual(fit.sigma(0.2), expected, delta=0.25 * expected)


class NumpyFilterTests(unittest.TestCase):
    def test_gaussian_smooth_preserves_constant_and_reduces_variance(self):
        constant = np.full((20, 30), 3.0)
        self.assertTrue(np.allclose(gaussian_smooth(constant, 1.5), constant))
        noise = np.random.default_rng(0).standard_normal((100, 100))
        self.assertLess(float(gaussian_smooth(noise, 2.0).std()), float(noise.std()) * 0.5)
        self.assertTrue(np.array_equal(gaussian_smooth(noise, 0.0), noise))

    def test_erode_shrinks_and_clears_border(self):
        mask = np.ones((7, 7), dtype=bool)
        once = erode(mask, 1)
        self.assertFalse(once[0, 3])
        self.assertTrue(once[3, 3])
        self.assertEqual(int(erode(mask, 3).sum()), 1)
        self.assertTrue(np.array_equal(erode(mask, 0), mask))

    def test_flat_mask_excludes_edges(self):
        image = np.zeros((60, 60))
        image[:, 30:] = 1.0
        mask = flat_region_mask(image, gradient_quantile=0.6, erosion=1)
        self.assertFalse(mask[30, 29] or mask[30, 30])
        self.assertTrue(mask[30, 5])


if __name__ == "__main__":
    unittest.main()
