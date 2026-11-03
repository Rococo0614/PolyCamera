import unittest

import numpy as np

from polread.polarization import linear_stokes, representation_images, virtual_analyzer


class PolarizationTests(unittest.TestCase):
    def setUp(self):
        self.channels = {
            "i0": np.array([[7.0]]),
            "i45": np.array([[6.0]]),
            "i90": np.array([[3.0]]),
            "i135": np.array([[4.0]]),
        }

    def test_stokes_and_canonical_roundtrip(self):
        stokes = linear_stokes(self.channels)
        self.assertAlmostEqual(float(stokes["s0"][0, 0]), 10.0)
        self.assertAlmostEqual(float(stokes["s1"][0, 0]), 4.0)
        self.assertAlmostEqual(float(stokes["s2"][0, 0]), 2.0)
        for angle, key in ((0, "i0"), (45, "i45"), (90, "i90"), (135, "i135")):
            reconstructed = virtual_analyzer(stokes, angle)
            self.assertTrue(np.allclose(reconstructed, self.channels[key]))

    def test_simple_representations(self):
        images = representation_images(self.channels, virtual_angles_deg=(30,))
        self.assertEqual(set(("i0", "i45", "i90", "i135", "s0", "min", "median", "mean")) - set(images), set())
        self.assertAlmostEqual(float(images["min"][0, 0]), 3.0)
        self.assertIn("virtual_030.00", images)


if __name__ == "__main__":
    unittest.main()
