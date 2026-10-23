import unittest

import numpy as np

from poldepth.polarization import (
    polarization_features,
    quadrant_pairing_scores,
    split_polar_quadrants,
)


class PolarizationTests(unittest.TestCase):
    def test_known_linear_state(self):
        # S0=2, S1=1, S2=0 -> DoLP=0.5, AoLP=0.
        channels = {
            "0": np.array([[1.5]]),
            "45": np.array([[1.0]]),
            "90": np.array([[0.5]]),
            "135": np.array([[1.0]]),
        }
        result = polarization_features(channels)
        self.assertAlmostEqual(float(result["s0"][0, 0]), 2.0)
        self.assertAlmostEqual(float(result["dolp"][0, 0]), 0.5)
        self.assertAlmostEqual(float(result["aolp"][0, 0]), 0.0)
        self.assertTrue(bool(result["valid"][0, 0]))

    def test_aolp_periodic_encoding(self):
        channels = {
            "0": np.array([[1.0]]),
            "45": np.array([[1.5]]),
            "90": np.array([[1.0]]),
            "135": np.array([[0.5]]),
        }
        result = polarization_features(channels)
        self.assertAlmostEqual(float(result["aolp"][0, 0]), np.pi / 4)
        self.assertAlmostEqual(float(result["cos_2aolp"][0, 0]), 0.0, places=7)
        self.assertAlmostEqual(float(result["sin_2aolp"][0, 0]), 1.0)

    def test_quadrant_mapping_is_explicit(self):
        composite = np.array([[1, 2], [3, 4]])
        result = split_polar_quadrants(composite, order=("45", "0", "135", "90"))
        self.assertEqual(int(result["0"][0, 0]), 2)
        self.assertEqual(int(result["90"][0, 0]), 4)

    def test_opposite_pairing_score(self):
        # q0+q2 == q1+q3, while the two alternative partitions disagree.
        composite = np.array([[1.5, 1.0], [0.5, 1.0]])
        scores = quadrant_pairing_scores(composite)
        self.assertEqual(scores["q0+q2_vs_q1+q3"], 0.0)
        self.assertGreater(scores["q0+q1_vs_q2+q3"], 0.0)
        self.assertGreater(scores["q0+q3_vs_q1+q2"], 0.0)

    def test_color_channel_saturation_is_invalid(self):
        base = np.array([[[255, 0, 0]]], dtype=np.uint8)
        channels = {name: base.copy() for name in ("0", "45", "90", "135")}
        result = polarization_features(channels, saturation_value=255)
        self.assertTrue(bool(result["saturated"][0, 0]))
        self.assertFalse(bool(result["valid"][0, 0]))


if __name__ == "__main__":
    unittest.main()
