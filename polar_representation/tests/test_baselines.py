import unittest

import numpy as np

from polrep.baselines import SceneEqualAffineAccumulator, oracle_channel_affine, representations


class BaselineTests(unittest.TestCase):
    def test_virtual_min_between_extrema(self):
        base = np.full((4, 5, 3), 0.5)
        channels = {
            "000": base + 0.2,
            "045": base + 0.1,
            "090": base - 0.2,
            "135": base - 0.1,
        }
        views = representations(channels, base)
        self.assertTrue(np.all(views["virtual_min"] <= views["mean4"] + 1e-12))
        self.assertTrue(np.all(views["virtual_max"] >= views["mean4"] - 1e-12))

    def test_scene_equal_affine_recovers_mapping(self):
        accumulator = SceneEqualAffineAccumulator()
        first = np.linspace(0.05, 0.8, 300).reshape(10, 10, 3)
        second = np.clip(first * np.array([1.1, 0.8, 1.2]) + np.array([0.02, 0.05, -0.03]), 0, 1)
        accumulator.add("scene-a", first, second, stride=1)
        model = accumulator.fit()
        np.testing.assert_allclose(model.gain, [1.1, 0.8, 1.2], atol=1e-10)
        np.testing.assert_allclose(model.offset, [0.02, 0.05, -0.03], atol=1e-10)

    def test_oracle_affine_is_only_colorwise(self):
        source = np.linspace(0.05, 0.7, 300).reshape(10, 10, 3)
        target = source * np.array([0.9, 1.1, 0.7]) + np.array([0.03, -0.02, 0.08])
        corrected, model = oracle_channel_affine(source, target)
        np.testing.assert_allclose(corrected, target, atol=1e-12)
        np.testing.assert_allclose(model.gain, [0.9, 1.1, 0.7], atol=1e-12)


if __name__ == "__main__":
    unittest.main()
