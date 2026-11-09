import unittest

import numpy as np

from polread.polarization import ANGLE_KEYS, linear_stokes, to_uint8, virtual_analyzer
from polread.views import (
    NoiseModel,
    compute_view,
    inject_noise,
    mean_std_match,
    mean_view,
    pooled_histogram_match,
    view_seed,
    virtual_angle_views,
)


def _crops(seed: int = 0, shape=(24, 40)) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    base = rng.integers(40, 200, size=shape)
    return {
        key: np.clip(base + offset + rng.integers(-6, 7, size=shape), 0, 255).astype(np.uint8)
        for key, offset in zip(ANGLE_KEYS, (20, 5, -15, -8), strict=True)
    }


class VirtualViewTests(unittest.TestCase):
    def test_dense_grid_has_36_unique_angles(self):
        names = virtual_angle_views(5)
        self.assertEqual(len(names), 36)
        self.assertEqual(len(set(names)), 36)
        self.assertEqual(names[0], "virtual_0")
        self.assertEqual(names[-1], "virtual_175")
        with self.assertRaises(ValueError):
            virtual_angle_views(7)

    def test_crop_then_view_equals_view_then_crop(self):
        """Pointwise views must be identical to the earlier whole-image path."""

        full = _crops(seed=3, shape=(48, 64))
        box = (slice(5, 21), slice(9, 37))
        cropped = {key: value[box] for key, value in full.items()}
        stokes = linear_stokes({key: value.astype(np.float64) for key, value in full.items()})
        for angle in (0, 20, 45, 77.5, 90, 135):
            whole = to_uint8(virtual_analyzer(stokes, angle), mode="clip")[box]
            via_crop = compute_view(f"virtual_{angle}", cropped)
            self.assertTrue(np.array_equal(whole, via_crop), angle)
        whole_mean = to_uint8(
            np.mean(np.stack([full[key].astype(np.float64) for key in ANGLE_KEYS]), axis=0),
            mode="clip",
        )[box]
        self.assertTrue(np.array_equal(whole_mean, mean_view(cropped)))

    def test_virtual_canonical_matches_raw_when_channels_are_consistent(self):
        # i0 + i90 == i45 + i135 -> Stokes synthesis returns the raw channel exactly.
        values = {"i0": 140, "i45": 120, "i90": 60, "i135": 80}
        crops = {key: np.full((8, 8), value, dtype=np.uint8) for key, value in values.items()}
        for angle, key in ((0, "i0"), (45, "i45"), (90, "i90"), (135, "i135")):
            self.assertTrue(np.array_equal(compute_view(f"virtual_{angle}", crops), crops[key]))

    def test_virtual_canonical_denoises_inconsistent_channels(self):
        # With i0 + i90 != i45 + i135 the synthesis differs from the raw channel,
        # which is why controls must use virtual canonical angles as the baseline.
        crops = {key: np.full((4, 4), value, dtype=np.uint8) for key, value in
                 {"i0": 150, "i45": 100, "i90": 60, "i135": 80}.items()}
        self.assertFalse(np.array_equal(compute_view("virtual_0", crops), crops["i0"]))

    def test_unknown_and_bad_inputs_rejected(self):
        crops = _crops()
        with self.assertRaises(ValueError):
            compute_view("nonsense", crops)
        with self.assertRaises(ValueError):
            compute_view("virtual_0", {"i0": crops["i0"]})
        bad = dict(crops, i45=crops["i45"].astype(np.float32))
        with self.assertRaises(ValueError):
            compute_view("virtual_0", bad)
        bad_shape = dict(crops, i45=crops["i45"][:-1])
        with self.assertRaises(ValueError):
            compute_view("virtual_0", bad_shape)


class MatchingTests(unittest.TestCase):
    def test_histogram_match_equalizes_pooled_distribution(self):
        rng = np.random.default_rng(0)
        dark = rng.integers(10, 90, size=(60, 60)).astype(np.uint8)
        bright = rng.integers(120, 250, size=(60, 60)).astype(np.uint8)
        matched = pooled_histogram_match([dark, bright])
        # Both images are pulled to the *pooled* distribution, whose mean is the
        # average of the inputs' means. Mapping everything onto the first image
        # would leave the first image unchanged and fail this.
        pooled_mean = 0.5 * (float(dark.mean()) + float(bright.mean()))
        for result in matched:
            self.assertAlmostEqual(float(result.mean()), pooled_mean, delta=8.0)
        self.assertFalse(np.array_equal(matched[0], dark))
        self.assertFalse(np.array_equal(matched[1], bright))
        # monotone: gray-level ordering inside each image is preserved
        for original, result in zip((dark, bright), matched, strict=True):
            order = np.argsort(original.ravel(), kind="stable")
            self.assertTrue(np.all(np.diff(result.ravel()[order].astype(int)) >= 0))

    def test_histogram_match_is_independent_of_input_order(self):
        rng = np.random.default_rng(7)
        first = rng.integers(10, 120, size=(40, 40)).astype(np.uint8)
        second = rng.integers(90, 250, size=(40, 40)).astype(np.uint8)
        forward = pooled_histogram_match([first, second])
        backward = pooled_histogram_match([second, first])
        self.assertTrue(np.array_equal(forward[0], backward[1]))
        self.assertTrue(np.array_equal(forward[1], backward[0]))

    def test_histogram_match_is_identity_for_identical_inputs(self):
        image = _crops()["i0"]
        for result in pooled_histogram_match([image, image.copy(), image.copy(), image.copy()]):
            self.assertTrue(np.array_equal(result, image))

    def test_mean_std_match_equalizes_first_two_moments(self):
        rng = np.random.default_rng(1)
        images = [
            np.clip(rng.normal(60, 10, (80, 80)), 0, 255).astype(np.uint8),
            np.clip(rng.normal(150, 30, (80, 80)), 0, 255).astype(np.uint8),
        ]
        matched = mean_std_match(images)
        means = [float(item.mean()) for item in matched]
        stds = [float(item.std()) for item in matched]
        # Target is the average of the inputs' moments, not any single input's.
        pooled_mean = 0.5 * sum(float(item.mean()) for item in images)
        pooled_std = 0.5 * sum(float(item.std()) for item in images)
        for mean, std in zip(means, stds, strict=True):
            self.assertAlmostEqual(mean, pooled_mean, delta=1.5)
            self.assertAlmostEqual(std, pooled_std, delta=1.5)
        self.assertGreater(abs(pooled_mean - float(images[0].mean())), 20.0)

    def test_flat_image_does_not_divide_by_zero(self):
        flat = np.full((6, 6), 77, dtype=np.uint8)
        textured = _crops()["i0"][:6, :6]
        matched = mean_std_match([flat, textured])
        self.assertEqual(matched[0].shape, (6, 6))
        self.assertTrue(np.all(matched[0] == matched[0][0, 0]))

    def test_named_matching_views(self):
        crops = _crops()
        for key in ANGLE_KEYS:
            self.assertEqual(compute_view(f"hm_{key}", crops).shape, crops[key].shape)
            self.assertEqual(compute_view(f"ms_{key}", crops).dtype, np.uint8)


class NullViewTests(unittest.TestCase):
    model = NoiseModel(a=0.0004, b=0.00005)

    def test_zero_multiplier_is_identity(self):
        crops = _crops()
        rng = np.random.default_rng(0)
        out = inject_noise(crops["i0"], self.model, 0.0, rng)
        self.assertTrue(np.array_equal(out, crops["i0"]))
        # A copy, not an alias: callers must be able to mutate the result safely.
        self.assertFalse(np.shares_memory(out, crops["i0"]))
        out[0, 0] = np.uint8((int(out[0, 0]) + 1) % 256)
        self.assertNotEqual(int(out[0, 0]), int(crops["i0"][0, 0]))
        # A zero-multiplier null view must also consume no randomness.
        state = np.random.default_rng(3)
        before = state.bit_generator.state
        inject_noise(crops["i0"], self.model, 0.0, state)
        self.assertEqual(state.bit_generator.state, before)

    def test_noise_strength_matches_model(self):
        flat = np.full((400, 400), 128, dtype=np.uint8)
        noisy = inject_noise(flat, self.model, 1.0, np.random.default_rng(5)).astype(np.float64)
        expected = 255.0 * np.sqrt(self.model.a * (128 / 255.0) + self.model.b)
        self.assertAlmostEqual(float(noisy.std()), expected, delta=0.06 * expected)
        doubled = inject_noise(flat, self.model, 2.0, np.random.default_rng(5)).astype(np.float64)
        self.assertAlmostEqual(float(doubled.std()) / float(noisy.std()), 2.0, delta=0.12)

    def test_noise_is_signal_dependent(self):
        rng = np.random.default_rng(2)
        dark = inject_noise(np.full((300, 300), 30, dtype=np.uint8), self.model, 1.0, rng)
        bright = inject_noise(np.full((300, 300), 220, dtype=np.uint8), self.model, 1.0, rng)
        self.assertGreater(float(bright.astype(float).std()), float(dark.astype(float).std()))

    def test_null_views_are_reproducible_and_independent(self):
        crops = _crops()
        name = "null_mean_m1_k0"
        first = compute_view(name, crops, sample_id="s1", seed=7, noise_model=self.model)
        again = compute_view(name, crops, sample_id="s1", seed=7, noise_model=self.model)
        other_k = compute_view("null_mean_m1_k1", crops, sample_id="s1", seed=7, noise_model=self.model)
        other_sample = compute_view(name, crops, sample_id="s2", seed=7, noise_model=self.model)
        self.assertTrue(np.array_equal(first, again))
        self.assertFalse(np.array_equal(first, other_k))
        self.assertFalse(np.array_equal(first, other_sample))

    def test_null_views_share_content_and_need_a_model(self):
        crops = _crops()
        views = [
            compute_view(f"null_mean_m0_k{index}", crops, sample_id="s", seed=1, noise_model=self.model)
            for index in range(4)
        ]
        for view in views[1:]:
            self.assertTrue(np.array_equal(views[0], view))
        self.assertTrue(np.array_equal(views[0], mean_view(crops)))
        with self.assertRaises(ValueError):
            compute_view("null_mean_m1_k0", crops, sample_id="s", seed=1)

    def test_seed_derivation_is_pinned(self):
        # Golden value: changing the derivation silently changes every null-view
        # noise realization, which would break comparability between runs.
        self.assertEqual(view_seed(1, "a", "b"), 7298354341163816706)
        self.assertEqual(
            view_seed(20261102, "82092117_a_3", "null_mean_m1_k0"), 5484769712163762483
        )
        self.assertNotEqual(view_seed(1, "a", "b"), view_seed(2, "a", "b"))


if __name__ == "__main__":
    unittest.main()
